#include <Arduino.h>
#include <SoftwareSerial.h>
#include <avr/wdt.h>
#include <stdio.h>
#include <string.h>
#include "control.h"

// Robot MSP430 supervises movement. This Uno handles IR steering and local stops.
// Digital IR outputs: LEFT OUT -> D4; RIGHT OUT -> D2. VCC -> Uno 5V.
// MSP P3.3 -> D5 RX; D6 TX -> resistor divider -> MSP P3.4. Common ground.
// L298N D7..D10 -> IN1..IN4. ENA/ENB caps fitted: full drive, no speed PWM.
const uint8_t motorPins[4]={7,8,9,10};
const uint8_t LEFT_IR_PIN=4, RIGHT_IR_PIN=2;
const bool LEFT_FORWARD_IN1_HIGH=true, RIGHT_FORWARD_IN3_HIGH=true;
// OUT1/2 = left wheel; OUT3/4 = right wheel. Keep the requested turn direction.
const bool REVERSE_TURN_OUTPUTS=false;
const uint32_t TURN_LIMIT_MS=3000; // Allow a slow corner; still bounded if stuck.
SoftwareSerial supervisor(5,6);
// White road with black borders: both heads read white when inside the road.
RobotControl robot(WHITE_LANE,TURN_LIMIT_MS,false); // Digital; MSP grants starts.
RlParser parser={};
uint32_t lastByte=0, lastReport=0;
char usbLine[24];
uint8_t usbUsed=0;
bool usbDiscard=false;
uint8_t usbReportPart=0; // 0 overall, 1 left D4, 2 right D2; each fits TX space.

// Clear a watchdog reset before normal C++ initialisation (Uno/ATmega328P).
void disableEarlyWatchdog(void) __attribute__((naked,section(".init3"),used));
void disableEarlyWatchdog(void) { MCUSR=0; wdt_disable(); }

void applyDrive() {
    bool l=robot.action==DRIVE_FORWARD || robot.action==DRIVE_RIGHT;
    bool r=robot.action==DRIVE_FORWARD || robot.action==DRIVE_LEFT;
    if(REVERSE_TURN_OUTPUTS && (robot.action==DRIVE_LEFT || robot.action==DRIVE_RIGHT)) {
        bool swap=l; l=r; r=swap;
    }
    digitalWrite(7,l && LEFT_FORWARD_IN1_HIGH);
    digitalWrite(8,l && !LEFT_FORWARD_IN1_HIGH);
    digitalWrite(9,r && RIGHT_FORWARD_IN3_HIGH);
    digitalWrite(10,r && !RIGHT_FORWARD_IN3_HIGH);
    digitalWrite(LED_BUILTIN,robot.following);
}
void sampleLineSensors(uint32_t now) {
    robot.tick(now,digitalRead(LEFT_IR_PIN),digitalRead(RIGHT_IR_PIN));
}
const char* calibrationLabel(const LineSensor& sensor) {
    if(sensor.white<0 || sensor.black<0) return "MISSING";
    return sensor.calibrated()?"OK":"SAME";
}
void statusUsb() {
    char line[64];
    int n;
    // Alternate short reports: the old long form never fitted the Uno TX buffer
    // and its fallback silently hid the per-sensor white/black samples.
    if(usbReportPart) {
        const LineSensor& sensor=robot.sensors[usbReportPart-1];
        n=snprintf(line,sizeof(line),"IR %s RAW=%u W=%d B=%d %s\n",
            usbReportPart==1?"LEFT D4":"RIGHT D2",sensor.raw,sensor.white,sensor.black,
            calibrationLabel(sensor));
    } else {
        n=snprintf(line,sizeof(line),"UNO V2 CAL=%u FLAGS=%u DRIVE=%u REASON=%u RAW=%u/%u REQ=%u\n",robot.calibrated(),robot.flags(),unsigned(robot.action),robot.reason,robot.sensors[0].raw,robot.sensors[1].raw,robot.userRequest);
    }
    // Never block steering/MSP handling to wait for USB output space.
    if(n>0 && n<64 && Serial.availableForWrite()>=n) {
        Serial.write((uint8_t*)line,n);
        usbReportPart=(usbReportPart+1)%3;
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
            } else if(!usbDiscard && !strcmp(usbLine,"IR")) {
                usbReportPart=1; // Read-only; does not alter calibration.
            } else if(!usbDiscard) {
                uint8_t op=!strcmp(usbLine,"W")?RL_WHITE:!strcmp(usbLine,"B")?RL_BLACK:
                    !strcmp(usbLine,"C")?RL_CLEAR:!strcmp(usbLine,"F")?RL_START:0;
                if(op) Serial.println(robot.requestLocal(op)
                    ? F("REQUEST QUEUED FOR MSP430; wait for acknowledgement.")
                    : F("WAIT: need stopped MSP link, no calibration or request pending."));
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
    pinMode(LED_BUILTIN,OUTPUT); pinMode(LEFT_IR_PIN,INPUT); pinMode(RIGHT_IR_PIN,INPUT);
    robot.stop(RL_OK);
    Serial.begin(115200); supervisor.begin(9600);
    Serial.println(F("UNO WHITE-LANE-DIGITAL+MSP: w/b/c/f request MSP; s stops."));
    Serial.println(F("IR DIGITAL pins: LEFT=D4; RIGHT=D2. RAW=0/1."));
    Serial.println(F("Centred: BOTH WHITE. LEFT BLACK -> RIGHT; RIGHT BLACK -> LEFT."));
    Serial.println(F("BOTH BLACK -> STOP. Calibrate w=WHITE, b=BLACK."));
    Serial.println(F("IR: RAW/W/B. OK=ready; SAME=identical white/black levels."));
    Serial.println(F("MISSING=sample needed/unstable. Keep the SAME height for w and b."));
    Serial.print(F("Corner turn limit (ms): ")); Serial.println(TURN_LIMIT_MS);
    wdt_enable(WDTO_1S);
}
void loop() {
    wdt_reset();
    uint32_t now=millis();
    sampleLineSensors(now); applyDrive();
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
            now=millis(); sampleLineSensors(now);
            RlPacket reply=robot.handle(p,now);
            applyDrive();
            uint8_t frame[RL_SIZE]; rlEncode(&reply,frame);
            supervisor.write(frame,RL_SIZE); // Only reply after a complete request.
            if(p.type==RL_STOP) Serial.println(F("MSP STOP received. No automatic restart."));
            break;
        }
    }
    now=millis(); sampleLineSensors(now); applyDrive();
    if(uint32_t(now-lastReport)>=1000) { lastReport=now; statusUsb(); }
}
