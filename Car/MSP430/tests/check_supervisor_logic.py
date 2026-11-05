"""Exercise the actual supervisor command/response/scheduling functions on host.
UART I/O and registers are stubbed; live board tests cover their integration.
"""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[3]
source=(ROOT/'Car/MSP430/robot_supervisor/main.c').read_text()
def function(name):
    start=source.index('static void '+name+'(')
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
static uint16_t ticks,session=42,sequence,requestAt,lastPoll,lastLinkByte,badFrames;
static uint8_t pending,linked,running,queued,peerFlags,peerResult,P4OUT;
static const uint8_t BIT7=128;
static RlPacket pendingPacket;
static RlParser parser;
static int linkRx;
static char usbLine[32];
static uint8_t usbUsed;
static std::string output;
static uint8_t sent;
static void print(const char *s) { output+=s; }
static void number(uint16_t) {}
static void status() {}
static void help() {}
static const char *reasonName(uint8_t) { return "TEST_REASON"; }
static uint8_t takeLost(int*) { return 0; }
static int pop(int*) { return -1; }
static void sendRequest(uint8_t op) { sent=op; pending=1; pendingPacket.type=op; requestAt=lastPoll=ticks; }
'''
tests=r'''
static unsigned checks=0;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static void reset() {
    pending=linked=running=queued=peerFlags=peerResult=P4OUT=sent=0;
    parser.used=0; ticks=requestAt=lastPoll=lastLinkByte=0; output.clear();
    pendingPacket={RL_START,42,7,0,0};
}
static void user(const char *s) { strcpy(usbLine,s); usbUsed=strlen(s); command(); }
int main() {
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
    printf("PASS %u supervisor assertions: matching acknowledgements, STOP priority, refusal, heartbeat and timeout recovery.\n",checks);
}
'''
build=ROOT/'Car/MSP430'/'build'
build.mkdir(exist_ok=True)
cpp=build/'supervisor_logic_tests.cpp'
cpp.write_text(prefix+''.join(function(n) for n in ['stopRequested','command','response','serviceLink'])+tests)
exe=build/'supervisor_logic_tests.exe'
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++11','-Wall','-Wextra',
               '-Wno-unused-function','-Wno-unused-variable','-Werror','-static',str(cpp),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
