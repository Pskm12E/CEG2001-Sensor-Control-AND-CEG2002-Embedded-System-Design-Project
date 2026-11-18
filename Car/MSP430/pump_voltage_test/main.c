/* MSP-EXP430F5529LP: control-voltage test only; keep pump disconnected.
 * MSP button S2 (P1.1), not the Zumo button: press and release for ~3 s HIGH
 * on P1.6. Red LED1 follows P1.6. Another press ends the pulse early.
 * This replaces the robot supervisor if flashed; no robot UART/motion control.
 */
#include <msp430.h>
#include "pulse_test.h"

#if !defined(__MSP430F5529__)
#error Select MSP430F5529 as the target device.
#endif

static PulseTest test = {0};

int main(void) {
    WDTCTL = WDTPW | WDTHOLD;
    /* Low latch before output enable. External gate-to-source pull-down is
     * still needed to hold a connected MOSFET off during reset/programming. */
    P1SEL &= ~(BIT0 | BIT1 | BIT6);
    P1OUT &= ~(BIT0 | BIT6);
    P1DIR = (P1DIR | BIT0 | BIT6) & ~BIT1;
    P1OUT |= BIT1; P1REN |= BIT1;
    P4SEL &= ~BIT7; P4OUT &= ~BIT7; P4DIR |= BIT7;

    UCSCTL4 = (UCSCTL4 & ~SELA_7) | SELA__REFOCLK;
    UCSCTL5 &= ~DIVA_7;
    TA0CCR0 = 328u - 1u;  /* ~10.01 ms; 300 ticks = ~3.003 seconds. */
    TA0CCTL0 = CCIE;
    TA0CTL = TASSEL__ACLK | MC__UP | TACLR;
    for (;;) {
        /* Reset-mode watchdog (~1 s), serviced outside the timer ISR. */
        WDTCTL = WDTPW | WDTCNTCL | WDTSSEL__ACLK | WDTIS__32K;
        __bis_SR_register(LPM3_bits | GIE);
        __no_operation();
    }
}

#pragma vector=TIMER0_A0_VECTOR
__interrupt void timer0_a0_isr(void) {
    if (pulseTick(&test, !(P1IN & BIT1))) P1OUT |= BIT0 | BIT6;
    else P1OUT &= ~(BIT0 | BIT6);
    __bic_SR_register_on_exit(LPM3_bits);
}
