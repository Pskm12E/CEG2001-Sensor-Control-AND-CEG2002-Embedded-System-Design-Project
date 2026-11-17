#include <cassert>
#include <cstdio>
#include "../msp_line_follow/control.h"
static unsigned checks=0;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static RlPacket req(uint8_t op,uint16_t seq) { return RlPacket{op,42,seq,0,0}; }
static void capture(RobotControl& r,uint8_t op,uint16_t seq,uint32_t& now,
                    uint16_t left,uint16_t right,uint16_t jitter=0) {
    CHECK(r.handle(req(op,seq),now).detail==RL_OK);
    for(unsigned i=0;i<40;++i) {
        now+=5; r.tick(now,left+(i%2?jitter:0),right);
        CHECK(!r.following && r.action==DRIVE_STOP);
    }
    CHECK(!r.calibration);
}
int main() {
    RobotControl r(WHITE_LANE,3000,true); uint32_t now=0;
    r.handle(req(RL_HELLO,0),now);
    capture(r,RL_WHITE,1,now,0,1023);
    capture(r,RL_BLACK,2,now,1023,0);
    CHECK(r.calibrated() && r.sensors[1].white==1023 && r.sensors[0].black==1023);
    CHECK(r.sensors[0].threshold()==511 && r.sensors[1].threshold()==511);
    r.tick(now+10,0,1023); r.tick(now+20,0,1023); now+=20;
    CHECK(r.handle(req(RL_START,3),now).detail==RL_OK);
    r.tick(now+10,511,511); r.tick(now+20,515,515); // ADC jitter within hysteresis.
    CHECK(r.following && r.action==DRIVE_FORWARD);
    r.tick(now+30,600,1023); r.tick(now+40,600,1023);
    CHECK(r.action==DRIVE_RIGHT);
    r.tick(now+50,511,1023); r.tick(now+60,507,1023);
    CHECK(r.action==DRIVE_RIGHT); // Retain black until below threshold minus margin.
    r.tick(now+70,490,1023); r.tick(now+80,490,1023);
    CHECK(r.action==DRIVE_FORWARD);
    r.tick(now+90,0,0); r.tick(now+100,0,0);
    CHECK(r.action==DRIVE_LEFT); // Opposite electrical polarity on right.
    r.handle(req(RL_STOP,4),now+110);
    CHECK(!r.following && r.action==DRIVE_STOP);
    r.tick(now+120,0,1023); r.tick(now+130,0,1023);
    CHECK(!r.following); // No restart on centred readings.

    RobotControl weak(WHITE_LANE,3000,true); now=0;
    weak.handle(req(RL_HELLO,0),now);
    capture(weak,RL_WHITE,1,now,100,100);
    capture(weak,RL_BLACK,2,now,139,100);
    CHECK(!weak.calibrated());
    CHECK(weak.handle(req(RL_START,3),now+1).detail==RL_NOT_CAL);
    CHECK(weak.sensors[0].span()==39 && weak.sensors[1].span()==0);

    RobotControl noisy(WHITE_LANE,3000,true); now=0;
    noisy.handle(req(RL_HELLO,0),now);
    capture(noisy,RL_WHITE,1,now,100,100,31);
    CHECK(noisy.reason==RL_CAL_UNSTABLE && noisy.sensors[0].white==-1);
    CHECK(noisy.sensors[1].white==100);
    capture(noisy,RL_WHITE,2,now,100,100,30);
    CHECK(noisy.sensors[0].white==115); // Mean, not a single sample or clipped byte.
    capture(noisy,RL_BLACK,3,now,650,650);
    CHECK(noisy.calibrated());
    noisy.tick(now+10,375,375); noisy.tick(now+30,375,375);
    CHECK(!noisy.sensors[1].settled); // Fresh classification in dead band is unknown.
    noisy.handle(req(RL_CLEAR,4),now+40);
    CHECK(!noisy.calibrated() && !noisy.sensors[0].settled && !noisy.sensors[1].settled);

    // Analogue support does not turn the legacy digital mode into an ADC reader.
    RobotControl legacy(BLACK_BETWEEN_SENSORS,3000); now=0;
    legacy.handle(req(RL_HELLO,0),now);
    capture(legacy,RL_WHITE,1,now,100,100);
    capture(legacy,RL_BLACK,2,now,650,650);
    CHECK(!legacy.calibrated()); // Both digital captures are HIGH; original issue.

    RobotControl slow(WHITE_LANE,3000,true);
    slow.handle(req(RL_HELLO,0),0);
    for(unsigned i=0;i<2;++i) { slow.sensors[i].white=100; slow.sensors[i].black=650; }
    slow.tick(0,100,100); slow.tick(10,100,100);
    CHECK(slow.handle(req(RL_START,1),20).detail==RL_OK);
    slow.tick(30,650,100); slow.tick(40,650,100); CHECK(slow.action==DRIVE_RIGHT);
    for(uint16_t seq=2;seq<=6;++seq) {
        const uint32_t t=(seq-1)*550;
        slow.handle(req(RL_KEEP,seq),t); slow.tick(t,650,100);
        CHECK(slow.following && slow.action==DRIVE_RIGHT);
    }
    slow.tick(3039,650,100); CHECK(slow.following);
    slow.tick(3040,650,100); CHECK(!slow.following && slow.reason==RL_TURN_TIMEOUT);
    slow.tick(3050,100,100); slow.tick(3060,100,100); CHECK(!slow.following);

    RobotControl expiry(WHITE_LANE,3000,true);
    expiry.handle(req(RL_HELLO,0),0);
    for(unsigned i=0;i<2;++i) { expiry.sensors[i].white=100; expiry.sensors[i].black=650; }
    expiry.tick(0,100,100); expiry.tick(10,100,100); expiry.handle(req(RL_START,1),20);
    expiry.tick(1019,100,100); CHECK(expiry.following);
    expiry.tick(1020,100,100); CHECK(!expiry.following && expiry.reason==RL_LEASE_LOST);

    RobotControl unstable(WHITE_LANE,3000,true);
    unstable.handle(req(RL_HELLO,0),0);
    for(unsigned i=0;i<2;++i) { unstable.sensors[i].white=100; unstable.sensors[i].black=650; }
    unstable.tick(0,100,100); unstable.tick(10,100,100); unstable.handle(req(RL_START,1),20);
    for(unsigned t=25;t<=200;t+=5) unstable.tick(t,((t/5)%2)?650:100,100);
    CHECK(!unstable.following && unstable.reason==RL_UNSTABLE);
    std::printf("PASS %u analogue capture/threshold/hysteresis/refusal/STOP assertions.\n",checks);
}
