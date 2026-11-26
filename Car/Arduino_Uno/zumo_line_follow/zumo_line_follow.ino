/* Arduino Uno and Zumo Shield | OG9 | Group P2-2 submission, November 2026.
 * Six reflectance channels give the position of the line under the chassis.
 * A first local request performs a rotating sweep over both track surfaces.
 * A valid sweep is saved in EEPROM and restored at the next power-up.
 * A second press requests line following from the car MSP430.
 * SoftwareSerial receives the MSP on D6 and replies on D13 at 9600 baud.
 * A framed session and motion lease bound the age of a drive permission.
 * The steering loop adjusts both tracks, with a slower fixed speed in reverse.
 * Local stop and lost heartbeat remove motor commands before the next run.
 * The accelerometer and buzzer provide the optional inversion warning.
 * USB reports the state and accepts local diagnostic commands.
 */
#include <Wire.h>
#include <ZumoShield.h>
#include <SoftwareSerial.h>
#include <avr/wdt.h>
#include <stdio.h>
#include <string.h>
#include "zumo_control.h"
#include "flip_alarm.h"
#include "line_calibration.h"

const uint8_t MSP_RX_PIN = 6;
const uint8_t MSP_TX_PIN = 13;
const uint32_t SERIAL_BAUD = 9600;
const uint8_t CALIBRATION_STEPS = 80;
const int CALIBRATION_SPEED = 200;
const uint16_t CALIBRATION_START_DELAY_MS = 1000;
const uint8_t CALIBRATION_INTERVAL_MS = 20;
const uint8_t FRAME_TIMEOUT_MS = 100;
const uint16_t REPORT_INTERVAL_MS = 1000;
const uint16_t ALARM_BUTTON_HOLD_MS = 2000;
const int LINE_CENTER = 2500;

ZumoReflectanceSensorArray reflectanceSensors;
ZumoMotors motors;
Pushbutton button(ZUMO_BUTTON);
FlipAlarm flipAlarm;
SoftwareSerial mspSerial(MSP_RX_PIN, MSP_TX_PIN);
ZumoControl robot;
RlParser parser={};

const int FOLLOW_SPEED=90;
const int TURN_MAX_SPEED=250;
const int REVERSE_MAX_SPEED=400;
const int EMPTY_TANK_SPEED=100;
const float kp=1.0f, kd=0.0f;
int lastError=0;
uint8_t calibrationStep=0;
uint32_t nextCalibration=0, lastByte=0, lastReport=0;
bool suppressButtonRelease=false;
bool timingButtonHold=false;
uint32_t buttonPressedAt=0;
char usbLine[16];
uint8_t usbUsed=0;
bool usbDiscard=false;
uint8_t usbReportPart=0; // 0 idle, 1 motion, 2 last event, 3 flip alarm.

void disableEarlyWatchdog(void) __attribute__((naked,section(".init3"),used));
/* Disable an inherited watchdog during AVR startup before the sketch configures its own
 * watchdog. */
void disableEarlyWatchdog(void) { MCUSR=0; wdt_disable(); }

/* Write zero to both motor channels as soon as the current robot state no longer permits
 * movement. */
void applyStop() { if(!robot.moving()) motors.setSpeeds(0,0); }
/* Record local stop reason why, stop both tracks and reset accumulated line error. */
void stopLocal(uint8_t why) { robot.stop(why); motors.setSpeeds(0,0); lastError=0; }

/* Write one USB diagnostic segment when there is room, leaving the motion loop free between
 * segments. */
void reportUsb() {
    if(!usbReportPart) return;
    char line[64];
    int n;
    if(usbReportPart==1) {
        n=snprintf(line,sizeof(line),"ZUMO FW=OG9 CAL=%u SWEEP=%u RUN=%u REASON=%u REQ=%u\n",
            robot.calibrated,robot.calibrating,robot.following,robot.reason,robot.userRequest);
    } else if(usbReportPart==2) {
        const char *event="BOOT";
        switch(robot.lastEvent) {
        case ZE_CALIBRATING: event="SWEEP"; break;
        case ZE_CAL_DONE: event="CAL_DONE"; break;
        case ZE_CAL_RESTORED: event="CAL_RESTORED"; break;
        case ZE_FOLLOWING: event="FOLLOWING"; break;
        case ZE_MSP_STOP: event="MSP_STOP"; break;
        case ZE_MSP_RESYNC: event="MSP_RESYNC"; break;
        case ZE_HEARTBEAT_LOST: event="HEARTBEAT_LOST"; break;
        case ZE_UART_ERROR: event="UART_ERROR"; break;
        case ZE_LOCAL_STOP: event="LOCAL_STOP"; break;
        case ZE_SESSION_ERROR: event="SESSION_ERROR"; break;
        case ZE_OBSTACLE_PAUSE: event="OBSTACLE_PAUSE"; break;
        case ZE_EMPTY_REVERSE: event="EMPTY_REVERSE"; break;
        case ZE_REVERSE_DONE: event="REVERSE_DONE"; break;
        }
        n=snprintf(line,sizeof(line),"ZUMO FW=OG9 STEP=%u/80 LAST=%s UP=%lu\n",
            calibrationStep,event,(unsigned long)(millis()/1000u));
    } else {
        n=snprintf(line,sizeof(line),"FLIP ALARM=%s IMU=%s FLIPPED=%u Z=%d UP_Z=%d\n",
            flipAlarm.enabled?"ON":"OFF",flipAlarm.enabled?(flipAlarm.sensorReady?"OK":"MISSING"):"IDLE",
            flipAlarm.flipped,flipAlarm.z,flipAlarm.uprightSign);
    }
    if(n>0 && n<int(sizeof(line)) && Serial.availableForWrite()>=n) {
        Serial.write((uint8_t*)line,n);
        if(++usbReportPart>3) usbReportPart=0;
    }
}

/* Consume bounded diagnostic and calibration commands from USB and discard malformed or overlong
 * lines. */
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
                else if(!strcmp(usbLine,"ALARM OFF")) flipAlarm.setEnabled(false);
                else if(!strcmp(usbLine,"ALARM ON")) flipAlarm.setEnabled(true);
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

/* Distinguish a short press from a parked long hold. Stop moving tracks immediately on a local
 * stop. */
void serviceButton() {
    // Stop on press, consume its release so the same press cannot restart.
    const bool pressed = button.isPressed();
    if (pressed && (robot.moving() || robot.obstaclePaused)) {
        stopLocal(RL_LOCAL_STOP);
        suppressButtonRelease = true;
    }
    // Only a parked hold toggles the alarm. Consume its release like a STOP
    // so muting the buzzer cannot also request a powered calibration or start.
    if (pressed && !suppressButtonRelease) {
        if (!timingButtonHold) {
            timingButtonHold = true;
            buttonPressedAt = millis();
        }
        if (uint32_t(millis() - buttonPressedAt) >= ALARM_BUTTON_HOLD_MS) {
            flipAlarm.setEnabled(!flipAlarm.enabled);
            suppressButtonRelease = true;
        }
    } else {
        timingButtonHold = false;
    }
    if (button.getSingleDebouncedRelease()) {
        if (suppressButtonRelease) suppressButtonRelease = false;
        else robot.requestLocal(robot.calibrated ? RL_START : RL_ZUMO_CALIBRATE);
    }
}

/* Validate complete MSP frames, apply a command and send the corresponding Uno state and
 * acknowledgement. */
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
            bool wasCalibrating=robot.calibrating, wasFollowing=robot.following, wasReversing=robot.reversing;
            RlPacket reply=robot.handle(p,millis());
            if((wasFollowing && robot.reversing) || (wasReversing && robot.following))
                motors.setSpeeds(0,0);
            applyStop(); // Apply STOP before sending the acknowledgement.
            if(p.type==RL_CLEAR && reply.detail==RL_OK) LineCalibration::clear();
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

/* Advance the timed calibration, reverse or line-follow state and calculate each track speed
 * from sensor position. */
void serviceMotion() {
    uint32_t now=millis();
    robot.tick(now); applyStop();
    // Do not start a sensor read while a received UART frame is incomplete.
    if(parser.used || mspSerial.available()) return;
    if(robot.reversing) {
        motors.setSpeeds(-EMPTY_TANK_SPEED,-EMPTY_TANK_SPEED);
    } else if(robot.calibrating) {
        if(int32_t(now-nextCalibration)<0) return;
        if(calibrationStep>=CALIBRATION_STEPS) {
            motors.setSpeeds(0,0);
            robot.finishCalibration();
            if (LineCalibration::save(reflectanceSensors))
                Serial.println(F("Line calibration saved."));
            else
                Serial.println(F("Sweep not saved. Check all six sensors cross black and white."));
            return;
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
        // Cruise slowly past camera targets. Give the outside track extra drive in turns.
        int m1Speed=FOLLOW_SPEED+speedDiff;
        int m2Speed=FOLLOW_SPEED-speedDiff;
        if(m1Speed>TURN_MAX_SPEED) m1Speed=TURN_MAX_SPEED;
        if(m2Speed>TURN_MAX_SPEED) m2Speed=TURN_MAX_SPEED;
        if(m1Speed<-REVERSE_MAX_SPEED) m1Speed=-REVERSE_MAX_SPEED;
        if(m2Speed<-REVERSE_MAX_SPEED) m2Speed=-REVERSE_MAX_SPEED;
        motors.setSpeeds(m1Speed,m2Speed);
    }
}

/* Initialise the shield, serial links and watchdog, then restore valid EEPROM line calibration
 * while parked. */
void setup() {
    motors.setSpeeds(0,0);
    Serial.begin(SERIAL_BAUD);
    mspSerial.begin(SERIAL_BAUD);
    reflectanceSensors.init();
    robot.calibrated = LineCalibration::restore(reflectanceSensors);
    if (robot.calibrated) robot.lastEvent = ZE_CAL_RESTORED;
    flipAlarm.begin();
    Serial.println(F("ZUMO FW=OG9 SAVED LINE CAL + PD + FLIP ALARM + CONTINUOUS LOW-WATER REVERSE"));
    Serial.println(F("USB 9600: C=sweep request, F=follow request, S=stop, STATUS."));
    wdt_enable(WDTO_1S);
}

/* Service local input, MSP traffic, motion and flip monitoring frequently enough to enforce the
 * movement lease. */
void loop() {
    wdt_reset();
    serviceLink();
    readUsb();
    serviceButton();
    serviceMotion();
    serviceLink();
    applyStop();
    if(!parser.used && !mspSerial.available())
        flipAlarm.service(millis(), robot.calibrating && calibrationStep == 0);
    uint32_t now=millis();
    if(uint32_t(now-lastReport)>=REPORT_INTERVAL_MS) {
        lastReport=now;
        if(!usbReportPart) usbReportPart=1;
    }
    reportUsb();
}
