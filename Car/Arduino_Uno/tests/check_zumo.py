"""Run the actual Zumo sketch, MSP scheduler and sonar adapter with fake hardware.

No serial ports are opened. Motor output, button events and sensor timing are
simulated; the real AVR/CCS builds verify the target-library interfaces separately.
"""
from pathlib import Path
import ast
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "Car/Arduino_Uno/build/zumo-tests"
BUILD.mkdir(parents=True, exist_ok=True)
source = (ROOT / "Car/MSP430/robot_supervisor/main.c").read_text()


def function(name, returns="void"):
    start = source.index("static " + returns + ("" if returns.endswith("*") else " ") + name + "(")
    brace = source.index("{", start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


stubs = {
    "Arduino.h": r'''
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cassert>
#include <deque>
#include <vector>
#include <string>
#include <functional>
inline uint32_t fakeMillis;
inline uint8_t MCUSR;
inline uint32_t millis() { return fakeMillis; }
#define F(x) x
struct FakeSerial {
    std::deque<uint8_t> input;
    std::vector<uint8_t> output;
    unsigned baud=0;
    void begin(unsigned n) { baud=n; }
    int available() { return int(input.size()); }
    int availableForWrite() { return 64; }
    int read() { int c=input.front(); input.pop_front(); return c; }
    void println(const char*) {}
    void write(const uint8_t* b,size_t n) { output.insert(output.end(),b,b+n); }
    void send(const char* s) { while(*s) input.push_back(uint8_t(*s++)); }
};
inline FakeSerial Serial;
''',
    "Wire.h": r'''
#pragma once
#include <Arduino.h>
inline struct { void begin() {} void setWireTimeout(uint32_t,bool) {} } Wire;
''',
    "EEPROM.h": r'''
#pragma once
#include <Arduino.h>
inline struct {
    uint8_t values[1024];
    int length() { return sizeof(values); }
    uint8_t read(int i) { assert(i>=0 && i<length()); return values[i]; }
    void update(int i,uint8_t v) { assert(i>=0 && i<length()); values[i]=v; }
    template<typename T> void put(int i, const T& value) {
        const auto* bytes=reinterpret_cast<const uint8_t*>(&value);
        for(size_t n=0;n<sizeof(T);++n) update(i+n,bytes[n]);
    }
    template<typename T> void get(int i,T& value) {
        auto* bytes=reinterpret_cast<uint8_t*>(&value);
        for(size_t n=0;n<sizeof(T);++n) bytes[n]=read(i+n);
    }
} EEPROM;
''',
    "SoftwareSerial.h": r'''
#pragma once
#include <Arduino.h>
class SoftwareSerial: public FakeSerial {
public:
    unsigned rx,tx;
    bool overflowed=false;
    std::function<void()> beforeWrite;
    SoftwareSerial(unsigned r,unsigned t):rx(r),tx(t) {}
    bool overflow() { bool result=overflowed; overflowed=false; return result; }
    void write(const uint8_t* b,size_t n) {
        if(beforeWrite) beforeWrite();
        FakeSerial::write(b,n);
    }
};
''',
    "ZumoShield.h": r'''
#pragma once
#include <Arduino.h>
#define ZUMO_BUTTON 12
inline bool imuPresent=true, readFails=false;
inline int16_t measuredZ=-15700;
inline unsigned beeps=0, silences=0;
struct ZumoIMU {
    struct { int16_t z=0; } a;
    bool init() { return imuPresent; }
    void enableDefault() {}
    uint8_t getLastError() { return readFails; }
    void readAcc() { a.z=measuredZ; }
};
struct ZumoBuzzer {
    void playFrequency(unsigned hz,unsigned duration,unsigned volume) {
        assert(hz && duration==120 && volume); ++beeps;
    }
    void stopPlaying() { ++silences; }
};
class ZumoMotors {
public:
    int left=0,right=0;
    void setSpeeds(int l,int r) { left=l; right=r; }
};
class Pushbutton {
public:
    bool pressed=false,released=false;
    explicit Pushbutton(int) {}
    bool isPressed() { return pressed; }
    bool getSingleDebouncedRelease() { bool r=released; released=false; return r; }
};
class ZumoReflectanceSensorArray {
public:
    unsigned int lows[6]={},highs[6]={};
    unsigned int* calibratedMinimumOn=nullptr;
    unsigned int* calibratedMaximumOn=nullptr;
    bool badContrast=false;
    unsigned offset=0;
    unsigned samples=0;
    int position=2500;
    std::function<void()> onRead;
    void init() {}
    void resetCalibration() { samples=0; }
    void calibrate() {
        ++samples; fakeMillis+=20;
        calibratedMinimumOn=lows; calibratedMaximumOn=highs;
        for(int i=0;i<6;++i) {
            lows[i]=100+offset+i; highs[i]=badContrast?lows[i]:900+offset+2*i;
        }
    }
    int readLine(unsigned int* values) {
        for(int i=0;i<6;++i) values[i]=(i==2)?1000:0;
        if(onRead) { auto callback=onRead; onRead=nullptr; callback(); }
        return position;
    }
};
''',
    "avr/wdt.h": r'''
#pragma once
#define WDTO_1S 1
inline void wdt_disable() {}
inline void wdt_enable(int) {}
inline void wdt_reset() {}
''',
}
for name, text in stubs.items():
    path = BUILD / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

prefix = r'''
#include <Arduino.h>
#include <fstream>
#define ZUMO_BASE 1
#define TANK_EMPTY_ADC 1836
#define TANK_FULL_ADC 2281
#define SUPERVISOR_ESP_UART 1
#define PUMP_DRIVER_VERIFIED 1
#define __interrupt
#define __disable_interrupt() ((void)0)
#define __enable_interrupt() ((void)0)
#define __bic_SR_register_on_exit(x) ((void)(x))
#include "../../zumo_line_follow/zumo_line_follow.ino"
#include "../../../ESP32_Gateway/robot_wifi_gateway/direct_protocol.h"
namespace msp {
enum { BIT0=1,BIT2=4,BIT6=64,BIT7=128,TASSEL__SMCLK=512,MC__CONTINUOUS=32,TACLR=4,CCIE=16,LPM0_bits=16,ADC12BUSY=1,ADC12SC=1 };
static uint8_t P3SEL,P3REN,P3OUT,P3DIR,P2SEL,P2DIR,P2OUT,P2REN,P2IE,P2IES,P2IFG,P2IN,P4OUT;
static uint16_t TA2CCTL0,TA2CTL,TA2CCR0,TA2R,ticks;
static uint8_t P1OUT,stopButton;
static uint16_t ADC12IFG,ADC12MEM0,ADC12CTL0,ADC12CTL1,waterRaw,waterAt,lastWaterSample;
#include "../../../MSP430/robot_supervisor/spray_job.h"
#include "../../../MSP430/robot_supervisor/water_level.h"
static WaterLevel tank;
static Refill refill={DEFAULT_REFILL_RAW,0,REFILL_WATCH,0};
static uint32_t dockVisit;
static uint8_t dockStopAck,dockReleaseDelay;
static uint16_t dockCancelAt;
static uint16_t dockClearAt;
static uint8_t dockClear,dockMode;
static SprayJob sprayJob;
static uint16_t session=42,sequence,requestAt,lastPoll,lastLinkByte,badFrames,uartErrors,rxDrops;
static uint8_t pending,linked,running,queued,peerFlags,peerResult,obstaclePaused;
static RlPacket pendingPacket;
static RlParser parser;
static int linkRx;
static std::string output;
static std::vector<uint8_t> transmitted;
static void print(const char* s) { output+=s; }
static void number(uint16_t n) { output+=std::to_string(n); }
static uint8_t takeLost(int*) { return 0; }
static int pop(int*) { return -1; }
static uint8_t put(uint8_t link,uint8_t b) { if(link) transmitted.push_back(b); else output+=char(b); return 1; }
#include "../../../MSP430/robot_supervisor/ultrasonic_hcsr04.h"
'''

tests = r'''
} // namespace msp
static unsigned checks=0;
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); std::abort(); } ++checks; } while(0)
static bool stopped() { return motors.left==0 && motors.right==0; }
static void reset(bool keepLineCalibration=false) {
    // Independent scenarios start with no line profile; flip settings survive.
    if(!keepLineCalibration) memset(EEPROM.values,0xff,EEPROM.length()-2);
    msp::dockVisit=msp::dockStopAck=msp::dockReleaseDelay=msp::dockCancelAt=0;
    msp::dockClearAt=msp::dockMode=msp::dockClear=0;
    msp::sprayJob={}; msp::P1OUT=0; msp::stopButton=msp::obstaclePaused=0;
    msp::tank={}; msp::ADC12IFG=msp::waterRaw=msp::waterAt=msp::lastWaterSample=0;
    msp::refill={msp::DEFAULT_REFILL_RAW,0,msp::REFILL_WATCH,0};
    fakeMillis=0; robot=ZumoControl(); parser={}; motors=ZumoMotors();
    reflectanceSensors=ZumoReflectanceSensorArray();
    Serial=FakeSerial(); button.pressed=button.released=false;
    mspSerial.input.clear(); mspSerial.output.clear(); mspSerial.overflowed=false;
    mspSerial.beforeWrite=nullptr; usbUsed=0; usbDiscard=false; suppressButtonRelease=false;
    timingButtonHold=false; flipAlarm=FlipAlarm();
    imuPresent=true; readFails=false; measuredZ=-15700; beeps=silences=0;
    usbReportPart=0;
    lastByte=lastReport=nextCalibration=calibrationStep=0;
    msp::ticks=msp::sequence=msp::requestAt=msp::lastPoll=msp::lastLinkByte=0;
    msp::pending=msp::linked=msp::running=msp::peerFlags=msp::peerResult=msp::P2IN=0;
    msp::session=42; msp::queued=RL_HELLO; msp::parser={};
    msp::output.clear(); msp::transmitted.clear();
    setup(); msp::sonarInit();
    CHECK(stopped() && !robot.moving());
}
static void sonar(unsigned cm) {
    msp::ticks=uint16_t(fakeMillis/100u);
    msp::sonarPhase=msp::SONAR_DONE; msp::sonarPulseValid=1;
    msp::sonarWidth=uint16_t((uint32_t(cm)*2097152ul+17150ul)/34300ul);
    msp::sonarSampleAt=msp::sonarLastTrigger=msp::ticks;
    msp::serviceObstacle();
}
static bool exchange() {
    msp::transmitted.clear(); msp::ticks=uint16_t(fakeMillis/100u);
    msp::serviceLink();
    if(msp::transmitted.empty()) { loop(); return false; }
    CHECK(msp::transmitted.size()==RL_SIZE);
    for(uint8_t b:msp::transmitted) mspSerial.input.push_back(b);
    mspSerial.output.clear(); loop();
    CHECK(mspSerial.output.size()==RL_SIZE);
    RlPacket reply={}; RlParser decoder={}; int decoded=0;
    for(uint8_t b:mspSerial.output) decoded=rlFeed(&decoder,b,&reply);
    CHECK(decoded==1); msp::response(&reply); return true;
}
static void step(uint32_t ms=20) { fakeMillis+=ms; sonar(40); msp::serviceWater(); exchange(); msp::serviceSpray(); }
static void stepWithoutEcho() {
    fakeMillis+=20; msp::ticks=uint16_t(fakeMillis/100u);
    msp::sonarPhase=msp::SONAR_DONE; msp::sonarPulseValid=0; msp::sonarWidth=0;
    msp::sonarSampleAt=msp::sonarLastTrigger=msp::ticks;
    msp::serviceObstacle(); exchange();
}
static void linkClear() {
    CHECK(exchange() && msp::linked && robot.session);
    sonar(40); fakeMillis+=100; sonar(40);
    CHECK(!msp::motionBlocked());
}
static void releaseButton() { button.released=true; loop(); }
static void calibrate() {
    releaseButton(); CHECK(robot.userRequest==RL_USER_ZUMO_CALIBRATE && stopped());
    for(unsigned i=0;i<40 && !robot.calibrating;++i) step();
    CHECK(robot.calibrating && msp::running && !robot.calibrated);
    CHECK(stopped()); // MSP grant begins the user's one-second wait.
    for(unsigned i=0;i<250 && robot.calibrating;++i) step();
    CHECK(!robot.calibrating && robot.calibrated && stopped());
    CHECK(reflectanceSensors.samples==80);
    for(unsigned i=0;i<30 && msp::running;++i) step();
    CHECK(!msp::running && msp::linked && !robot.following);
}
static void start() {
    releaseButton(); CHECK(robot.userRequest==RL_USER_START && stopped());
    for(unsigned i=0;i<40 && !robot.following;++i) step();
    CHECK(robot.following && msp::running);
    CHECK(motors.left==90 && motors.right==90);
}
static void waterSample(uint16_t raw) {
    msp::ADC12MEM0=raw; msp::ADC12IFG=msp::BIT0; msp::serviceWater();
}
static void secondWithWater(uint16_t raw) {
    for(unsigned i=0;i<50;++i) step();
    waterSample(raw);
}
int main(int argc,char** argv) {
    memset(EEPROM.values,0xff,EEPROM.length());
    reset(); linkClear(); reflectanceSensors.offset=125; calibrate();
    reset(true); linkClear();
    CHECK(robot.calibrated && robot.lastEvent==ZE_CAL_RESTORED && (msp::peerFlags&RL_CAL));
    for(int i=0;i<6;++i) {
        CHECK(reflectanceSensors.calibratedMinimumOn[i]==225u+i);
        CHECK(reflectanceSensors.calibratedMaximumOn[i]==1025u+2*i);
    }
    for(unsigned i=0;i<40;++i) step();
    CHECK(!robot.moving() && !msp::running && stopped()); start();
    // A power cut partway through the replacement EEPROM record leaves the
    // active selector pointing at the previous six ranges.
    EEPROM.update(LineCalibration::address(LineCalibration::slotB),0x42);
    reset(true); linkClear(); Serial.send("C\n"); loop();
    for(unsigned i=0;i<100 && calibrationStep<2;++i) step();
    CHECK(robot.calibrating && calibrationStep>=2);
    reset(true); linkClear();
    CHECK(robot.calibrated && reflectanceSensors.lows[0]==225);
    // A full replacement sweep writes the alternate slot and survives reboot.
    reflectanceSensors.offset=70; Serial.send("C\n"); loop();
    for(unsigned i=0;i<300 && robot.lastEvent!=ZE_CAL_DONE;++i) step();
    CHECK(robot.lastEvent==ZE_CAL_DONE); reset(true);
    CHECK(robot.calibrated && reflectanceSensors.lows[0]==170);
    // Bad contrast cannot overwrite a usable profile. Corruption requires a sweep.
    reflectanceSensors.badContrast=true; reflectanceSensors.calibrate();
    CHECK(!LineCalibration::save(reflectanceSensors)); reset(true);
    CHECK(robot.calibrated && reflectanceSensors.lows[0]==170);
    EEPROM.values[LineCalibration::address(EEPROM.read(0))]^=1;
    reset(true); linkClear(); CHECK(!robot.calibrated && stopped());
    releaseButton(); CHECK(robot.userRequest==RL_USER_ZUMO_CALIBRATE);

    reset(); linkClear(); calibrate();
    msp::queued=RL_CLEAR; CHECK(exchange() && !robot.calibrated && stopped());
    reset(true); CHECK(!robot.calibrated && stopped());
    reset(); linkClear(); calibrate(); start();
    waterSample(456); waterSample(499); exchange(); CHECK(robot.reversing);
    msp::netCommand("NET 101 DOCK 4294967295");
    CHECK(msp::queued==RL_STOP && !msp::dockStopAck && !msp::sprayJob.pump);
    msp::netCommand("NET 102 DEPART 4294967295"); CHECK(msp::queued==RL_STOP);
    for(unsigned i=0;i<40;++i) step();
    CHECK(stopped() && msp::dockVisit==4294967295u && msp::dockStopAck && msp::linked);
    msp::netCommand("NET 103 DEPART 4294967295"); CHECK(!msp::queued);
    waterSample(2104); waterSample(2104);
    msp::netCommand("NET 104 DEPART 1337"); CHECK(!msp::queued && stopped());
    msp::netCommand("NET 105 DOCK 4294967295"); CHECK(msp::dockStopAck && stopped());
    msp::netCommand("NET 106 DEPART 4294967295"); CHECK(msp::queued==RL_START);
    exchange(); CHECK(robot.following && !msp::dockVisit);
    msp::netCommand("NET 107 DEPART 4294967295"); CHECK(!msp::queued);

    waterSample(3); waterSample(3); exchange();
    msp::netCommand("NET 110 DOCK 77");
    for(unsigned i=0;i<40;++i) step();
    CHECK(msp::dockStopAck && stopped());
    msp::netCommand("NET 111 STOP"); exchange();
    waterSample(600); waterSample(600);
    msp::netCommand("NET 112 DEPART 77"); CHECK(msp::queued!=RL_START);
    for(unsigned i=0;i<60;++i) step();
    CHECK(!robot.moving() && !msp::dockStopAck);
    reset(); linkClear(); calibrate(); start();
    msp::netCommand("NET 20 APPROACH");
    waterSample(100); waterSample(100); exchange(); CHECK(robot.reversing);
    for(unsigned i=0;i<240;++i) {
        if(i%50==0) waterSample(100);
        step();
    }
    CHECK(!robot.moving() && !msp::dockClear && stopped());
    reset(); linkClear();
    for(unsigned i=0;i<120;++i) step(); // No conversion yet, even though WATER reports zero.
    CHECK(!msp::tank.empty && !robot.moving());
    waterSample(456); waterSample(499);
    CHECK(msp::tank.empty && !robot.moving() && !msp::queued);
    calibrate(); releaseButton();
    for(unsigned i=0;i<45;++i) step();
    CHECK(!msp::running && stopped());
    waterSample(501); waterSample(500); waterSample(501);
    CHECK(msp::tank.empty);
    waterSample(501); CHECK(!msp::tank.empty && stopped());
    for(unsigned i=0;i<5;++i) secondWithWater(2104);
    CHECK(robot.following && msp::running);
    waterSample(500); waterSample(500);
    CHECK(!msp::tank.empty && robot.following);
    waterSample(499); waterSample(500); waterSample(456); msp::serviceWater();
    CHECK(!msp::tank.empty && robot.following);
    waterSample(499); CHECK(msp::queued==RL_ZUMO_REVERSE);
    msp::netCommand("NET 1 TARGET"); CHECK(!msp::sprayJob.pump && msp::sprayJob.phase==msp::SJ_IDLE);
    CHECK(exchange() && robot.reversing && motors.left==-100 && motors.right==-100);
    CHECK(!msp::zumoFollowing() && (msp::peerFlags&RL_ZUMO_REVERSING));
    for(unsigned i=0;i<1500;++i) {
        if(i%50==0) waterSample(456);
        step();
        CHECK(msp::running && robot.reversing && motors.left==-100 && motors.right==-100);
    }
    waterSample(501); waterSample(500); waterSample(501);
    for(unsigned i=0;i<20;++i) step();
    CHECK(msp::tank.empty && robot.reversing);
    waterSample(501);
    for(unsigned i=0;i<220;++i) { step(); if(i%50==0) waterSample(2104); }
    CHECK(msp::running && msp::linked && motors.left==90 && motors.right==90);
    CHECK(!msp::tank.empty && robot.following && !robot.reversing);
    waterSample(14); waterSample(15); exchange();
    CHECK(robot.reversing);
    button.pressed=true; loop(); CHECK(stopped() && !robot.moving());
    waterSample(501); waterSample(501);
    for(unsigned i=0;i<70;++i) step();
    CHECK(!robot.moving() && !msp::running && stopped());

    reset(); linkClear(); calibrate(); start();
    waterSample(0); waterSample(0); exchange(); sonar(4); exchange();
    CHECK(stopped() && !robot.obstaclePaused && !robot.reversing);
    waterSample(501); waterSample(501);
    for(unsigned i=0;i<60;++i) step();
    CHECK(!robot.moving() && stopped());

    reset(); linkClear(); calibrate(); start();
    msp::netCommand("NET 1 TARGET"); exchange();
    for(unsigned i=0;i<100 && !msp::sprayJob.pump;++i) step();
    CHECK(msp::sprayJob.pump);
    waterSample(0); waterSample(0); exchange();
    CHECK(!msp::sprayJob.pump && !(msp::P1OUT&PUMP_GATE_MASK) && stopped());
    CHECK(msp::sprayJob.phase==msp::SJ_ABORTED);
    for(unsigned i=0;i<6;++i) secondWithWater(2104);
    CHECK(robot.following && !msp::sprayJob.pump);

    // Calibrated at boot, manually filled on the line, with no dock or Wi-Fi.
    reset(true); linkClear(); CHECK(robot.calibrated);
    for(unsigned i=0;i<5;++i) secondWithWater(2281);
    CHECK(stopped()); // An already full tank at boot is not a refill.
    secondWithWater(1343);
    for(unsigned i=0;i<4;++i) secondWithWater(2103);
    CHECK(stopped() && msp::refill.mode==msp::REFILL_WAIT);
    secondWithWater(2104); secondWithWater(2104); secondWithWater(2103);
    secondWithWater(2104); secondWithWater(2104); secondWithWater(2104);
    CHECK(stopped() && !msp::queued);
    secondWithWater(2104); step(); CHECK(robot.following);
    button.pressed=true; loop(); button.pressed=false;
    for(unsigned i=0;i<3;++i) secondWithWater(1343);
    for(unsigned i=0;i<6;++i) secondWithWater(2281);
    CHECK(stopped() && !robot.moving());

    // Recalibrating changes the boundary. An interrupted sample series cannot
    // authorise motion, and resetting calibration disables automatic restart.
    reset(true); linkClear();
    msp::netCommand("NET 7 RFMIN 901"); CHECK(msp::refill.minimum==901);
    msp::netCommand("NET 8 RFMIN 4097"); CHECK(msp::refill.minimum==901);
    secondWithWater(900); secondWithWater(901);
    for(unsigned i=0;i<200;++i) step();
    secondWithWater(901); secondWithWater(901); CHECK(stopped());
    msp::netCommand("NET 9 RFMIN 4096"); CHECK(msp::refill.minimum==4096);
    for(unsigned i=0;i<6;++i) secondWithWater(4095);
    CHECK(!robot.moving());

    reset(); linkClear(); calibrate(); start();
    sonar(4); msp::serviceLink(); CHECK(msp::pendingPacket.type==RL_ZUMO_PAUSE);
    waterSample(0); waterSample(0); CHECK(msp::queued==RL_STOP);
    waterSample(515); waterSample(515);
    for(unsigned i=0;i<60;++i) step();
    CHECK(stopped() && !msp::running && !msp::obstaclePaused);

    // A late retry cannot extend the reverse. A missing heartbeat stops the tracks.
    reset(); linkClear(); calibrate(); start(); waterSample(0); waterSample(0); exchange();
    CHECK(robot.reversing);
    uint32_t began=robot.lastReverseGrant;
    fakeMillis+=200; auto retry=robot.handle(msp::pendingPacket,fakeMillis);
    CHECK(retry.detail==RL_OK && robot.lastReverseGrant==began && robot.lastLease==began);
    fakeMillis=began+ZumoControl::LEASE_MS; loop();
    CHECK(stopped() && !robot.reversing && robot.reason==RL_LEASE_LOST);
    // Legacy MSP heartbeats can keep the link alive but cannot renew reverse.
    reset(); linkClear(); calibrate(); start(); waterSample(0); waterSample(0); exchange();
    RlPacket keep=msp::pendingPacket; keep.type=RL_KEEP;
    for(unsigned i=0;i<5;++i) {
        fakeMillis+=200; ++keep.seq; robot.handle(keep,fakeMillis); loop();
    }
    CHECK(stopped() && robot.lastEvent==ZE_REVERSE_DONE);
    // A healthy UART alone must not maintain reverse after the ADC stalls.
    reset(); linkClear(); calibrate(); start(); waterSample(0); waterSample(0); exchange();
    for(unsigned i=0;i<180;++i) step();
    CHECK(msp::tank.empty && !msp::running && stopped());
    waterSample(0); waterSample(0); step(); CHECK(!robot.moving());
    reset(); linkClear();
    auto samples=[](int16_t z,unsigned count) {
        measuredZ=z;
        for(unsigned i=0;i<count;++i) { fakeMillis+=40; loop(); }
    };
    // Reproduce the reported behavior with positive Z when the tracks are down.
    // A reboot on its side or upside down must never teach a new reference.
    EEPROM.update(EEPROM.length()-2,0xff); reset(); linkClear();
    samples(16000,20);
    CHECK(!flipAlarm.flipped && !beeps);
    measuredZ=16000; calibrate();
    CHECK(!flipAlarm.flipped && !beeps);
    samples(0,15); samples(16000,15);
    CHECK(!flipAlarm.flipped && !beeps);
    reset(); samples(-16000,15);
    CHECK(flipAlarm.flipped && beeps==1);
    samples(0,5); CHECK(!flipAlarm.flipped);
    samples(16000,15); CHECK(!flipAlarm.flipped && beeps==1);
    samples(-32768,12); CHECK(flipAlarm.flipped && beeps==2);
    // A sideways calibration cannot overwrite the previously learned sign.
    reset(); linkClear(); measuredZ=0; calibrate(); samples(-16000,12);
    CHECK(flipAlarm.flipped && beeps==1);
    // Neither unstable readings before the sweep nor steady readings once
    // the tracks move can replace the reference.
    reset(); linkClear(); releaseButton();
    for(unsigned i=0; i<40 && !robot.calibrating; ++i) step();
    CHECK(robot.calibrating);
    for(unsigned i=0; i<250 && robot.calibrating; ++i) {
        measuredZ = (calibrationStep > 0 || i % 12 < 6) ? -15700 : 16000;
        step();
    }
    CHECK(robot.calibrated && flipAlarm.uprightSign==1);
    // Relearn an opposite mounting while muted. Re-enabling after a reset
    // must use the new reference and preserve the existing mute preference.
    reset(); linkClear(); Serial.send("alarm off\n"); loop();
    measuredZ=-15700; calibrate(); reset(); linkClear();
    CHECK(flipAlarm.uprightSign==-1 && !flipAlarm.enabled);
    Serial.send("alarm on\n"); loop();
    const int16_t tracksDown=-15700, tracksUp=16384;
    samples(tracksDown,15); samples(0,15);
    samples(tracksUp,9); samples(tracksDown,1);
    CHECK(flipAlarm.enabled && flipAlarm.sensorReady && !flipAlarm.flipped && !beeps);
    samples(tracksUp,11); CHECK(flipAlarm.flipped && beeps==1);
    samples(tracksUp,19); CHECK(beeps==2);
    samples(7000,5); samples(tracksDown,3); CHECK(flipAlarm.flipped);
    samples(tracksDown,1); CHECK(!flipAlarm.flipped && silences==1);
    samples(tracksUp,11); CHECK(flipAlarm.flipped);
    button.pressed=true; loop(); samples(tracksUp,51);
    CHECK(!flipAlarm.enabled && !flipAlarm.flipped && silences==2);
    samples(tracksUp,55); button.pressed=false; releaseButton();
    CHECK(!flipAlarm.enabled && !robot.userRequest && stopped());
    reset(); samples(tracksUp,20); CHECK(!flipAlarm.enabled && !beeps);
    Serial.send("alarm on\n"); loop(); samples(tracksUp,11);
    CHECK(flipAlarm.flipped && beeps==1);
    readFails=true; samples(tracksUp,1); CHECK(!flipAlarm.sensorReady && !flipAlarm.flipped);
    imuPresent=false; readFails=false; samples(tracksUp,100); CHECK(beeps==1);
    imuPresent=true; samples(tracksDown,65); CHECK(flipAlarm.sensorReady && !flipAlarm.flipped);
    samples(tracksUp,11); Serial.send("alarm off\n"); loop();
    CHECK(!flipAlarm.enabled && !flipAlarm.flipped);
    button.pressed=true; loop(); samples(tracksDown,51); button.pressed=false; releaseButton();
    CHECK(flipAlarm.enabled && !robot.userRequest);
    reset(); CHECK(mspSerial.rx==6 && mspSerial.tx==13 && mspSerial.baud==9600);
    CHECK(Serial.baud==9600);
    // MSP session is still required, but missing sonar is no longer a veto.
    releaseButton(); CHECK(!robot.userRequest && stopped());
    CHECK(exchange()); releaseButton();
    CHECK(robot.userRequest==RL_USER_ZUMO_CALIBRATE);
    fakeMillis=300; CHECK(exchange() && msp::queued==RL_ZUMO_CALIBRATE);
    CHECK(exchange() && stopped() && robot.calibrating && msp::running);
    CHECK(!msp::obstacle.valid && msp::obstacle.fault && !msp::motionBlocked());
    // User's failing scenario: finish all 80 steps with no sonar echoes at all.
    for(unsigned i=0;i<250 && robot.calibrating;++i) stepWithoutEcho();
    CHECK(robot.calibrated && !robot.calibrating && reflectanceSensors.samples==80);
    for(unsigned i=0;i<30 && msp::running;++i) stepWithoutEcho();
    CHECK(!msp::running && stopped() && !msp::obstacle.valid);
    releaseButton();
    for(unsigned i=0;i<40 && !robot.following;++i) stepWithoutEcho();
    CHECK(robot.following && msp::running);
    for(unsigned i=0;i<100;++i) stepWithoutEcho();
    CHECK(robot.following && msp::running && msp::obstacle.fault && !msp::motionBlocked());
    // A real near echo still pauses; missing echoes cannot confirm clearance.
    sonar(2); CHECK(msp::queued==RL_ZUMO_PAUSE); exchange();
    CHECK(!robot.following && stopped());
    for(unsigned i=0;i<40;++i) stepWithoutEcho();
    CHECK(!msp::motionBlocked() && !robot.following && stopped());
    CHECK(msp::obstaclePaused && robot.obstaclePaused);

    reset(); linkClear(); calibrate(); start();
    reflectanceSensors.position=5000; loop();
    CHECK(motors.left==250 && motors.right==-400);
    reflectanceSensors.position=0; loop();
    CHECK(motors.left==-400 && motors.right==250);
    reflectanceSensors.position=2575; loop();
    CHECK(motors.left==165 && motors.right==15); // More outer-track drive at ordinary bends.
    reflectanceSensors.position=2500;
    // Near echo pauses the real sketch, whose motors stop before acknowledging.
    sonar(10); CHECK(msp::running && msp::queued!=RL_STOP);
    sonar(6); CHECK(msp::running && msp::queued!=RL_STOP);
    sonar(5); CHECK(!msp::running && msp::queued==RL_ZUMO_PAUSE);
    bool stopAck=false;
    const uint16_t pausedSession=robot.session;
    mspSerial.beforeWrite=[&]() { CHECK(stopped() && !robot.moving()); stopAck=true; };
    CHECK(exchange() && stopAck); mspSerial.beforeWrite=nullptr;
    CHECK(msp::obstaclePaused && robot.obstaclePaused && robot.calibrated);
    CHECK(robot.session==pausedSession && !robot.following);
    for(unsigned i=0;i<5;++i) { fakeMillis+=100; sonar(5); exchange(); }
    CHECK(stopped() && !msp::running && msp::obstaclePaused);
    fakeMillis+=100; sonar(7); exchange();
    CHECK(stopped() && msp::obstaclePaused);
    fakeMillis+=100; sonar(6); exchange();
    fakeMillis+=100; sonar(7); exchange();
    CHECK(stopped() && msp::obstaclePaused);
    fakeMillis+=100; sonar(7); CHECK(exchange());
    CHECK(robot.following && msp::running && !stopped());
    CHECK(!robot.obstaclePaused && !msp::obstaclePaused && robot.session==pausedSession);

    // Pressing Zumo STOP while paused cancels the session and consumes release.
    sonar(5); CHECK(exchange() && robot.obstaclePaused);
    button.pressed=true; loop(); CHECK(stopped() && !robot.session);
    button.pressed=false; releaseButton(); CHECK(!robot.userRequest);
    for(unsigned i=0;i<25;++i) step();
    CHECK(stopped() && !msp::running && !msp::obstaclePaused);
    start();

    // A manual MSP STOP also cancels the paused run.
    sonar(5); CHECK(exchange() && msp::obstaclePaused);
    CHECK(msp::netCommand("NET 10 STOP"));
    for(unsigned i=0;i<25;++i) step();
    CHECK(stopped() && !msp::running && !msp::obstaclePaused);
    start();

    // An older Uno's refused pause falls back to STOP and cannot grant resume.
    sonar(5); msp::serviceLink(); CHECK(msp::pendingPacket.type==RL_ZUMO_PAUSE);
    RlPacket refusal=msp::pendingPacket;
    refusal.type|=RL_REPLY; refusal.arg=RL_CAL|RL_FAULT; refusal.detail=RL_BAD_COMMAND;
    msp::response(&refusal); CHECK(msp::queued==RL_STOP);
    for(unsigned i=0;i<25;++i) step();
    CHECK(stopped() && !msp::running && !msp::obstaclePaused);
    start();

    // A lost pause frame also falls back to a session-independent STOP.
    sonar(5); msp::serviceLink(); CHECK(msp::pendingPacket.type==RL_ZUMO_PAUSE);
    CHECK(robot.following);
    fakeMillis+=200; CHECK(exchange() && stopped());
    for(unsigned i=0;i<25;++i) step();
    CHECK(!robot.following && !msp::obstaclePaused);
    start();

    // A STOP arriving during readLine wins before the new motor output.
    reflectanceSensors.onRead=[]() {
        RlPacket stop={RL_STOP,999,999,0,0}; uint8_t bytes[RL_SIZE]; rlEncode(&stop,bytes);
        for(uint8_t b:bytes) mspSerial.input.push_back(b);
    };
    loop(); CHECK(stopped() && !robot.moving());

    reset(); linkClear(); calibrate(); start();
    // Stale/no echo must not stop driving when the Uno link remains healthy.
    fakeMillis+=300; msp::ticks=uint16_t(fakeMillis/100u); msp::serviceObstacle();
    CHECK(!msp::motionBlocked() && msp::queued!=RL_STOP && msp::obstacle.fault);
    exchange();
    CHECK(robot.following && msp::running && !stopped());

    reset(); linkClear(); calibrate(); start();
    // No MSP messages: no dependence on STOP getting through a broken cable.
    fakeMillis=robot.lastLease+ZumoControl::LEASE_MS; loop();
    CHECK(!robot.moving() && stopped() && robot.reason==RL_LEASE_LOST);
    CHECK(robot.lastEvent==ZE_HEARTBEAT_LOST);
    fakeMillis+=2000; loop(); CHECK(stopped());

    reset(); linkClear(); calibrate(); start();
    button.pressed=true; loop(); CHECK(stopped() && suppressButtonRelease);
    button.pressed=false; button.released=true; loop();
    CHECK(!robot.userRequest && !robot.moving() && !suppressButtonRelease);

    reset(); linkClear(); calibrate(); start();
    Serial.send("s\n"); loop(); CHECK(stopped() && !robot.following);

    // Obstacle and communication loss can also interrupt the powered sweep.
    reset(); linkClear(); releaseButton();
    for(unsigned i=0;i<80 && !reflectanceSensors.samples;++i) step();
    CHECK(robot.calibrating && !stopped()); sonar(2); exchange();
    CHECK(stopped() && !robot.calibrated && !robot.calibrating);
    CHECK(robot.lastEvent==ZE_MSP_STOP && calibrationStep>0 && calibrationStep<80);
    for(unsigned i=0;i<40;++i) step();
    CHECK(!robot.moving() && stopped());
    // Reproduce the screenshot: HELLO has cleared REASON, but sweep is aborted.
    CHECK(robot.reason==RL_OK && !robot.calibrated && robot.lastEvent==ZE_MSP_STOP);
    Serial.output.clear(); usbReportPart=1; reportUsb(); reportUsb(); reportUsb();
    std::string statusText(Serial.output.begin(),Serial.output.end());
    CHECK(statusText.find("FW=OG9 CAL=0 SWEEP=0 RUN=0 REASON=0")!=std::string::npos);
    CHECK(statusText.find("FLIP ALARM=ON IMU=OK FLIPPED=0")!=std::string::npos);
    CHECK(statusText.find("LAST=MSP_STOP")!=std::string::npos && !usbReportPart);
    releaseButton();
    for(unsigned i=0;i<80 && !robot.calibrating;++i) step();
    CHECK(robot.calibrating);
    fakeMillis=robot.lastLease+ZumoControl::LEASE_MS; loop();
    CHECK(stopped() && !robot.calibrated && !robot.calibrating);

    reset(); linkClear(); reflectanceSensors.badContrast=true;
    releaseButton();
    for(unsigned i=0;i<300 && (!reflectanceSensors.samples || robot.calibrating);++i) step();
    // Original behavior: finishing the sweep is enough, regardless of added thresholds.
    CHECK(reflectanceSensors.samples==80 && robot.calibrated && stopped());
    CHECK(robot.reason==RL_OK);
    CHECK(robot.lastEvent==ZE_CAL_DONE);
    for(unsigned i=0;i<30 && msp::running;++i) step();
    CHECK(robot.calibrated && !msp::running && msp::linked);
    CHECK(robot.lastEvent==ZE_CAL_DONE);
    start();
    CHECK(reflectanceSensors.samples==80 && robot.following && !robot.calibrating);

    // Corruption, partial frames and overflow stop the actual sketch.
    for(unsigned kind=0;kind<3;++kind) {
        reset(); linkClear(); calibrate(); start();
        if(kind==0) {
            RlPacket keep={RL_KEEP,robot.session,uint16_t(robot.sequence+1),0,0};
            uint8_t bytes[RL_SIZE]; rlEncode(&keep,bytes); bytes[10]^=1;
            for(uint8_t b:bytes) mspSerial.input.push_back(b);
        } else if(kind==1) {
            mspSerial.input.push_back(0xa5); loop(); fakeMillis+=101;
        } else mspSerial.overflowed=true;
        loop(); CHECK(stopped() && !robot.moving() && robot.reason==RL_BAD_FRAME);
        CHECK(robot.lastEvent==ZE_UART_ERROR);
    }

    // Duplicate KEEP cannot renew a lease, even across millis rollover.
    ZumoControl c; c.calibrated=true;
    RlPacket p={RL_HELLO,7,0,0,0}; c.handle(p,0xfffffff0u);
    p={RL_START,7,1,0,0}; c.handle(p,0xfffffff0u);
    p={RL_KEEP,7,2,0,0}; c.handle(p,0xfffffff5u);
    c.handle(p,100); CHECK(c.lastLease==0xfffffff5u);
    c.tick(uint32_t(0xfffffff5u+1000u)); CHECK(!c.moving() && c.reason==RL_LEASE_LOST);
    CHECK(c.lastEvent==ZE_HEARTBEAT_LOST);
    p={RL_STOP,7,3,0,0}; c.handle(p,1000);
    p={RL_HELLO,8,0,0,0}; c.handle(p,1001);
    CHECK(c.reason==RL_OK && c.lastEvent==ZE_HEARTBEAT_LOST);

    // A fresh HELLO during a sweep is distinguished from an explicit STOP.
    p={RL_ZUMO_CALIBRATE,8,1,0,0}; c.handle(p,1002);
    p={RL_HELLO,9,0,0,0}; c.handle(p,1003);
    CHECK(!c.calibrated && !c.calibrating && c.lastEvent==ZE_MSP_RESYNC);
    p={RL_STOP,9,1,0,0}; c.handle(p,1004);
    CHECK(c.lastEvent==ZE_MSP_RESYNC);

    // Each diagnostic line must fit a real Uno's 63-byte serial TX space.
    robot.reason=robot.userRequest=255; calibrationStep=255;
    robot.lastEvent=ZE_HEARTBEAT_LOST; fakeMillis=0xffffffffu;
    Serial.output.clear(); usbReportPart=1; reportUsb(); reportUsb(); reportUsb();
    CHECK(!usbReportPart);
    statusText.assign(Serial.output.begin(),Serial.output.end());
    size_t lineStart=0;
    while(lineStart<statusText.size()) {
        size_t end=statusText.find('\n',lineStart); CHECK(end!=std::string::npos);
        CHECK(end-lineStart+1<=63); lineStart=end+1;
    }

    // Real target command -> STOP ACK -> settle -> bounded pump -> token-gated resume.
    reset(); linkClear(); calibrate(); start();
    CHECK(msp::netCommand("NET 123 TARGET"));
    CHECK(msp::sprayJob.phase==msp::SJ_STOPPING && !msp::sprayJob.pump);
    CHECK(exchange() && stopped());
    for(unsigned i=0;i<100 && msp::sprayJob.phase!=msp::SJ_SPRAYING;++i) {
        step(); CHECK(stopped());
    }
    CHECK(msp::sprayJob.pump && (msp::P1OUT&PUMP_GATE_MASK));
    CHECK((msp::P1OUT&((1u<<4)|msp::BIT6))==PUMP_GATE_MASK);
    for(unsigned i=0;i<200 && msp::sprayJob.phase==msp::SJ_SPRAYING;++i) {
        step(); CHECK(stopped());
    }
    CHECK(msp::sprayJob.phase==msp::SJ_RESUMING && !msp::sprayJob.pump && !(msp::P1OUT&PUMP_GATE_MASK));
    CHECK(msp::netCommand("NET 124 RESUME 999") && msp::queued!=RL_START);
    CHECK(msp::netCommand("NET 125 RESUME 123") && msp::queued==RL_START);
    CHECK(exchange()); loop();
    CHECK(msp::sprayJob.phase==msp::SJ_COMPLETE && robot.following);
    msp::netCommand("NET 126 TARGET");
    exchange();
    for(unsigned i=0;i<100 && msp::sprayJob.phase!=msp::SJ_SPRAYING;++i) step();
    CHECK(msp::sprayJob.pump);
    sonar(5); exchange();
    CHECK(stopped() && !msp::sprayJob.pump && msp::sprayJob.phase==msp::SJ_ABORTED);
    msp::netCommand("NET 127 RESUME 126");
    CHECK(msp::queued!=RL_START && !msp::sprayJob.pump);
    for(unsigned i=0;i<25;++i) step();
    CHECK(stopped() && !msp::obstaclePaused && !msp::sprayJob.pump);

    // Bridge accepts the preserved status prefix and new base identity.
    msp::output.clear(); msp::status();
    CHECK(msp::output.find("STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 ")==0);
    CHECK(msp::output.find("BASE=ZUMO LINE=BLACK")!=std::string::npos);
    CHECK(msp::output.find(" L2=")==std::string::npos);
    std::string telemetry=msp::output.substr(0,msp::output.size()-2);
    CHECK(direct::status(telemetry.c_str()));
    CHECK(argc==2);
    std::ofstream(argv[1])<<telemetry;
    printf("PASS %u Zumo sketch/MSP/sonar assertions; no hardware accessed.\n",checks);
}
'''
cpp = BUILD / "zumo_tests.cpp"
cpp.write_text(prefix + "".join(function(name, result) for name, result in (
    ("pumpOff", "void"), ("cancelSpray", "void"),
    ("zumoFollowing", "uint8_t"), ("zumoStopped", "uint8_t"),
    ("stopRequested", "void"), ("serviceObstacle", "void"), ("userRequest", "void"),
    ("reasonName", "const char *"), ("parseToken", "uint32_t"), ("printId", "void"), ("status", "void"), ("sendRequest", "void"),
    ("response", "void"), ("serviceLink", "void"),
    ("serviceWater", "void"), ("serviceSpray", "void"), ("netCommand", "uint8_t"),
)) + tests, encoding="utf-8")
exe = BUILD / "zumo_tests.exe"
telemetry_path = BUILD / "supervisor-status.txt"
for pin, definitions in (("P1.6", []), ("P1.4", ["-DPUMP_GATE_P14=1"])):
    subprocess.run([
        "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-Wno-unknown-pragmas", "-Wno-unused-function", "-Wno-unused-variable",
        *definitions, "-I" + str(BUILD), "-static", str(cpp), "-o", str(exe),
    ], check=True)
    subprocess.run([str(exe), str(telemetry_path)], check=True)
    print(f"PASS {pin} pump gate profile.")
# Feed the actual emitted MSP record through the dashboard's production parser.
# Only its pure parsing code is needed; no camera dependencies or ports are opened.
dashboard = ast.parse((ROOT / "Laptop/Dashboard/desk_bridge.py").read_text(encoding="utf-8-sig"))
parsing_nodes = [node for node in dashboard.body if
                 isinstance(node, ast.FunctionDef) and node.name == "parse_status" or
                 isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
                    target.id in {"STATUS_PATTERN", "ZUMO_STATUS_PATTERN"} for target in node.targets)]
namespace = {"re": re}
exec(compile(ast.Module(body=parsing_nodes, type_ignores=[]), "desk_bridge.py", "exec"), namespace)
value = namespace["parse_status"](telemetry_path.read_text())
assert value and value["base"] == "ZUMO" and value["left"] is None
print("PASS: actual MSP status accepted by ESP bridge and dashboard parser.")
