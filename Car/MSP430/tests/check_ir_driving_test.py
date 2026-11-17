"""Exercise both real sonar policies through the actual supervisor/Uno path.

Host registers and UART transport are fake; sonar processing, supervisor command
functions, framing and the digital white-lane controller are production code.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / "Car/MSP430/robot_supervisor/main.c").read_text()


def function(name):
    start = source.index("static void " + name + "(")
    brace = source.index("{", start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


prefix = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#define __interrupt
#define __disable_interrupt() ((void)0)
#define __enable_interrupt() ((void)0)
#define __bic_SR_register_on_exit(x) ((void)(x))
enum { BIT2=4,BIT7=128,TASSEL__SMCLK=512,MC__CONTINUOUS=32,TACLR=4,CCIE=16,LPM0_bits=16 };
static uint8_t P3SEL,P3REN,P3OUT,P3DIR,P2SEL,P2DIR,P2OUT,P2REN,P2IE,P2IES,P2IFG,P2IN;
static uint16_t TA2CCTL0,TA2CTL,TA2CCR0,TA2R,ticks;
static std::string output;
static void print(const char* text) { output+=text; }
static void number(uint16_t value) { output+=std::to_string(value); }
#include "../robot_supervisor/ultrasonic_hcsr04.h"
#include "../../Arduino_Uno/msp_line_follow/control.h"
static uint16_t session=42,sequence,requestAt,lastPoll,lastLinkByte,badFrames;
static uint8_t pending,linked,running,queued,peerFlags,peerResult,P4OUT;
static RlPacket pendingPacket;
static RlParser parser;
static int linkRx;
static const char* reasonName(uint8_t) { return "TEST_REASON"; }
static uint8_t takeLost(int*) { return 0; }
static int pop(int*) { return -1; }
static uint8_t tx[RL_SIZE],txUsed;
static uint8_t put(uint8_t link,uint8_t byte) {
    if(link) { tx[txUsed++]=byte; if(txUsed==RL_SIZE) txUsed=0; }
    return 1;
}
#if defined(IR_DRIVING_TEST) && IR_DRIVING_TEST
static const bool testBuild=true;
#else
static const bool testBuild=false;
#endif
'''

tests = r'''
static unsigned checks=0;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static void reset() {
    pending=linked=running=queued=peerFlags=peerResult=P4OUT=txUsed=0;
    parser.used=0; ticks=requestAt=lastPoll=lastLinkByte=badFrames=0;
    session=42; sequence=0; output.clear(); P2IN=0; TA2R=0;
    sonarInit();
}
static void exchange(RobotControl& robot,uint32_t now) {
    serviceLink(); CHECK(pending);
    RlParser decode={}; RlPacket packet={}; int result=0;
    for(uint8_t byte:tx) result=rlFeed(&decode,byte,&packet);
    CHECK(result==1);
    RlPacket reply=robot.handle(packet,now); response(&reply);
}
static void calibrate(RobotControl& robot) {
    queued=RL_HELLO; exchange(robot,0);
    CHECK(linked && robot.session && !running && !robot.following);
    CHECK(robot.requestLocal(RL_WHITE)); ticks=3; exchange(robot,300);
    CHECK(queued==RL_WHITE); exchange(robot,301);
    for(unsigned t=306;t<=501;t+=5) {
        robot.tick(t,0,1); CHECK(!robot.following && robot.action==DRIVE_STOP);
    }
    CHECK(robot.requestLocal(RL_BLACK)); ticks=6; exchange(robot,600);
    CHECK(queued==RL_BLACK); exchange(robot,601);
    for(unsigned t=606;t<=801;t+=5) {
        robot.tick(t,1,0); CHECK(!robot.following && robot.action==DRIVE_STOP);
    }
    robot.tick(810,0,1); robot.tick(820,0,1);
    CHECK(robot.calibrated());
    CHECK(robot.sensors[0].white==0 && robot.sensors[0].black==1);
    CHECK(robot.sensors[1].white==1 && robot.sensors[1].black==0);
    ticks=9;
}
static void echo(uint16_t cm) {
    // Feed a completed ISR sample to the real service adapter, preserving its
    // interrupt timestamp rather than assigning fresh validity in a mock.
    sonarPhase=SONAR_DONE; sonarPulseValid=1; sonarSampleAt=ticks;
    sonarWidth=uint16_t((uint32_t(cm)*2097152ul+17150ul)/34300ul);
    sonarLastTrigger=ticks;
    serviceObstacle();
    CHECK(obstacle.valid && obstacle.cm==cm && !obstacle.fault);
}
static void clearSonar() {
    echo(40); ++ticks; echo(40);
    CHECK(!obstacle.inhibit && !motionBlocked());
}
static void sensorState(unsigned kind) {
    if(kind==0) {
        sonarLastTrigger=ticks; serviceObstacle();
        CHECK(!obstacle.valid && obstacle.fault && !obstacle.inhibit);
    } else if(kind==1) {
        echo(2); CHECK(obstacle.inhibit && !obstacle.fault);
    } else if(kind==2) {
        clearSonar(); ticks+=3; sonarLastTrigger=ticks; serviceObstacle();
        CHECK(!obstacle.valid && obstacle.fault && !obstacle.inhibit);
    } else clearSonar();
    CHECK(bool(motionBlocked())==(!testBuild && kind==1));
    output.clear(); sonarReport();
    if(testBuild) CHECK(output.find(" ULTRASONIC_INTERLOCK=OFF")!=std::string::npos);
    else CHECK(output.find("ULTRASONIC_INTERLOCK=")==std::string::npos);
    if(kind==0 || kind==2)
        CHECK(output.find("SONAR VALID=0 CM=UNKNOWN INHIBIT=0 FAULT=1")!=std::string::npos);
    else if(kind==1)
        CHECK(output.find("SONAR VALID=1 CM=2 INHIBIT=1 FAULT=0")!=std::string::npos);
    else CHECK(output.find("SONAR VALID=1 CM=40 INHIBIT=0 FAULT=0")!=std::string::npos);
}
static uint32_t askStart(RobotControl& robot,bool allowed) {
    CHECK(robot.requestLocal(RL_START)); ticks+=3;
    const uint32_t now=uint32_t(ticks)*100u;
    exchange(robot,now);
    CHECK(!running && !robot.following);
    CHECK(queued==(allowed?RL_START:RL_STOP));
    exchange(robot,now+1);
    CHECK(bool(running)==allowed && robot.following==allowed);
    CHECK(robot.action==(allowed?DRIVE_FORWARD:DRIVE_STOP));
    return now+1;
}
int main() {
    for(unsigned kind=0;kind<4;++kind) {
        reset(); RobotControl robot(WHITE_LANE,3000,false);
        CHECK(!robot.following && robot.action==DRIVE_STOP && !running && !queued);
        CHECK(!obstacle.inhibit && !obstacle.valid && obstacle.fault);
        CHECK(!motionBlocked());
        serviceObstacle(); CHECK(!running && !queued && !robot.following);
        calibrate(robot); sensorState(kind);
        CHECK(!running && !queued && !robot.following); // Sonar never starts driving.
        const bool allowed=testBuild || kind!=1;
        uint32_t started=askStart(robot,allowed);
        if(allowed) {
            sensorState(kind);
            CHECK(running && !queued && robot.following); // Actual obstacle service preserves authorised test driving.
            started=uint32_t(ticks)*100u+1u;
            robot.tick(started+10,1,1); robot.tick(started+20,1,1);
            CHECK(robot.action==DRIVE_RIGHT); // Left black -> avoid the left border.
            stopRequested();
            CHECK(!running && queued==RL_STOP);
            exchange(robot,started+30);
            CHECK(!robot.following && robot.action==DRIVE_STOP && !robot.userRequest);
        }
        CHECK(queued==RL_HELLO); exchange(robot,started+31);
        robot.tick(started+40,0,1); robot.tick(started+50,0,1);
        clearSonar();
        CHECK(linked && !running && !queued && !robot.following);
        ticks+=3; exchange(robot,uint32_t(ticks)*100u);
        CHECK(!running && !queued && !robot.following); // Clear sonar cannot restart.

        // A fresh explicit request is still required after a stop. Thereafter,
        // losing the MSP heartbeat stops the Uno in BOTH build configurations.
        const uint32_t restarted=askStart(robot,true);
        robot.tick(restarted+999,0,1); CHECK(robot.following);
        robot.tick(restarted+1000,0,1);
        CHECK(!robot.following && robot.action==DRIVE_STOP && robot.reason==RL_LEASE_LOST);
        ticks+=10; exchange(robot,restarted+1001);
        CHECK(!running && queued==RL_STOP && !robot.following);
    }

    // Bypassing the sonar gate never bypasses the Uno's calibration or position checks.
    reset(); RobotControl uncalibrated(WHITE_LANE,3000,false);
    queued=RL_HELLO; exchange(uncalibrated,0); ticks=9; clearSonar();
    CHECK(uncalibrated.requestLocal(RL_START)); ticks+=3;
    uint32_t now=uint32_t(ticks)*100u;
    exchange(uncalibrated,now); CHECK(queued==RL_START); exchange(uncalibrated,now+1);
    CHECK(!running && !uncalibrated.following && peerResult==RL_NOT_CAL);

    reset(); RobotControl offCentre(WHITE_LANE,3000,false); calibrate(offCentre);
    clearSonar(); offCentre.tick(1200,1,1); offCentre.tick(1210,1,1);
    CHECK(offCentre.requestLocal(RL_START)); ticks+=3; now=uint32_t(ticks)*100u;
    exchange(offCentre,now); CHECK(queued==RL_START); exchange(offCentre,now+1);
    CHECK(!running && !offCentre.following && peerResult==RL_NOT_CENTER);

    // One authorised start must sustain forward travel across many lease periods.
    // Exercise the real MSP scheduler and framed replies, not injected KEEP calls.
    reset(); RobotControl continuous(WHITE_LANE,3000,false); calibrate(continuous);
    sensorState(testBuild?0:3);
    const uint32_t continuousStart=askStart(continuous,true);
    uint16_t lastSonarTick=uint16_t(ticks-1u);
    unsigned keepCount=0;
    for(uint32_t elapsed=0;elapsed<=12000;elapsed+=10) {
        const uint32_t current=continuousStart+elapsed;
        ticks=uint16_t(current/100u);
        if(ticks!=lastSonarTick) {
            lastSonarTick=ticks;
            if(testBuild) {
                sonarPhase=SONAR_DONE; sonarPulseValid=0; sonarWidth=0;
                sonarSampleAt=sonarLastTrigger=ticks;
                serviceObstacle();
                CHECK(!obstacle.valid && !obstacle.inhibit && obstacle.fault);
            } else echo(40);
        } else serviceObstacle();
        continuous.tick(current,0,1);
        serviceLink();
        if(pending) {
            CHECK(pendingPacket.type==RL_KEEP);
            exchange(continuous,current);
            ++keepCount;
            CHECK(continuous.lastLease==current);
        }
        CHECK(running && linked && !queued && continuous.following);
        CHECK(continuous.action==DRIVE_FORWARD);
    }
    CHECK(keepCount==60); // 12 seconds at the actual 200ms supervisor cadence.
    CHECK(continuous.lastLease==continuousStart+12000);
    const uint32_t finalKeep=continuous.lastLease;
    continuous.tick(finalKeep+999,0,1);
    CHECK(continuous.following && continuous.action==DRIVE_FORWARD);
    continuous.tick(finalKeep+1000,0,1);
    CHECK(!continuous.following && continuous.action==DRIVE_STOP && continuous.reason==RL_LEASE_LOST);
    ticks=uint16_t((finalKeep+1001)/100u);
    exchange(continuous,finalKeep+1001);
    CHECK(!running && queued==RL_STOP && !continuous.following);
    exchange(continuous,finalKeep+1002);
    CHECK(!continuous.following && continuous.action==DRIVE_STOP && continuous.calibrated());
    std::printf("PASS %u %s sonar-policy/supervisor/white-lane/STOP/lease assertions.\n",
                checks,testBuild?"IR-driving-test":"normal");
}
'''

build = ROOT / "Car/MSP430/build"
build.mkdir(exist_ok=True)
cpp = build / "ir_driving_test.cpp"
cpp.write_text(prefix + "".join(function(name) for name in (
    "stopRequested", "serviceObstacle", "userRequest", "sendRequest", "response", "serviceLink"
)) + tests, encoding="utf-8")
for name, flags in (("default", []), ("explicit_zero", ["-DIR_DRIVING_TEST=0"]),
                    ("enabled", ["-DIR_DRIVING_TEST=1"])):
    exe = build / ("ir_driving_test_" + name + ".exe")
    subprocess.run([
        "C:/msys64/ucrt64/bin/g++.exe", "-std=c++11", "-Wall", "-Wextra", "-Werror",
        "-Wno-unknown-pragmas", "-Wno-unused-function", "-static", *flags, str(cpp), "-o", str(exe)
    ], check=True)
    subprocess.run([str(exe)], check=True)
