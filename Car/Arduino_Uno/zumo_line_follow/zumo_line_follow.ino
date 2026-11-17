// Black line on white, based on the user's working ZumoShield PD follower.
// MSP P3.3 -> D6 RX; D13 TX -> 2.2k/2.2k divider -> MSP P3.4 RX.
// D13 is UART TX: do not use LED_BUILTIN or a buzzer here.
#include <Wire.h>
#include <ZumoShield.h>
#include <SoftwareSerial.h>
#include <avr/wdt.h>
#include <stdio.h>
#include <string.h>
#include "zumo_control.h"

const uint8_t MSP_RX_PIN = 6;
const uint8_t MSP_TX_PIN = 13;
const uint32_t SERIAL_BAUD = 9600;
const uint8_t CALIBRATION_STEPS = 80;
const int CALIBRATION_SPEED = 200;
const uint16_t CALIBRATION_START_DELAY_MS = 1000;
const uint8_t CALIBRATION_INTERVAL_MS = 20;
const uint8_t FRAME_TIMEOUT_MS = 100;
const uint16_t REPORT_INTERVAL_MS = 1000;
const int LINE_CENTER = 2500;

ZumoReflectanceSensorArray reflectanceSensors;
ZumoMotors motors;
Pushbutton button(ZUMO_BUTTON);
SoftwareSerial mspSerial(MSP_RX_PIN, MSP_TX_PIN);
ZumoControl robot;
RlParser parser={};

const int MAX_SPEED=150;
const float kp=1.0f, kd=0.0f;
int lastError=0;
uint8_t calibrationStep=0;
uint32_t nextCalibration=0, lastByte=0, lastReport=0;
bool suppressButtonRelease=false;
char usbLine[16];
uint8_t usbUsed=0;
bool usbDiscard=false;
uint8_t usbReportPart=0; // 0 idle, 1 status, 2 persistent event; each fits USB TX.

void disableEarlyWatchdog(void) __attribute__((naked,section(".init3"),used));
void disableEarlyWatchdog(void) { MCUSR=0; wdt_disable(); }

void applyStop() { if(!robot.moving()) motors.setSpeeds(0,0); }
void stopLocal(uint8_t why) { robot.stop(why); motors.setSpeeds(0,0); lastError=0; }

void reportUsb() {
    if(!usbReportPart) return;
    char line[64];
    int n;
    if(usbReportPart==1) {
        n=snprintf(line,sizeof(line),"ZUMO FW=OG3 CAL=%u SWEEP=%u RUN=%u REASON=%u REQ=%u\n",
            robot.calibrated,robot.calibrating,robot.following,robot.reason,robot.userRequest);
    } else {
        const char *event="BOOT";
        switch(robot.lastEvent) {
        case ZE_CALIBRATING: event="SWEEP"; break;
        case ZE_CAL_DONE: event="CAL_DONE"; break;
        case ZE_FOLLOWING: event="FOLLOWING"; break;
        case ZE_MSP_STOP: event="MSP_STOP"; break;
        case ZE_MSP_RESYNC: event="MSP_RESYNC"; break;
        case ZE_HEARTBEAT_LOST: event="HEARTBEAT_LOST"; break;
        case ZE_UART_ERROR: event="UART_ERROR"; break;
        case ZE_LOCAL_STOP: event="LOCAL_STOP"; break;
        case ZE_SESSION_ERROR: event="SESSION_ERROR"; break;
        }
        n=snprintf(line,sizeof(line),"ZUMO FW=OG3 STEP=%u/80 LAST=%s UP=%lu\n",
            calibrationStep,event,(unsigned long)(millis()/1000u));
    }
    if(n>0 && n<int(sizeof(line)) && Serial.availableForWrite()>=n) {
        Serial.write((uint8_t*)line,n);
        if(++usbReportPart>2) usbReportPart=0;
    }
}

void readUsb() {
    uint8_t budget=32;
    while(budget-- && Serial.available()) {
        int c=Serial.read();
        if(c=='\n' || c=='\r') {
            usbLine[usbUsed]=0;
            if(!usbDiscard) {
                if(!strcmp(usbLine,"S") || !strcmp(usbLine,"STOP")) stopLocal(RL_LOCAL_STOP);
                else if(!strcmp(usbLine,"C")) robot.requestLocal(RL_ZUMO_CALIBRATE);
                else if(!strcmp(usbLine,"F")) robot.requestLocal(RL_START);
                else if(!strcmp(usbLine,"STATUS")) usbReportPart=1;
            }
            usbUsed=0; usbDiscard=false;
        } else if(c<32 || c>126 || usbUsed>=sizeof(usbLine)-1) {
            usbDiscard=true; stopLocal(RL_BAD_FRAME);
        } else if(!usbDiscard) {
            if(c>='a' && c<='z') c-=32;
            usbLine[usbUsed++]=(char)c;
        }
    }
}

void serviceButton() {
    // Stop on press, consume its release so the same press cannot restart.
    if(button.isPressed() && robot.moving()) {
        stopLocal(RL_LOCAL_STOP); suppressButtonRelease=true;
    }
    if(button.getSingleDebouncedRelease()) {
        if(suppressButtonRelease) suppressButtonRelease=false;
        else robot.requestLocal(robot.calibrated?RL_START:RL_ZUMO_CALIBRATE);
    }
}

void serviceLink() {
    uint32_t now=millis();
    robot.tick(now); applyStop();
    if(mspSerial.overflow()) { parser.used=0; stopLocal(RL_BAD_FRAME); }
    if(parser.used && uint32_t(now-lastByte)>FRAME_TIMEOUT_MS) { parser.used=0; stopLocal(RL_BAD_FRAME); }
    uint8_t budget=32;
    while(budget-- && mspSerial.available()) {
        RlPacket p;
        lastByte=millis();
        int result=rlFeed(&parser,(uint8_t)mspSerial.read(),&p);
        if(result<0) stopLocal(RL_BAD_FRAME);
        else if(result>0 && !(p.type&RL_REPLY)) {
            bool wasCalibrating=robot.calibrating, wasFollowing=robot.following;
            RlPacket reply=robot.handle(p,millis());
            applyStop(); // Apply STOP before sending the acknowledgement.
            if(robot.calibrating && !wasCalibrating) {
                motors.setSpeeds(0,0); reflectanceSensors.resetCalibration();
                calibrationStep=0; nextCalibration=millis()+CALIBRATION_START_DELAY_MS;
            }
            if(robot.following && !wasFollowing) lastError=0;
            uint8_t frame[RL_SIZE]; rlEncode(&reply,frame);
            mspSerial.write(frame,RL_SIZE); // Half duplex: reply only to a request.
            break;
        }
    }
}

void serviceMotion() {
    uint32_t now=millis();
    robot.tick(now); applyStop();
    // Do not start a sensor read while a received UART frame is incomplete.
    if(parser.used || mspSerial.available()) return;
    if(robot.calibrating) {
        if(int32_t(now-nextCalibration)<0) return;
        if(calibrationStep>=CALIBRATION_STEPS) {
            motors.setSpeeds(0,0); robot.finishCalibration(); return;
        }
        uint8_t i=calibrationStep;
        if((i>10 && i<=30) || (i>50 && i<=70))
            motors.setSpeeds(-CALIBRATION_SPEED,CALIBRATION_SPEED);
        else motors.setSpeeds(CALIBRATION_SPEED,-CALIBRATION_SPEED);
        reflectanceSensors.calibrate(); // Ten bounded RC reads, not an 80-step blocking loop.
        ++calibrationStep; nextCalibration=millis()+CALIBRATION_INTERVAL_MS;
    } else if(robot.following) {
        unsigned int sensors[6];
        int read_position=reflectanceSensors.readLine(sensors);
        // UART STOP and lease expiry win over the reading just obtained.
        serviceLink(); serviceButton();
        if(!robot.following) { applyStop(); return; }
        int error=read_position-LINE_CENTER;
        int speedDiff=kp*error+kd*(error-lastError);
        lastError=error;
        // Original motor calculation: upper clamp only; reverse remains allowed.
        int m1Speed=MAX_SPEED+speedDiff;
        int m2Speed=MAX_SPEED-speedDiff;
        if(m1Speed>MAX_SPEED) m1Speed=MAX_SPEED;
        if(m2Speed>MAX_SPEED) m2Speed=MAX_SPEED;
        motors.setSpeeds(m1Speed,m2Speed);
    }
}

void setup() {
    motors.setSpeeds(0,0);
    Serial.begin(SERIAL_BAUD);
    mspSerial.begin(SERIAL_BAUD);
    reflectanceSensors.init();
    Serial.println(F("ZUMO FW=OG3 ORIGINAL CAL+PD + MSP STOP"));
    Serial.println(F("USB 9600: C=sweep request, F=follow request, S=stop, STATUS."));
    wdt_enable(WDTO_1S);
}

void loop() {
    wdt_reset();
    serviceLink();
    readUsb();
    serviceButton();
    serviceMotion();
    serviceLink();
    applyStop();
    uint32_t now=millis();
    if(uint32_t(now-lastReport)>=REPORT_INTERVAL_MS) {
        lastReport=now;
        if(!usbReportPart) usbReportPart=1;
    }
    reportUsb();
}
