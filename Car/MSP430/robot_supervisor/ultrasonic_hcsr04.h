/* Fixed confirmed car wiring: TRIG P3.2; divided ECHO P2.7. Timer_A2 only.
 * 2.2k from ECHO to P2.7 node, 3.3k from node to GND (about 3V at 5V ECHO).
 * No polling delay: Timer_A2 ends the trigger and bounds the echo wait.
 */
#ifndef ULTRASONIC_HCSR04_H
#define ULTRASONIC_HCSR04_H
#include "obstacle_guard.h"
enum { SONAR_IDLE,SONAR_TRIGGER,SONAR_RISE,SONAR_FALL,SONAR_DONE };
static ObstacleGuard obstacle;
static volatile uint8_t sonarPhase,sonarPulseValid;
static volatile uint16_t sonarRise,sonarWidth,sonarSampleAt;
static uint16_t sonarLastTrigger;
/* Configure TRIG, divided ECHO and Timer_A2 so a measurement can finish independently of
 * foreground UART traffic. */
static void sonarInit(void) {
    obstacleInit(&obstacle);
    P3SEL&=~BIT2; P3REN&=~BIT2; P3OUT&=~BIT2; P3DIR|=BIT2;
    P2SEL&=~BIT7; P2DIR&=~BIT7; P2OUT&=~BIT7; P2REN&=~BIT7;
    P2IE&=~BIT7; P2IFG&=~BIT7;
    TA2CCTL0=0; TA2CTL=TASSEL__SMCLK|MC__CONTINUOUS|TACLR;
    sonarPhase=SONAR_IDLE; sonarLastTrigger=(uint16_t)(ticks-1u);
}
/* Start due measurements and convert a completed echo or timeout into the obstacle filter's next
 * sample. */
static void sonarService(void) {
    uint8_t done,valid=0;
    uint16_t width=0,sampledAt=0;
    __disable_interrupt();
    done=sonarPhase==SONAR_DONE;
    if(done) { valid=sonarPulseValid; width=sonarWidth; sampledAt=sonarSampleAt; sonarPhase=SONAR_IDLE; }
    __enable_interrupt();
    if(done) obstacleSample(&obstacle,sampledAt,obstacleCmFromCounts(width),valid);
    obstacleAge(&obstacle,ticks);
    if(sonarPhase==SONAR_IDLE && (uint16_t)(ticks-sonarLastTrigger)>=1u) {
        sonarLastTrigger=ticks;
        if(P2IN&BIT7) { obstacleSample(&obstacle,ticks,0,0); return; }
        __disable_interrupt();
        sonarPulseValid=0; sonarWidth=0;
        P2IE&=~BIT7; P2IES&=~BIT7; P2IFG&=~BIT7;
        sonarPhase=SONAR_TRIGGER;
        P3OUT|=BIT2;
        TA2CCR0=TA2R+12u; TA2CCTL0=CCIE; /* About 11.4us, >= 10us. */
        __enable_interrupt();
    }
}
/* Read the current obstacle decision used by the motion supervisor. */
static uint8_t motionBlocked(void) {
#if defined(IR_DRIVING_TEST) && IR_DRIVING_TEST
    /* Explicit bench build only: preserve sensor diagnostics, bypass its veto.
     * Manual/protocol STOP and the Uno lease are handled separately. */
    return 0;
#else
    return obstacle.inhibit;
#endif
}
/* Print the latest sonar result and filter state to the diagnostic UART. */
static void sonarReport(void) {
    print("SONAR VALID="); number(obstacle.valid);
    print(" CM="); if(obstacle.valid) number(obstacle.cm); else print("UNKNOWN");
    print(" INHIBIT="); number(obstacle.inhibit);
    print(" FAULT="); number(obstacle.fault);
    print(" NO_ECHO_STOP=OFF");
#if defined(IR_DRIVING_TEST) && IR_DRIVING_TEST
    print(" ULTRASONIC_INTERLOCK=OFF");
#endif
    print("\r\n");
}
/* Advance the timed trigger/timeout sequence and wake the main loop when a measurement is
 * complete. */
#pragma vector=TIMER2_A0_VECTOR
__interrupt void sonar_timer_isr(void) {
    if(sonarPhase==SONAR_TRIGGER) {
        P3OUT&=~BIT2; sonarPhase=SONAR_RISE;
        TA2CCR0=TA2R+36700u; TA2CCTL0=CCIE; /* About 35ms total echo deadline. */
        P2IFG&=~BIT7; P2IE|=BIT7;
    } else {
        TA2CCTL0=0; P2IE&=~BIT7; P3OUT&=~BIT2;
        sonarPulseValid=0; sonarSampleAt=ticks; sonarPhase=SONAR_DONE;
        __bic_SR_register_on_exit(LPM0_bits);
    }
}
/* Timestamp the ECHO transitions on Port 2 and wake the main loop when the pulse width is ready. */
#pragma vector=PORT2_VECTOR
__interrupt void sonar_echo_isr(void) {
    uint16_t now=TA2R;
    if(P2IFG&BIT7) {
        P2IFG&=~BIT7;
        if(sonarPhase==SONAR_RISE && (P2IN&BIT7)) {
            sonarRise=now; P2IES|=BIT7; sonarPhase=SONAR_FALL;
        } else if(sonarPhase==SONAR_FALL && !(P2IN&BIT7)) {
            sonarWidth=(uint16_t)(now-sonarRise); sonarPulseValid=1;
            TA2CCTL0=0; P2IE&=~BIT7; sonarSampleAt=ticks; sonarPhase=SONAR_DONE;
            __bic_SR_register_on_exit(LPM0_bits);
        }
    }
}
#endif
