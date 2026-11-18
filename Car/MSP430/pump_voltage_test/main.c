/* MSP-EXP430F5529LP: control-voltage test only; keep pump disconnected.
 * MSP S2 (P1.1): one press starts ~3 s steady HIGH on P1.6.
 * Red LED1 blinks at ~2 Hz during the pulse, then turns off. No auto-repeat.
 * This replaces the robot supervisor if flashed; no robot UART/motion control.
 */
#include <msp430.h>
#include "pulse_test.h"

#if !defined(__MSP430F5529__)
#error Select MSP430F5529 as the target device.
#endif

static PulseTest test = {0};
/* Debug evidence: distinguish missing presses, a stalled ISR and resets without
 * inferring program health from an idle output latch alone. */
static volatile struct {
    uint16_t isrTicks, loopTicks, starts, stops, resetCause;
    uint8_t pressed, output;
} diag = {0};

int main(void) {
    WDTCTL = WDTPW | WDTHOLD;
    diag.resetCause = SYSRSTIV;
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
        ++diag.loopTicks;
        __bis_SR_register(LPM3_bits | GIE);
        __no_operation();
    }
}

#pragma vector=TIMER0_A0_VECTOR
__interrupt void timer0_a0_isr(void) {
    uint8_t wasOn = diag.output;
    ++diag.isrTicks;
    diag.pressed = !(P1IN & BIT1);
    diag.output = pulseTick(&test, diag.pressed);
    if (diag.output && !wasOn) ++diag.starts;
    if (!diag.output && wasOn) ++diag.stops;
    if (diag.output) P1OUT |= BIT6;
    else P1OUT &= ~BIT6;
    if (pulseLedOn(&test)) P1OUT |= BIT0;
    else P1OUT &= ~BIT0;
    __bic_SR_register_on_exit(LPM3_bits);
}
