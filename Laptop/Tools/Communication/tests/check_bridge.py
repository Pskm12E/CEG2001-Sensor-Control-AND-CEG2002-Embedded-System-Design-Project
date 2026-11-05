"""Run actual wire codec, MSP dispatch and Pico transaction code with host I/O stubs.
Does not claim to test electrical wiring or MCU peripheral timing.
"""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
build=ROOT/'Laptop/Tools/Communication/build/bridge-tests'
build.mkdir(parents=True,exist_ok=True)
(build/'hardware').mkdir(exist_ok=True)
(build/'hardware/i2c.h').write_text(r'''
#pragma once
#include <cstdint>
#include <cstring>
#include "SupervisorBridge.h"
static int i2c0=0;
static const int GPIO_FUNC_I2C=3;
static unsigned writes=0,reads=0;
static int writeResult=MB_REQUEST_SIZE,readResult=MB_REPLY_SIZE;
static uint8_t lastRequest[MB_REQUEST_SIZE],nextReply[MB_REPLY_SIZE];
static uint32_t time_us_32() { return 100; }
static void i2c_init(int,int) {}
static void gpio_set_function(int,int) {}
static void gpio_pull_up(int) {}
static int i2c_write_timeout_us(int,int,const uint8_t *b,size_t,bool,unsigned) {
    ++writes; memcpy(lastRequest,b,MB_REQUEST_SIZE); return writeResult;
}
static int i2c_read_timeout_us(int,int,uint8_t *b,size_t,bool,unsigned) {
    ++reads; memcpy(b,nextReply,MB_REPLY_SIZE); return readResult;
}
''')
source=(ROOT/'Car/MSP430/robot_supervisor/supervisor_i2c.h').read_text()
def function(name):
    start=source.index('static void '+name+'(')
    brace=source.index('{',start); depth=1; end=brace+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}'); end+=1
    return source[start:end]+'\n'

prefix=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include "SupervisorBridge.h"
#include "msp_bridge.h"
static unsigned checks=0,stops=0;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static volatile uint8_t bridgeMailbox[MB_REQUEST_SIZE],bridgeReply[MB_REPLY_SIZE],bridgePending;
static volatile uint16_t bridgeRejected;
static uint16_t ticks=123,uartErrors=4,rxDrops=5,badFrames=6;
static uint8_t linked=1,running=1,peerFlags=8,peerResult=0,queued=0,pending=1;
static struct { uint8_t type=3; } pendingPacket;
static void __disable_interrupt() {}
static void __enable_interrupt() {}
static void stopRequested() { ++stops; running=0; queued=2; }
'''
tests=r'''
static void dispatch(const uint8_t *b) {
    for(unsigned i=0;i<MB_REQUEST_SIZE;++i) bridgeMailbox[i]=b[i];
    bridgePending=1; bridgeService();
}
static void responseForRequest() {
    memset(nextReply,0,MB_REPLY_SIZE); nextReply[0]=0xb7; nextReply[1]=1;
    nextReply[2]=lastRequest[2]; memcpy(nextReply+4,lastRequest+4,4);
    mbSeal(nextReply,MB_REPLY_SIZE);
}
int main() {
    CHECK(mbCrc((const uint8_t*)"123456789",9)==0x29b1);
    uint8_t req[MB_REQUEST_SIZE],copy[MB_REQUEST_SIZE];
    mbRequest(req,MB_STATUS,0xdeadbeefu);
    CHECK(mbRequestValid(req,sizeof(req)) && mbGet32(req+4)==0xdeadbeefu);
    for(unsigned bit=0;bit<MB_REQUEST_SIZE*8;++bit) {
        memcpy(copy,req,sizeof(req)); copy[bit/8]^=1u<<(bit%8);
        CHECK(!mbRequestValid(copy,sizeof(copy)));
    }
    CHECK(!mbRequestValid(req,0)); CHECK(!mbRequestValid(req,MB_REQUEST_SIZE-1));
    dispatch(req); CHECK(stops==0 && running && !bridgePending);
    uint8_t reply[MB_REPLY_SIZE];
    for(unsigned i=0;i<MB_REPLY_SIZE;++i) reply[i]=bridgeReply[i];
    CHECK(mbReplyValid(reply,sizeof(reply),MB_STATUS,0xdeadbeefu));
    CHECK(mbGet16(reply+8)==123 && reply[10]==1 && reply[11]==1 && reply[12]==8);
    CHECK(mbGet16(reply+16)==4 && mbGet16(reply+18)==5 && mbGet16(reply+20)==6);
    for(unsigned bit=0;bit<MB_REPLY_SIZE*8;++bit) {
        uint8_t corrupt[MB_REPLY_SIZE]; memcpy(corrupt,reply,sizeof(reply));
        corrupt[bit/8]^=1u<<(bit%8);
        CHECK(!mbReplyValid(corrupt,sizeof(corrupt),MB_STATUS,0xdeadbeefu));
    }
    CHECK(!mbReplyValid(reply,sizeof(reply),MB_STATUS,1));
    CHECK(!mbReplyValid(reply,sizeof(reply),MB_STOP,0xdeadbeefu));
    mbRequest(req,99,10); dispatch(req); CHECK(!stops && bridgeRejected==1);
    mbRequest(req,MB_STOP,0); dispatch(req); CHECK(!stops && bridgeRejected==2);
    mbRequest(req,MB_STOP,11); dispatch(req); CHECK(stops==1 && !running && queued==2);
    dispatch(req); CHECK(stops==2 && !running); // STOP remains harmless when repeated
    req[9]^=1; dispatch(req); CHECK(stops==2 && bridgeRejected==3);

    MspBridge bridge; bridge.init();
    CHECK(!strcmp(bridge.phase(),"NEVER") && bridge.lastWrite()==-99 && bridge.lastReadResult()==-99);
    CHECK(!strcmp(bridge.state(0),"NOT_CONNECTED"));
    bridge.start(MB_STATUS,0); CHECK(writes==1 && bridge.busy());
    responseForRequest(); nextReply[4]^=1; mbSeal(nextReply,MB_REPLY_SIZE);
    bridge.service(15); CHECK(bridge.busy() && bridge.takeResult()==0); // stale token
    CHECK(!strcmp(bridge.phase(),"VERIFY") && bridge.invalidReplies()==1 && bridge.lastReadResult()==MB_REPLY_SIZE);
    responseForRequest(); bridge.service(30);
    CHECK(!bridge.busy() && bridge.takeResult()==1 && !strcmp(bridge.state(30),"UP"));
    CHECK(!strcmp(bridge.phase(),"VERIFIED") && bridge.lastWrite()==MB_REQUEST_SIZE);
    CHECK(!strcmp(bridge.state(1530),"STALE"));
    writeResult=-1; bridge.start(MB_STATUS,40);
    CHECK(bridge.takeResult()==-1 && !bridge.busy() && !strcmp(bridge.state(40),"NOT_CONNECTED"));
    CHECK(!strcmp(bridge.phase(),"WRITE") && bridge.lastWrite()==-1 && bridge.lastReadResult()==-99 && bridge.invalidReplies()==0);
    bridge.start(MB_STOP,50); CHECK(bridge.takeResult()==-2); // outcome never falsely confirmed
    writeResult=MB_REQUEST_SIZE; bridge.start(MB_STOP,100);
    unsigned sent=writes; memset(nextReply,0,sizeof(nextReply));
    for(unsigned t=115;t<700;t+=15) bridge.service(t);
    bridge.service(700); CHECK(bridge.takeResult()==-2 && writes==sent && !bridge.busy());
    CHECK(!strcmp(bridge.phase(),"REPLY_DEADLINE"));
    bridge.start(MB_STATUS,UINT32_MAX-99); bridge.service(500);
    CHECK(bridge.takeResult()==-1 && !bridge.busy()); // timeout wrap
    bridge.start(MB_STOP,800); sent=writes; bridge.cancel(); bridge.service(2000);
    CHECK(!bridge.busy() && bridge.takeResult()==0 && writes==sent);
    bridge.start(MB_STATUS,2001); responseForRequest(); bridge.service(2016);
    CHECK(bridge.takeResult()==1); // next fresh request works
    readResult=-1; bridge.start(MB_STOP,3000); bridge.service(3015);
    CHECK(bridge.takeResult()==-2);
    CHECK(!strcmp(bridge.phase(),"READ") && bridge.lastReadResult()==-1);
    printf("PASS %u bridge assertions: CRC, correlation, MSP authority, stale data, timeouts and no replay.\n",checks);
}
'''
cpp=build/'bridge_tests.cpp'
cpp.write_text(prefix+function('bridgeService')+tests)
exe=build/'bridge_tests.exe'
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++17','-Wall','-Wextra','-Werror',
               '-Wno-unused-function','-static','-I'+str(build),
               '-I'+str(ROOT/'Laptop/Tools/Communication/libraries/RobotBench/src'),
               '-I'+str(ROOT/'Car/Archive/Pico_W/wireless_robot_link'),str(cpp),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
