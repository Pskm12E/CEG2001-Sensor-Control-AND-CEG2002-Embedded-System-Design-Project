/* FireBeetle ESP32 gateway | Group P2-2 submission, November 2026.
 * The board on the car hosts a private access point for the camera and desk Pico.
 * UART2 on GPIO16/17 connects the gateway to the MSP430 at 9600 baud.
 * A request ID ties each response to a specific outstanding request.
 * Identity and status polls expire when the supervisor stops replying.
 * HTTP GET returns the last confirmed status and its freshness.
 * Allowed HTTP POST operations are translated into bounded MSP requests.
 * Visit and job tokens identify dock and camera actions across retries.
 * The MSP decides whether a motion or pump request is permissible.
 * The gateway services Wi-Fi, UART and its diagnostic USB console cooperatively.
 */
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <RobotBench.h>
#include <NetworkConfig.h>
#include "direct_protocol.h"

// Original FireBeetle DFR0478. On robot: GPIO17 TX -> MSP P4.2 RX;
// GPIO16 RX <- MSP P4.1 TX. 3.3V UART, 9600 8N1, shared GND.
// Wi-Fi requests status/STOP or one bounded target job. MSP owns pump/resume.
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
uint32_t targetId=0;
char targetState[40]="NONE";

/* Return whether the identified MSP430 has supplied a response inside the status freshness
 * window. */
bool fresh() { return identified && seen && static_cast<uint32_t>(millis()-lastSeen)<3500u; }
/* Return text escaped for a JSON string in the gateway status response. */
String quoted(const char *text) {
    String out="\"";
    while(*text) {
        const unsigned char c=*text++;
        if(c=='"' || c=='\\') { out+='\\'; out+=static_cast<char>(c); }
        else if(c>=32 && c<127) out+=static_cast<char>(c);
    }
    out+='"'; return out;
}
/* Serialise current gateway identity, link health and the most recent MSP response for the desk
 * Pico. */
String stateJson() {
    String json="{\"board\":\"ESP32_FIREBEETLE\",\"firmware\":\"DIRECT_WIFI_V2\",\"main_controller\":\"MSP430F5529\",\"ap_ready\":";
    json+=apReady?"true":"false";
    json+=",\"msp_link\":"; json+=quoted(fresh()?"UP":seen?"STALE":"NOT_CONNECTED");
    json+=",\"fresh\":"; json+=fresh()?"true":"false";
    json+=",\"age_ms\":"; json+=seen?String(static_cast<uint32_t>(millis()-lastSeen)):"null";
    json+=",\"telemetry\":"; json+=seen?quoted(telemetry):"null";
    json+=",\"error\":"; json+=lastError[0]?quoted(lastError):"null";
    json+=",\"pending_id\":"; json+=String(pendingId);
    json+=",\"stop_id\":"; json+=String(stopId);
    json+=",\"stop_state\":"; json+=quoted(stopState);
    json+=",\"target_id\":"; json+=String(targetId);
    json+=",\"target_state\":"; json+=quoted(targetState);
    json+="}"; return json;
}
/* Send op to the MSP430 when the link permits it. fromUsb directs the reply to USB; jobToken
 * correlates a visit, job or refill setting. */
bool request(direct::Op op,bool fromUsb=false,uint32_t jobToken=0) {
    const bool action=op!=direct::Op::Ping && op!=direct::Op::Status;
    if(action && !fresh()) return false;
    if(pendingId) {
        if(!action || pendingOp==direct::Op::Stop ||
           (pendingOp!=direct::Op::Ping && pendingOp!=direct::Op::Status &&
            op!=direct::Op::Stop && op!=direct::Op::Dock)) return false;
        // A bounded job/STOP preempts telemetry polling, never another action.
        pendingId=0; pendingOp=direct::Op::None; usbRequest=false;
    }
    if(++nextId==0) ++nextId;
    pendingId=nextId; pendingOp=op; usbRequest=fromUsb;
    sentAt=lastAttempt=millis();
    if(op==direct::Op::Stop) { stopId=pendingId; strcpy(stopState,"SENT_OUTCOME_UNKNOWN"); }
    if(op==direct::Op::Target) { targetId=pendingId; strcpy(targetState,"SENT_OUTCOME_UNKNOWN"); }
    if(op==direct::Op::Resume || op==direct::Op::Dock || op==direct::Op::Depart || op==direct::Op::RefillMinimum)
        supervisor.printf("NET %lu %s %lu\n",static_cast<unsigned long>(pendingId),direct::name(op),static_cast<unsigned long>(jobToken));
    else supervisor.printf("NET %lu %s\n",static_cast<unsigned long>(pendingId),direct::name(op));
    return true;
}
/* Match an incoming MSP UART line to its pending request and update published state only for
 * accepted replies. */
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
    if(pendingOp==direct::Op::Target)
        strcpy(targetState,!strcmp(payload,"TARGET ACCEPTED")?"REQUEST_ACCEPTED":"REFUSED");
    lastError[0]=0;
    if(usbRequest) { Serial.print("MSP "); Serial.println(payload); }
    pendingId=0; pendingOp=direct::Op::None; usbRequest=false;
}
/* Handle one completed USB diagnostic line; the command whitelist bounds the operations
 * available here. */
void command(const char *line) {
    if(!strcmp(line,"PING")) Serial.println("PONG ESP32_DIRECT_WIFI_V2");
    else if(!strcmp(line,"STATUS")) {
        Serial.print("STATUS BOARD=ESP32_FIREBEETLE FW=DIRECT_WIFI_V2 AP=");
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
/* Start the local access point, initialise the MSP UART and register the status and bounded-
 * action HTTP routes. */
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
    http.on("/api/target",HTTP_POST,[]() {
        if(!request(direct::Op::Target)) { http.send(503,"application/json","{\"error\":\"MSP unavailable or busy; nothing queued\"}"); return; }
        http.send(202,"application/json",String("{\"request_id\":")+String(targetId)+",\"state\":\"SENT_OUTCOME_UNKNOWN\"}");
    });
    http.on("/api/approach",HTTP_POST,[]() {
        if(!request(direct::Op::Approach)) { http.send(503,"application/json","{}"); return; }
        http.send(202,"application/json",String("{\"request_id\":")+String(pendingId)+",\"state\":\"SENT_OUTCOME_UNKNOWN\"}");
    });
    auto visitCommand=[](direct::Op op) {
        const String token=http.arg(op==direct::Op::RefillMinimum?"raw":"job_id"); uint32_t id=0; const char *p=token.c_str();
        bool good=*p>='1' && *p<='9';
        while(*p && good) {
            const uint8_t d=static_cast<uint8_t>(*p++-'0');
            if(d>9 || id>429496729u || (id==429496729u && d>5u)) good=false;
            else id=id*10u+d;
        }
        if(!good || *p || (op==direct::Op::RefillMinimum && id>4096) || !request(op,false,id)) {
            http.send(503,"application/json","{\"error\":\"Invalid job, MSP unavailable or busy; nothing queued\"}"); return;
        }
        http.send(202,"application/json",String("{\"request_id\":")+String(pendingId)+",\"state\":\"SENT_OUTCOME_UNKNOWN\"}");
    };
    http.on("/api/resume",HTTP_POST,[visitCommand]() { visitCommand(direct::Op::Resume); });
    http.on("/api/dock",HTTP_POST,[visitCommand]() { visitCommand(direct::Op::Dock); });
    http.on("/api/depart",HTTP_POST,[visitCommand]() { visitCommand(direct::Op::Depart); });
    http.on("/api/refill-minimum",HTTP_POST,[visitCommand]() { visitCommand(direct::Op::RefillMinimum); });
    http.onNotFound([]() { http.send(404,"application/json","{\"error\":\"Unsupported route or method\"}"); });
    http.begin();
    Serial.println("ESP32 DIRECT_WIFI_V2; MSP main; status/STOP/target jobs.");
    command("STATUS");
}
/* Service HTTP, serial replies and periodic identity or status polls without blocking the car's
 * own control loop. */
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
