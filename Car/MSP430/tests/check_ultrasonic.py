"""Test actual HC-SR04 policy and ISR/service adapter with fake MSP registers."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[3]
build=root/'Car/MSP430/build'
build.mkdir(exist_ok=True)
source=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#define __interrupt
#define __disable_interrupt() ((void)0)
#define __enable_interrupt() ((void)0)
#define __bic_SR_register_on_exit(x) ((void)(x))
enum { BIT2=4,BIT7=128,TASSEL__SMCLK=512,MC__CONTINUOUS=32,TACLR=4,CCIE=16,LPM0_bits=16 };
static uint8_t P3SEL,P3REN,P3OUT,P3DIR,P2SEL,P2DIR,P2OUT,P2REN,P2IE,P2IES,P2IFG,P2IN;
static uint16_t TA2CCTL0,TA2CTL,TA2CCR0,TA2R,ticks;
static void print(const char*) {}
static void number(uint16_t) {}
#include "../robot_supervisor/ultrasonic_hcsr04.h"
#include "../robot_supervisor/console_tx.h"
static unsigned checks;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static void echo(uint16_t cm) {
    CHECK(sonarPhase==SONAR_TRIGGER && (P3OUT&BIT2));
    TA2R=TA2CCR0; sonar_timer_isr();
    CHECK(sonarPhase==SONAR_RISE && !(P3OUT&BIT2) && (P2IE&BIT7));
    TA2R=(uint16_t)(TA2R+100u); P2IN=BIT7; P2IFG=BIT7; sonar_echo_isr();
    CHECK(sonarPhase==SONAR_FALL && (P2IES&BIT7));
    TA2R=(uint16_t)(TA2R+((uint32_t)cm*2097152ul+17150ul)/34300ul);
    P2IN=0; P2IFG=BIT7; sonar_echo_isr();
    CHECK(sonarPhase==SONAR_DONE && sonarPulseValid && !TA2CCTL0);
    sonarService();
    CHECK(obstacle.valid && obstacle.cm==cm);
}
int main() {
    ObstacleGuard g; obstacleInit(&g); CHECK(!g.inhibit && g.fault && !g.valid);
    obstacleSample(&g,0,40,1); CHECK(!g.inhibit && !g.fault);
    obstacleSample(&g,1,40,1); CHECK(!g.inhibit);
    obstacleSample(&g,2,20,1); CHECK(!g.inhibit); // Old stop threshold now stays clear.
    obstacleSample(&g,2,10,1); CHECK(!g.inhibit);
    obstacleSample(&g,2,6,1); CHECK(!g.inhibit);
    obstacleSample(&g,2,5,1); CHECK(g.inhibit);
    obstacleSample(&g,3,6,1); CHECK(g.inhibit && !g.clearCount);
    obstacleSample(&g,4,7,1); CHECK(g.inhibit);
    obstacleSample(&g,5,7,1); CHECK(!g.inhibit);
    obstacleSample(&g,6,0,0); CHECK(!g.inhibit && !g.valid);
    obstacleSample(&g,7,0,0); CHECK(!g.inhibit);
    obstacleAge(&g,8); CHECK(!g.inhibit && g.fault);
    obstacleSample(&g,9,0,1); CHECK(!g.valid && !g.inhibit);
    obstacleSample(&g,10,401,1); CHECK(!g.valid && !g.inhibit);
    obstacleSample(&g,11,1,1); CHECK(!g.valid && !g.inhibit);
    obstacleSample(&g,12,2,1); CHECK(g.valid && g.inhibit);
    obstacleInit(&g); obstacleSample(&g,65534,50,1); obstacleSample(&g,65535,50,1);
    obstacleAge(&g,1); CHECK(!g.inhibit); obstacleAge(&g,2); CHECK(!g.inhibit && g.fault);
    // A past near reading expires; clearing an inhibit never starts a motor.
    obstacleSample(&g,3,2,1); CHECK(g.inhibit);
    obstacleAge(&g,5); CHECK(g.inhibit);
    obstacleAge(&g,6); CHECK(!g.inhibit && !g.valid && g.fault);
    CHECK(obstacleCmFromCounts(1223)==20);
    CHECK(obstacleCmFromCounts(2446)==40);
    CHECK(obstacleCmFromCounts(24457)==400);
    ticks=0; P2IN=0; TA2R=65530; sonarInit();
    CHECK(!motionBlocked() && !(P3OUT&BIT2) && (P3DIR&BIT2) && !(P2DIR&BIT7));
    sonarService(); echo(40); CHECK(!motionBlocked()); // Wrapped timer pulse.
    ++ticks; sonarService(); echo(40); CHECK(!motionBlocked());
    ++ticks; sonarService(); echo(10); CHECK(!motionBlocked());
    ++ticks; sonarService(); echo(2); CHECK(motionBlocked());
    ++ticks; sonarService(); echo(40); CHECK(motionBlocked());
    ++ticks; sonarService(); echo(40); CHECK(!motionBlocked());
    ++ticks; sonarService(); TA2R=TA2CCR0; sonar_timer_isr(); // Finish trigger.
    TA2R=TA2CCR0; sonar_timer_isr(); CHECK(sonarPhase==SONAR_DONE && !sonarPulseValid);
    sonarService(); CHECK(!obstacle.valid && !motionBlocked());
    ++ticks; P2IN=BIT7; sonarService(); CHECK(!(P3OUT&BIT2)); // Stuck high; no trigger.
    ++ticks; sonarService(); CHECK(!motionBlocked() && obstacle.fault);
    P2IN=0; sonarReport();
    // A delayed main loop must not give an old echo a new freshness timestamp.
    sonarPhase=SONAR_DONE; sonarPulseValid=1; sonarWidth=2446;
    sonarSampleAt=100; ticks=103; sonarLastTrigger=103; sonarService();
    CHECK(!obstacle.inhibit && !obstacle.valid && obstacle.fault);
    ConsoleTx queue={}; CHECK(consoleTxPop(&queue)==-1);
    for(unsigned i=0;i<511;++i) CHECK(consoleTxPush(&queue,uint8_t(i)));
    CHECK(!consoleTxPush(&queue,99));
    for(unsigned i=0;i<511;++i) CHECK(consoleTxPop(&queue)==int(uint8_t(i)));
    CHECK(consoleTxPop(&queue)==-1);
    for(unsigned i=0;i<1024;++i) {
        CHECK(consoleTxPush(&queue,uint8_t(i)));
        CHECK(consoleTxPop(&queue)==int(uint8_t(i)));
    }
    std::printf("PASS %u ultrasonic policy, timer-wrap, echo-edge and timeout assertions.\n",checks);
}
'''
cpp=build/'ultrasonic_tests.cpp'
cpp.write_text(source,encoding='utf-8')
exe=build/'ultrasonic_tests.exe'
subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror',
                '-Wno-unknown-pragmas','-static',str(cpp),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
