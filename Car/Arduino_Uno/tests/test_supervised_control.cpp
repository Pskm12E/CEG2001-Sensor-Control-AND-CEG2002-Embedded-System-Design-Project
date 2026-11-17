#include <cassert>
#include <cstdio>
#include <cstring>
#include "../msp_line_follow/control.h"
static unsigned checks=0;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static RlPacket req(uint8_t op,uint16_t seq,uint16_t session=42) { RlPacket p={op,session,seq,0,0}; return p; }
static void ready(RobotControl &r,uint32_t now=100) {
    r.handle(req(RL_HELLO,0),now);
    for(unsigned i=0;i<2;++i) { r.sensors[i].white=0; r.sensors[i].black=1; }
    r.tick(now,1,1); r.tick(now+10,1,1);
}
int main() {
    CHECK(rlCrc((const uint8_t*)"123456789",9)==0x29b1);
    RlPacket p=req(RL_START,123),out={}; uint8_t wire[RL_SIZE]; rlEncode(&p,wire);
    RlParser parser={};
    for(unsigned i=0;i<RL_SIZE;++i) CHECK(rlFeed(&parser,wire[i],&out)==(i==RL_SIZE-1?1:0));
    CHECK(out.type==p.type && out.seq==123 && out.session==42);
    wire[7]^=1;
    int result=0; for(unsigned i=0;i<RL_SIZE;++i) result=rlFeed(&parser,wire[i],&out);
    CHECK(result==-1);
    rlEncode(&p,wire);
    const uint8_t garbage[]={0,'P','I','N','G','\n',0xa5,0xa5,0x5a,99};
    for(uint8_t b:garbage) rlFeed(&parser,b,&out);
    bool found=false;
    for(uint8_t b:wire) if(rlFeed(&parser,b,&out)==1) found=true;
    CHECK(found && out.seq==123);
    for(unsigned byte=0;byte<RL_SIZE;++byte) for(unsigned bit=0;bit<8;++bit) {
        uint8_t damaged[RL_SIZE]; memcpy(damaged,wire,RL_SIZE); damaged[byte]^=(1u<<bit);
        RlParser s={}; bool accepted=false;
        for(uint8_t b:damaged) if(rlFeed(&s,b,&out)==1) accepted=true;
        CHECK(!accepted);
    }
    RobotControl r;
    CHECK(r.handle(req(RL_START,1),0).detail==RL_BAD_SESSION && !r.following);
    r.handle(req(RL_HELLO,0),0);
    CHECK(r.handle(req(RL_START,1),1).detail==RL_NOT_CAL && !r.following);
    r.handle(req(RL_WHITE,2),10);
    for(unsigned t=15;t<=210;t+=5) r.tick(t,0,0);
    CHECK(!r.calibration && r.sensors[0].white==0 && !r.calibrated());
    r.handle(req(RL_BLACK,3),220);
    for(unsigned t=225;t<=420;t+=5) r.tick(t,1,1);
    r.tick(430,1,1);
    CHECK(r.calibrated());
    CHECK(r.handle(req(RL_START,4),440).detail==RL_OK && r.following);
    r.tick(441,1,1); CHECK(r.action==DRIVE_FORWARD);
    uint32_t lease=r.lastLease;
    r.handle(req(RL_START,4),600); CHECK(r.lastLease==lease);
    r.handle(req(RL_KEEP,5),700); CHECK(r.lastLease==700);
    r.handle(req(RL_KEEP,5),900); CHECK(r.lastLease==700);
    r.tick(1699,1,1); CHECK(r.following);
    r.handle(req(RL_KEEP,6),1700); CHECK(!r.following && !r.session && r.action==DRIVE_STOP);
    CHECK(r.reason==RL_LEASE_LOST);
    r.handle(req(RL_START,7),1701); CHECK(!r.following);
    ready(r,2000);
    r.tick(2020,0,1); r.tick(2030,0,1);
    CHECK(r.handle(req(RL_START,1),2040).detail==RL_NOT_CENTER && !r.following);
    r.tick(2050,1,1); r.tick(2060,1,1); r.handle(req(RL_START,2),2070);
    r.tick(2080,1,0); CHECK(r.action==DRIVE_STOP); // filtered transition
    r.tick(2090,1,0); CHECK(r.action==DRIVE_LEFT);
    r.tick(2100,0,1); r.tick(2110,0,1); CHECK(r.action==DRIVE_RIGHT);
    r.tick(2120,0,0); r.tick(2130,0,0); CHECK(r.action==DRIVE_RIGHT);
    r.tick(2361,0,0); CHECK(!r.following && r.reason==RL_LINE_LOST);
    ready(r,3000); r.handle(req(RL_START,1),3010);
    r.stop(RL_LOCAL_STOP); r.handle(req(RL_KEEP,2),3020); CHECK(!r.following && !r.session);
    ready(r,4000); r.handle(req(RL_START,1),4010);
    CHECK(r.handle(req(RL_KEEP,3),4100).detail==RL_BAD_SEQUENCE && r.lastLease==4010);
    CHECK(r.handle(req(RL_KEEP,2,99),4200).detail==RL_BAD_SESSION && r.lastLease==4010);
    r.handle(req(RL_STOP,555,99),4300); CHECK(!r.following && !r.session);
    ready(r,5000); r.handle(req(RL_START,1),5010);
    RlPacket bad=req(RL_KEEP,2); bad.arg=1; r.handle(bad,5020); CHECK(!r.following && !r.session);
    ready(r,6000); r.handle(req(RL_START,1),6010);
    r.handle(req(RL_HELLO,0,55),6050); CHECK(!r.following && r.session==55);
    ready(r,7000); r.handle(req(RL_START,1),7010);
    for(uint32_t t=7020;t<7200;t+=5) r.tick(t,(t/5)&1,1);
    CHECK(!r.following && r.reason==RL_UNSTABLE);
    ready(r,8000); r.handle(req(RL_START,1),8010);
    r.tick(8020,1,0); r.tick(8030,1,0); r.handle(req(RL_KEEP,2),8500);
    r.tick(8780,1,0); CHECK(!r.following && r.reason==RL_TURN_TIMEOUT);
    ready(r,UINT32_MAX-300); r.handle(req(RL_START,1),UINT32_MAX-280);
    r.tick(718,1,1); CHECK(r.following);
    r.tick(719,1,1); CHECK(!r.following && r.reason==RL_LEASE_LOST);
    RobotControl same;
    same.handle(req(RL_HELLO,0),0); same.handle(req(RL_WHITE,1),0);
    for(unsigned t=5;t<=200;t+=5) same.tick(t,1,1);
    same.handle(req(RL_BLACK,2),210);
    for(unsigned t=215;t<=410;t+=5) same.tick(t,1,1);
    CHECK(!same.calibrated() && same.handle(req(RL_START,3),430).detail==RL_NOT_CAL);
    RobotControl white(true);
    CHECK(!white.requestLocal(RL_START)); // No local bypass before MSP session.
    white.handle(req(RL_HELLO,0),0);
    CHECK(white.requestLocal(RL_WHITE) && !white.following);
    CHECK(white.handle(req(RL_STATUS,1),1).detail==RL_USER_WHITE);
    CHECK(!white.requestLocal(RL_START)); // One request, no silent replacement.
    white.handle(req(RL_WHITE,2),2);
    for(unsigned t=7;t<=202;t+=5) white.tick(t,0,1);
    CHECK(!white.userRequest && !white.calibration && white.sensors[1].white==1);
    CHECK(white.requestLocal(RL_BLACK));
    CHECK(white.handle(req(RL_STATUS,3),210).detail==RL_USER_BLACK);
    white.handle(req(RL_BLACK,4),211);
    for(unsigned t=216;t<=411;t+=5) white.tick(t,1,0);
    CHECK(white.calibrated() && !white.following);
    white.tick(420,1,0); white.tick(430,1,0);
    CHECK(white.handle(req(RL_START,5),431).detail==RL_NOT_CENTER && !white.following);
    white.tick(440,0,1); white.tick(450,0,1);
    CHECK(white.requestLocal(RL_START));
    CHECK(white.handle(req(RL_STATUS,6),451).detail==RL_USER_START && !white.following);
    CHECK(white.handle(req(RL_START,7),452).detail==RL_OK && white.following);
    CHECK(!white.requestLocal(RL_WHITE));
    white.tick(460,0,1); CHECK(white.action==DRIVE_FORWARD);
    white.tick(470,1,1); white.tick(480,1,1); CHECK(white.action==DRIVE_RIGHT);
    white.tick(490,0,0); white.tick(500,0,0); CHECK(white.action==DRIVE_LEFT);
    white.tick(510,1,0); white.tick(520,1,0);
    CHECK(!white.following && white.reason==RL_BOTH_BLACK && white.action==DRIVE_STOP);
    white.tick(530,0,1); white.tick(540,0,1);
    CHECK(!white.following && !white.requestLocal(RL_START)); // Need MSP resync after stop.
    white.handle(req(RL_HELLO,0,51),550);
    CHECK(white.requestLocal(RL_START));
    white.handle(req(RL_STOP,77,99),551); // Obstacle STOP overrides pending local f.
    CHECK(!white.following && !white.userRequest && !white.session);
    white.handle(req(RL_HELLO,0,52),560);
    CHECK(!white.following && !white.userRequest); // Clear/recovered link never auto-restarts.
    RobotControl slow(BLACK_BETWEEN_SENSORS,3000);
    slow.handle(req(RL_HELLO,0),0);
    for(unsigned i=0;i<2;++i) { slow.sensors[i].white=0; slow.sensors[i].black=1; }
    slow.tick(0,0,0); slow.tick(10,0,0); slow.handle(req(RL_START,1),20);
    slow.tick(30,1,0); slow.tick(40,1,0);
    CHECK(slow.following && slow.action==DRIVE_LEFT);
    slow.handle(req(RL_KEEP,2),700); slow.tick(790,1,0);
    CHECK(slow.following && slow.action==DRIVE_LEFT); // Old 750ms cutoff passed.
    slow.handle(req(RL_KEEP,3),1400); slow.tick(1500,1,0);
    CHECK(slow.following && slow.action==DRIVE_LEFT);
    slow.handle(req(RL_KEEP,4),2100); slow.handle(req(RL_KEEP,5),2800);
    slow.tick(3039,1,0); CHECK(slow.following);
    slow.tick(3040,1,0); CHECK(!slow.following && slow.reason==RL_TURN_TIMEOUT);
    slow.tick(3050,0,0); slow.tick(3060,0,0);
    CHECK(!slow.following && slow.action==DRIVE_STOP); // Deadline stays latched.

    RobotControl lostLease(BLACK_BETWEEN_SENSORS,3000);
    lostLease.handle(req(RL_HELLO,0),0);
    for(unsigned i=0;i<2;++i) { lostLease.sensors[i].white=0; lostLease.sensors[i].black=1; }
    lostLease.tick(0,0,0); lostLease.tick(10,0,0); lostLease.handle(req(RL_START,1),20);
    lostLease.tick(30,1,0); lostLease.tick(40,1,0); lostLease.tick(1020,1,0);
    CHECK(!lostLease.following && lostLease.reason==RL_LEASE_LOST); // Still 1000ms.

    RobotControl interrupted(BLACK_BETWEEN_SENSORS,3000);
    interrupted.handle(req(RL_HELLO,0),0);
    for(unsigned i=0;i<2;++i) { interrupted.sensors[i].white=0; interrupted.sensors[i].black=1; }
    interrupted.tick(0,0,0); interrupted.tick(10,0,0); interrupted.handle(req(RL_START,1),20);
    interrupted.tick(30,1,0); interrupted.tick(40,1,0);
    interrupted.handle(req(RL_STOP,2),100); CHECK(!interrupted.following && interrupted.action==DRIVE_STOP);

    RobotControl recentred(BLACK_BETWEEN_SENSORS,3000);
    recentred.handle(req(RL_HELLO,0),0);
    for(unsigned i=0;i<2;++i) { recentred.sensors[i].white=0; recentred.sensors[i].black=1; }
    recentred.tick(0,0,0); recentred.tick(10,0,0); recentred.handle(req(RL_START,1),20);
    recentred.tick(30,1,0); recentred.tick(40,1,0);
    recentred.tick(500,0,0); recentred.tick(510,0,0);
    CHECK(recentred.following && recentred.action==DRIVE_FORWARD);
    printf("PASS %u assertions: framing, calibration, legacy layouts, active black-between layout, MSP-authorised requests, STOP and lease expiry.\n",checks);
}
