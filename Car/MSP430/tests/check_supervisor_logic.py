"""Exercise the actual supervisor command/response/scheduling functions on host.
UART I/O and registers are stubbed; live board tests cover their integration.
"""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[3]
source=(ROOT/'Car/MSP430/robot_supervisor/main.c').read_text()
def function(name,returns='void'):
    start=source.index('static '+returns+' '+name+'(')
    brace=source.index('{',start)
    depth=1; end=brace+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}'); end+=1
    return source[start:end]+'\n'
prefix=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include "../../Arduino_Uno/msp_line_follow/robot_link.h"
#include "../../Arduino_Uno/msp_line_follow/control.h"
#include "../robot_supervisor/obstacle_guard.h"
#define __disable_interrupt() ((void)0)
#define __enable_interrupt() ((void)0)
static uint16_t ticks,session=42,sequence,requestAt,lastPoll,lastLinkByte,badFrames;
static volatile uint16_t uartErrors,rxDrops,linkUartErrors,consoleUartErrors;
static volatile uint8_t lastLinkUartError,lastConsoleUartError;
static uint8_t pending,linked,running,queued,peerFlags,peerResult,P4OUT,obstacleBlocked;
static const uint8_t BIT7=128;
static RlPacket pendingPacket;
static RlParser parser;
typedef struct { volatile uint8_t data[128],head,tail,lost; } Ring;
static Ring usbRx,linkRx;
static char usbLine[32];
static uint8_t usbUsed,usbDiscard;
static std::string output;
static uint8_t sent;
static void print(const char *s) { output+=s; }
static void number(uint16_t) {}
static void status() {}
static void help() {}
static void sonarReport() {}
static void sonarService() {}
static uint8_t motionBlocked() { return obstacleBlocked; }
static const char *reasonName(uint8_t) { return "TEST_REASON"; }
static uint8_t tx[RL_SIZE],txUsed;
static uint8_t put(uint8_t link,uint8_t b) {
    if(link) { tx[txUsed++]=b; if(txUsed==RL_SIZE) { sent=tx[2]; txUsed=0; } }
    return 1;
}
'''
tests=r'''
static unsigned checks=0;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static void reset() {
    pending=linked=running=queued=peerFlags=peerResult=P4OUT=sent=obstacleBlocked=txUsed=0;
    parser.used=0; ticks=requestAt=lastPoll=lastLinkByte=0; output.clear();
    session=42; sequence=0;
    memset(&usbRx,0,sizeof(usbRx)); memset(&linkRx,0,sizeof(linkRx));
    uartErrors=rxDrops=linkUartErrors=consoleUartErrors=0;
    lastLinkUartError=lastConsoleUartError=usbUsed=usbDiscard=0;
    pendingPacket={RL_START,42,7,0,0};
}
static void user(const char *s) { strcpy(usbLine,s); usbUsed=strlen(s); command(); }
static void exchange(RobotControl &robot,uint32_t now) {
    serviceLink(); CHECK(pending);
    RlParser decode={}; RlPacket packet={};
    for(uint8_t b:tx) rlFeed(&decode,b,&packet);
    RlPacket reply=robot.handle(packet,now); response(&reply);
}
int main() {
    // A corrupt Uno byte is rejected, identified by port, and still stops.
    reset(); linked=running=1;
    receive(&linkRx,0xa5,0x44); // UCRXERR + framing error.
    CHECK(uartErrors==1 && linkUartErrors==1 && consoleUartErrors==0);
    CHECK(lastLinkUartError==0x44 && !lastConsoleUartError);
    CHECK(linkRx.head==0 && linkRx.lost);
    serviceLink(); CHECK(!running && !linked && sent==RL_STOP);
    CHECK(output.find("UART0 UNO RX ERROR/OVERFLOW")!=std::string::npos);
    pending=queued=sent=0; serviceLink(); CHECK(!running && !sent);
    // A console/ESP receive failure has a distinct counter and also stops.
    reset(); linked=running=1;
    receive(&usbRx,'F',0x24); // UCRXERR + overrun error.
    CHECK(uartErrors==1 && !linkUartErrors && consoleUartErrors==1);
    CHECK(!lastLinkUartError && lastConsoleUartError==0x24);
    CHECK(usbRx.head==0 && usbRx.lost);
    readUsb(); CHECK(!running && queued==RL_STOP && usbDiscard);
    CHECK(output.find("UART1 CONSOLE RX ERROR/OVERFLOW")!=std::string::npos);
    serviceLink(); CHECK(sent==RL_STOP && !running);
    // Ring overflow remains separate from hardware UART receive failures.
    reset(); linked=running=1;
    for(unsigned i=0;i<128;++i) receive(&linkRx,0,0);
    CHECK(rxDrops==1 && !uartErrors && !linkUartErrors && !consoleUartErrors);
    CHECK(linkRx.lost); serviceLink(); CHECK(!running && sent==RL_STOP);
    reset(); receive(&linkRx,42,0); receive(&usbRx,43,0);
    CHECK(pop(&linkRx)==42 && pop(&usbRx)==43 && !uartErrors && !rxDrops);
    reset(); user("F"); CHECK(!queued && !running);
    linked=1; user("F"); CHECK(queued==RL_START && !running);
    user("S"); CHECK(queued==RL_STOP && !running);
    user("F"); CHECK(queued==RL_STOP && !running);
    reset(); pending=linked=1;
    RlPacket r={RL_START|RL_REPLY,99,7,RL_MOVING,RL_OK};
    response(&r); CHECK(pending && !running);
    r.session=42; r.seq=6; response(&r); CHECK(pending && !running);
    r.seq=7; r.type=RL_KEEP|RL_REPLY; response(&r); CHECK(pending && !running);
    r.type=RL_START|RL_REPLY; response(&r); CHECK(!pending && running && P4OUT==BIT7);
    user("F"); CHECK(!queued && running);
    pending=1; pendingPacket.type=RL_KEEP;
    r.type=RL_KEEP|RL_REPLY; r.arg=0; response(&r);
    CHECK(!running && queued==RL_STOP && !linked);
    reset(); pending=linked=1; queued=RL_STOP;
    r={RL_START|RL_REPLY,42,7,RL_MOVING,RL_OK}; response(&r);
    CHECK(!running && queued==RL_STOP);
    reset(); pending=linked=1;
    r={RL_START|RL_REPLY,42,7,0,RL_NOT_CAL}; response(&r); CHECK(!running && !pending);
    reset(); pending=1; pendingPacket.type=RL_HELLO;
    r={RL_HELLO|RL_REPLY,42,7,RL_CAL,RL_OK}; response(&r); CHECK(linked && !running);
    reset(); pending=running=linked=1; pendingPacket.type=RL_STOP;
    r={RL_STOP|RL_REPLY,42,7,RL_CAL,RL_OK}; response(&r);
    CHECK(!running && !linked && queued==RL_HELLO);
    reset(); linked=running=1; lastPoll=100; ticks=101;
    serviceLink(); CHECK(!sent);
    ticks=102; serviceLink(); CHECK(sent==RL_KEEP);
    ticks=106; sent=0; serviceLink(); CHECK(!sent && running);
    ticks=107; serviceLink(); CHECK(sent==RL_STOP && !running && !linked);
    ticks=112; sent=0; serviceLink(); CHECK(sent==RL_HELLO && !running);
    reset(); pending=linked=running=1; pendingPacket.type=RL_START;
    requestAt=65533; ticks=2; serviceLink(); CHECK(sent==RL_STOP && !running);
    reset(); linked=running=1; user("W"); CHECK(!running && queued==RL_WHITE);
    reset(); linked=running=1; user("FORWARD"); CHECK(!queued); // no accidental alias
    reset(); linked=1; obstacleBlocked=1; user("F"); CHECK(queued==RL_STOP && !running);
    reset(); obstacleBlocked=1; sendRequest(RL_START); CHECK(!sent && queued==RL_STOP && !pending);
    reset(); linked=pending=1; obstacleBlocked=1;
    r={RL_START|RL_REPLY,42,7,RL_MOVING,RL_OK}; response(&r); CHECK(!running);
    reset(); linked=pending=1; pendingPacket.type=RL_STATUS;
    r={RL_STATUS|RL_REPLY,42,7,RL_CAL,RL_USER_START}; response(&r); CHECK(queued==RL_START && !running);
    reset(); linked=pending=1; obstacleBlocked=1; pendingPacket.type=RL_STATUS;
    r={RL_STATUS|RL_REPLY,42,7,RL_CAL,RL_USER_START}; response(&r); CHECK(queued==RL_STOP && !running);
    reset(); linked=pending=1; obstacleBlocked=1; pendingPacket.type=RL_STATUS;
    r={RL_STATUS|RL_REPLY,42,7,0,RL_USER_WHITE}; response(&r); CHECK(queued==RL_WHITE);
    reset(); linked=1; queued=RL_STOP; userRequest(RL_USER_START); CHECK(queued==RL_STOP);
    reset(); linked=pending=1; queued=RL_STOP; pendingPacket.type=RL_STATUS;
    ticks=0; serviceLink(); CHECK(!sent && pending);
    ticks=1; serviceLink(); CHECK(sent==RL_STOP && pending);
    reset(); linked=pending=1; pendingPacket.type=RL_STATUS; r={RL_STATUS|RL_REPLY,42,7,0,RL_USER_START};
    response(&r); CHECK(queued==RL_START);
    obstacleBlocked=1; serviceLink(); CHECK(!running && queued==RL_STOP && sent==0);
    reset(); linked=running=1; peerFlags=RL_MOVING; obstacleBlocked=1;
    serviceObstacle(); CHECK(!running && queued==RL_STOP);
    serviceLink(); CHECK(sent==RL_STOP);
    pending=0; queued=0; peerFlags=0; obstacleBlocked=0; sent=0;
    serviceObstacle(); CHECK(!running && !queued && !sent); // Clear path never auto-starts.
    // Full software path: local request -> MSP grant -> near echo -> framed STOP -> Uno.
    reset(); ObstacleGuard guard; obstacleInit(&guard); obstacleBlocked=guard.inhibit;
    RobotControl robot(WHITE_LANE,3000,false); queued=RL_HELLO; exchange(robot,0);
    CHECK(linked && robot.session && !running && !robot.following);
    CHECK(robot.requestLocal(RL_WHITE)); ticks=3; exchange(robot,300); CHECK(queued==RL_WHITE);
    exchange(robot,301);
    for(unsigned t=306;t<=501;t+=5) robot.tick(t,0,1);
    CHECK(!robot.calibration && !robot.userRequest);
    CHECK(robot.requestLocal(RL_BLACK)); ticks=6; exchange(robot,600); CHECK(queued==RL_BLACK);
    exchange(robot,601);
    for(unsigned t=606;t<=801;t+=5) robot.tick(t,1,0);
    robot.tick(810,0,1); robot.tick(820,0,1); CHECK(robot.calibrated());
    ticks=9; obstacleSample(&guard,ticks,50,1); CHECK(!guard.inhibit);
    ticks=10; obstacleSample(&guard,ticks,50,1); obstacleBlocked=guard.inhibit; CHECK(!motionBlocked());
    CHECK(robot.requestLocal(RL_START)); exchange(robot,1000); CHECK(queued==RL_START);
    exchange(robot,1001); CHECK(running && robot.following);
    robot.tick(1002,0,1); CHECK(robot.action==DRIVE_FORWARD);
    ticks=11; obstacleSample(&guard,ticks,2,1); obstacleBlocked=guard.inhibit;
    serviceObstacle(); CHECK(queued==RL_STOP && !running);
    exchange(robot,1100); CHECK(!robot.following && robot.action==DRIVE_STOP && !robot.userRequest);
    ticks=12; obstacleSample(&guard,ticks,50,1); obstacleBlocked=guard.inhibit;
    exchange(robot,1200); CHECK(linked && !robot.following);
    ticks=13; obstacleSample(&guard,ticks,50,1); obstacleBlocked=guard.inhibit;
    serviceObstacle(); CHECK(!motionBlocked() && !running && !robot.following && !queued);
    CHECK(robot.requestLocal(RL_START));
    ticks=15; obstacleSample(&guard,ticks,50,1); obstacleBlocked=guard.inhibit;
    exchange(robot,1500); exchange(robot,1501); CHECK(running && robot.following);
    ticks=18; obstacleAge(&guard,ticks); obstacleBlocked=guard.inhibit;
    serviceObstacle(); exchange(robot,1800);
    CHECK(guard.fault && !guard.inhibit && running && robot.following);
    printf("PASS %u supervisor assertions: matching acknowledgements, STOP priority, refusal, heartbeat and timeout recovery.\n",checks);
}
'''
build=ROOT/'Car/MSP430'/'build'
build.mkdir(exist_ok=True)
cpp=build/'supervisor_logic_tests.cpp'
cpp.write_text(prefix+function('receive')+function('pop','int')+function('takeLost','uint8_t')+
               ''.join(function(n) for n in ['stopRequested','serviceObstacle','userRequest','command','readUsb','sendRequest','response','serviceLink'])+tests)
exe=build/'supervisor_logic_tests.exe'
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++11','-Wall','-Wextra',
               '-Wno-unused-function','-Wno-unused-variable','-Werror','-static',str(cpp),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
