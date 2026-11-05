#include <Arduino.h>
#include <SoftwareSerial.h>
#include <avr/wdt.h>
#include <stdio.h>
#include <string.h>
#include "control.h"

// Robot MSP430 supervises movement. This Uno handles IR steering and local stops.
// D2 left IR, D4 right IR, both powered at 3.3V; inputs have no 5V pull-up.
// MSP P3.3 -> D5 RX; D6 TX -> resistor divider -> MSP P3.4. Common ground.
// L298N D7..D10 -> IN1..IN4. ENA/ENB caps fitted: full drive, no speed PWM.
const uint8_t motorPins[4]={7,8,9,10};
const bool LEFT_FORWARD_IN1_HIGH=true, RIGHT_FORWARD_IN3_HIGH=true;
SoftwareSerial supervisor(5,6);
RobotControl robot;
RlParser parser={};
uint32_t lastByte=0, lastReport=0;
char usbLine[24];
uint8_t usbUsed=0;
bool usbDiscard=false;

// Clear a watchdog reset before normal C++ initialisation (Uno/ATmega328P).
void disableEarlyWatchdog(void) __attribute__((naked,section(".init3"),used));
void disableEarlyWatchdog(void) { MCUSR=0; wdt_disable(); }

void applyDrive() {
    bool l=robot.action==DRIVE_FORWARD || robot.action==DRIVE_RIGHT;
    bool r=robot.action==DRIVE_FORWARD || robot.action==DRIVE_LEFT;
    digitalWrite(7,l && LEFT_FORWARD_IN1_HIGH);
    digitalWrite(8,l && !LEFT_FORWARD_IN1_HIGH);
    digitalWrite(9,r && RIGHT_FORWARD_IN3_HIGH);
    digitalWrite(10,r && !RIGHT_FORWARD_IN3_HIGH);
    digitalWrite(LED_BUILTIN,robot.following);
}
void statusUsb() {
    char line[116];
    int n=snprintf(line,sizeof(line),"UNO FOLLOW V2 CAL=%u L=%u R=%u FOLLOW=%u DRIVE=%u REASON=%u SESSION=%u W=%d/%d B=%d/%d\n",
        robot.calibrated(),robot.sensors[0].raw,robot.sensors[1].raw,robot.following,
        unsigned(robot.action),robot.reason,robot.session,
        robot.sensors[0].white,robot.sensors[1].white,robot.sensors[0].black,robot.sensors[1].black);
    // The Uno USB TX buffer is 64 bytes. Emit only a short non-blocking status.
    if(n>0 && n<64 && Serial.availableForWrite()>=n) Serial.write((uint8_t*)line,n);
    else {
        n=snprintf(line,sizeof(line),"UNO V2 FLAGS=%u DRIVE=%u REASON=%u RAW=%u/%u\n",robot.flags(),unsigned(robot.action),robot.reason,robot.sensors[0].raw,robot.sensors[1].raw);
        if(n>0 && n<64 && Serial.availableForWrite()>=n) Serial.write((uint8_t*)line,n);
    }
}
void readUsb() {
    uint8_t budget=32;
    while(budget-- && Serial.available()) {
        int c=Serial.read();
        if(c=='\n' || c=='\r') {
            usbLine[usbUsed]=0;
            if(!usbDiscard && (!strcmp(usbLine,"S") || !strcmp(usbLine,"STOP"))) {
                robot.stop(RL_LOCAL_STOP); applyDrive();
            }
            if(!usbDiscard && usbUsed) statusUsb();
            usbUsed=0; usbDiscard=false;
        } else if(c<32 || c>126 || usbUsed>=sizeof(usbLine)-1) {
            usbDiscard=true; robot.stop(RL_BAD_FRAME); applyDrive();
        } else if(!usbDiscard) {
            if(c>='a' && c<='z') c-=32;
            usbLine[usbUsed++]=(char)c;
        }
    }
}
void setup() {
    for(uint8_t p:motorPins) { digitalWrite(p,LOW); pinMode(p,OUTPUT); }
    pinMode(LED_BUILTIN,OUTPUT); pinMode(2,INPUT); pinMode(4,INPUT);
    robot.stop(RL_OK);
    Serial.begin(115200); supervisor.begin(9600);
    Serial.println(F("UNO V2: MSP START only; USB S stops; calibration from MSP."));
    wdt_enable(WDTO_1S);
}
void loop() {
    wdt_reset();
    uint32_t now=millis();
    robot.tick(now,digitalRead(2),digitalRead(4)); applyDrive();
    readUsb();
    if(supervisor.overflow()) { parser.used=0; robot.stop(RL_BAD_FRAME); applyDrive(); }
    if(parser.used && uint32_t(now-lastByte)>100) { parser.used=0; robot.stop(RL_BAD_FRAME); applyDrive(); }
    uint8_t budget=32;
    while(budget-- && supervisor.available()) {
        RlPacket p;
        lastByte=millis();
        int result=rlFeed(&parser,(uint8_t)supervisor.read(),&p);
        if(result<0) { robot.stop(RL_BAD_FRAME); applyDrive(); }
        else if(result>0 && !(p.type&RL_REPLY)) {
            now=millis(); robot.tick(now,digitalRead(2),digitalRead(4));
            RlPacket reply=robot.handle(p,now);
            applyDrive();
            uint8_t frame[RL_SIZE]; rlEncode(&reply,frame);
            supervisor.write(frame,RL_SIZE); // Only reply after a complete request.
            break;
        }
    }
    now=millis(); robot.tick(now,digitalRead(2),digitalRead(4)); applyDrive();
    if(uint32_t(now-lastReport)>=1000) { lastReport=now; statusUsb(); }
}
