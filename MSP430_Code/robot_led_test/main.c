/*
 * Robot MSP430 - onboard LED bring-up, version 1.0 (2026-10-29).
 * AI-assisted starter for the project team to review and extend.
 * Board: MSP-EXP430F5529LP; TARGET MCU: MSP430F5529.
 *
 * LED1 (red, P1.0): approximately 0.5 seconds ON / 0.5 seconds OFF.
 * Timer_A0 generates the interrupt; the CPU sleeps in LPM3 between events.
 * REFO provides the nominal 32768 Hz timer clock, so no external crystal
 * configuration or extra wiring is required. This is an LED-only test;
 * robot communications, sensors and actuator control are not implemented.
 */
#include <msp430.h>

#if !defined(__MSP430F5529__)
#error Select MSP430F5529 as the target device in Code Composer Studio.
#endif

int main(void)
{
    WDTCTL = WDTPW | WDTHOLD;       /* Stop the watchdog during bring-up. */

    P1SEL &= ~BIT0;                /* P1.0 is an ordinary GPIO output. */
    P1OUT &= ~BIT0;                /* Start with the red LED off. */
    P1DIR |= BIT0;

    /* Keep the other user LED off, so the expected result is unambiguous. */
    P4SEL &= ~BIT7;
    P4OUT &= ~BIT7;
    P4DIR |= BIT7;

    UCSCTL4 = (UCSCTL4 & ~SELA_7) | SELA__REFOCLK;
    UCSCTL5 &= ~DIVA_7;            /* ACLK divider = 1. */

    TA0CCR0 = 16384u - 1u;         /* 16384 / 32768 Hz = about 0.5 s. */
    TA0CCTL0 = CCIE;               /* Enable the CCR0 interrupt. */
    TA0CTL = TASSEL__ACLK | MC__UP | TACLR;

    for (;;) {
        __bis_SR_register(LPM3_bits | GIE);
        __no_operation();         /* Convenient debugger breakpoint site. */
    }
}

#pragma vector=TIMER0_A0_VECTOR
__interrupt void timer0_a0_isr(void)
{
    P1OUT ^= BIT0;                 /* Flip LED1; return to sleep after ISR. */
}
