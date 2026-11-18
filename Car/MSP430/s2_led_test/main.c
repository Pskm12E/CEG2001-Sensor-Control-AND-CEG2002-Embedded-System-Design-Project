/* MSP-EXP430F5529LP: isolated S2 / user-LED test. No pump activation.
 * Green LED2 = ready. One S2 press -> six red LED1 flashes (~3 s), then OFF.
 * P1.6 stays an INPUT with a pull-down; it is never driven HIGH.
 */
#include <msp430.h>
#include <stdint.h>

#if !defined(__MSP430F5529__)
#error Select MSP430F5529 as the target device.
#endif

volatile uint16_t s2Presses = 0, redEdges = 0;

int main(void) {
    uint8_t flash;
    WDTCTL = WDTPW | WDTHOLD;
    P1SEL &= ~(BIT0 | BIT1 | BIT6);
    P1OUT = (P1OUT & ~(BIT0 | BIT6)) | BIT1;
    P1DIR = (P1DIR | BIT0) & ~(BIT1 | BIT6);
    P1REN |= BIT1 | BIT6;
    P4SEL &= ~BIT7; P4OUT &= ~BIT7; P4DIR |= BIT7;

    /* Same nominal 1.048576 MHz clock setup used by the robot supervisor. */
    UCSCTL3 = SELREF__REFOCLK;
    __bis_SR_register(SCG0); UCSCTL0 = 0; UCSCTL1 = DCORSEL_2;
    UCSCTL2 = FLLD_1 | 31u;
    UCSCTL4 = SELA__REFOCLK | SELS__DCOCLKDIV | SELM__DCOCLKDIV;
    UCSCTL5 = 0; __bic_SR_register(SCG0); __delay_cycles(32768);
    UCSCTL7 &= ~DCOFFG;

    /* A button held during startup must be released before the ready light. */
    while (!(P1IN & BIT1)) __delay_cycles(10486);
    P4OUT |= BIT7;
    for (;;) {
        if (!(P1IN & BIT1)) {
            __delay_cycles(20972); /* ~20 ms debounce. */
            if (!(P1IN & BIT1)) {
                ++s2Presses;
                for (flash = 0; flash < 6; ++flash) {
                    P1OUT |= BIT0; ++redEdges;
                    __delay_cycles(262144); /* 250 ms ON. */
                    P1OUT &= ~BIT0; ++redEdges;
                    __delay_cycles(262144); /* 250 ms OFF. */
                }
                while (!(P1IN & BIT1)) __delay_cycles(10486);
            }
        }
        __delay_cycles(10486);
    }
}
