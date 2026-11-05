#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <RobotBench.h>
#include <NetworkConfig.h>
#include "direct_protocol.h"

// Original FireBeetle DFR0478. On robot: GPIO17 TX -> MSP P4.2 RX;
// GPIO16 RX <- MSP P4.1 TX. 3.3V UART, 9600 8N1, shared GND.
// Wi-Fi can request status/identity/STOP only. MSP retains all robot decisions.
HardwareSerial supervisor(2);
WebServer http(80);
bench::Line<64> usbLine;
bench::Line<384> uartLine;
bool apReady=false,identified=false,seen=false,usbRequest=false;
uint32_t nextId=0,pendingId=0,sentAt=0,lastAttempt=0,lastSeen=0;
direct::Op pendingOp=direct::Op::None;
char telemetry[320]={};
char lastError[64]="MSP not connected";
char stopState[40]="NONE";
uint32_t stopId=0;

bool fresh() { return identified && seen && static_cast<uint32_t>(millis()-lastSeen)<3500u; }
String quoted(const char *text) {
    String out="\"";
    while(*text) {
        const unsigned char c=*text++;
        if(c=='"' || c=='\\') { out+='\\'; out+=static_cast<char>(c); }
        else if(c>=32 && c<127) out+=static_cast<char>(c);
    }
    out+='"'; return out;
}
String stateJson() {
    String json="{\"board\":\"ESP32_FIREBEETLE\",\"firmware\":\"DIRECT_WIFI_V1\",\"main_controller\":\"MSP430F5529\",\"ap_ready\":";
    json+=apReady?"true":"false";
    json+=",\"msp_link\":"; json+=quoted(fresh()?"UP":seen?"STALE":"NOT_CONNECTED");
    json+=",\"fresh\":"; json+=fresh()?"true":"false";
    json+=",\"age_ms\":"; json+=seen?String(static_cast<uint32_t>(millis()-lastSeen)):"null";
    json+=",\"telemetry\":"; json+=seen?quoted(telemetry):"null";
    json+=",\"error\":"; json+=lastError[0]?quoted(lastError):"null";
    json+=",\"pending_id\":"; json+=String(pendingId);
    json+=",\"stop_id\":"; json+=String(stopId);
    json+=",\"stop_state\":"; json+=quoted(stopState);
    json+="}"; return json;
}
bool request(direct::Op op,bool fromUsb=false) {
    if(pendingId) return false; // no queue, and no replay after timeout/reconnect
    if(op==direct::Op::Stop && !fresh()) return false;
    if(++nextId==0) ++nextId;
    pendingId=nextId; pendingOp=op; usbRequest=fromUsb;
    sentAt=lastAttempt=millis();
    if(op==direct::Op::Stop) { stopId=pendingId; strcpy(stopState,"SENT_OUTCOME_UNKNOWN"); }
    supervisor.printf("NET %lu %s\n",static_cast<unsigned long>(pendingId),direct::name(op));
    return true;
}
void receive(const char *line) {
    uint32_t id=0; const char *payload=nullptr;
    if(!direct::frame(line,id,payload) || !pendingId || id!=pendingId) return;
    if(!direct::matches(pendingOp,payload)) {
        strcpy(lastError,"Invalid MSP reply"); return;
    }
    if(pendingOp==direct::Op::Ping) identified=true;
    if(pendingOp==direct::Op::Status) {
        // Status polling starts only after the expected MSP firmware identifies.
        snprintf(telemetry,sizeof(telemetry),"%s",payload); seen=true; lastSeen=millis();
    }
    if(pendingOp==direct::Op::Stop) strcpy(stopState,"REQUEST_ACCEPTED");
    lastError[0]=0;
    if(usbRequest) { Serial.print("MSP "); Serial.println(payload); }
    pendingId=0; pendingOp=direct::Op::None; usbRequest=false;
}
void command(const char *line) {
    if(!strcmp(line,"PING")) Serial.println("PONG ESP32_DIRECT_WIFI_V1");
    else if(!strcmp(line,"STATUS")) {
        Serial.print("STATUS BOARD=ESP32_FIREBEETLE FW=DIRECT_WIFI_V1 AP=");
        Serial.print(apReady?"READY":"FAILED");
        Serial.print(" MSP_LINK="); Serial.print(fresh()?"UP":seen?"STALE":"NOT_CONNECTED");
        Serial.print(" MSP_UART_RX=16 MSP_UART_TX=17 IP="); Serial.println(WiFi.softAPIP());
    } else if(!strcmp(line,"STATE")) Serial.println(stateJson());
    else if(!strcmp(line,"MSP PING") || !strcmp(line,"MSP STATUS") || !strcmp(line,"MSP STOP")) {
        const direct::Op op=!strcmp(line,"MSP PING")?direct::Op::Ping:
                            !strcmp(line,"MSP STATUS")?direct::Op::Status:direct::Op::Stop;
        if(op==direct::Op::Status && !identified) { Serial.println("ERROR MSP identity not verified"); return; }
        if(!request(op,true)) Serial.println("ERROR MSP unavailable or busy; request not queued");
        else { Serial.print("MSP REQUEST ID="); Serial.println(pendingId); }
    } else if(!strcmp(line,"HELP") || !strcmp(line,"?"))
        Serial.println("PING | STATUS | STATE | MSP PING | MSP STATUS | MSP STOP. No start/spray/calibration commands.");
    else Serial.println("ERROR unsupported command");
}
void setup() {
    Serial.begin(115200);
    supervisor.begin(9600,SERIAL_8N1,16,17);
    nextId=esp_random();
    WiFi.mode(WIFI_AP);
    WiFi.softAPConfig(IPAddress(192,168,4,1),IPAddress(192,168,4,1),IPAddress(255,255,255,0));
    apReady=WiFi.softAP(BENCH_SSID,BENCH_PASSWORD,6,false,2);
    http.on("/",HTTP_GET,[]() { http.send(200,"application/json",stateJson()); });
    http.on("/api/state",HTTP_GET,[]() { http.send(200,"application/json",stateJson()); });
    http.on("/api/stop",HTTP_POST,[]() {
        if(!request(direct::Op::Stop)) { http.send(503,"application/json","{\"error\":\"MSP unavailable or busy; nothing queued\"}"); return; }
        http.send(202,"application/json",String("{\"request_id\":")+String(stopId)+",\"state\":\"SENT_OUTCOME_UNKNOWN\"}");
    });
    http.onNotFound([]() { http.send(404,"application/json","{\"error\":\"Unsupported route or method\"}"); });
    http.begin();
    Serial.println("ESP32 DIRECT_WIFI_V1; MSP main; STATUS/STOP bridge; Pico not required.");
    command("STATUS");
}
void loop() {
    // Drain UART before handling HTTP to limit overrun at the MSP's 9600 baud.
    for(unsigned n=0;n<384 && supervisor.available();++n) {
        const auto result=uartLine.push(static_cast<uint8_t>(supervisor.read()));
        if(result==bench::Feed::Ready) receive(uartLine.text);
        else if(result==bench::Feed::Invalid) strcpy(lastError,"Invalid or oversized MSP line");
        if(result!=bench::Feed::Pending) uartLine.reset();
    }
    if(pendingId && static_cast<uint32_t>(millis()-sentAt)>=1500u) {
        if(usbRequest) Serial.println("ERROR MSP reply timed out; request not replayed");
        strcpy(lastError,"MSP UART reply timed out");
        pendingId=0; pendingOp=direct::Op::None; usbRequest=false; identified=false; seen=false;
        uartLine.reset(); // status may be requested again; a STOP is never replayed
    }
    http.handleClient();
    for(unsigned n=0;n<128 && Serial.available();++n) {
        const auto result=usbLine.push(static_cast<uint8_t>(Serial.read()));
        if(result==bench::Feed::Ready) command(usbLine.text);
        else if(result==bench::Feed::Invalid) Serial.println("ERROR invalid or oversized USB line");
        if(result!=bench::Feed::Pending) usbLine.reset();
    }
    if(!pendingId && static_cast<uint32_t>(millis()-lastAttempt)>=1000u)
        request(identified?direct::Op::Status:direct::Op::Ping);
    delay(1);
}
