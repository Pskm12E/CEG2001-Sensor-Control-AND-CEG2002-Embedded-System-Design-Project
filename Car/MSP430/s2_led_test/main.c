/* MSP-EXP430F5529LP: isolated user-button / LED test. No pump activation.
 * Green LED2 = ready. One press -> six red LED1 flashes (~3 s), then OFF.
 * USE_S1_BUTTON=1 selects SW1/S1 (P2.1); default selects S2 (P1.1).
 * P1.6 stays an INPUT with a pull-down; it is never driven HIGH.
 */
#include <msp430.h>
#include <stdint.h>

#if !defined(__MSP430F5529__)
#error Select MSP430F5529 as the target device.
#endif

volatile uint16_t s2Presses = 0, redEdges = 0;

#if !defined(AUTO_LED_TEST) || !AUTO_LED_TEST
static uint8_t buttonPressed(void) {
#if defined(USE_S1_BUTTON) && USE_S1_BUTTON
    return !(P2IN & BIT1);
#else
    return !(P1IN & BIT1);
#endif
}
#endif

int main(void) {
#if !defined(AUTO_LED_TEST) || !AUTO_LED_TEST
    uint8_t flash;
#endif
    WDTCTL = WDTPW | WDTHOLD;
    P1SEL &= ~(BIT0 | BIT1 | BIT6);
    P1OUT = (P1OUT & ~(BIT0 | BIT6)) | BIT1;
    P1DIR = (P1DIR | BIT0) & ~(BIT1 | BIT6);
    P1REN |= BIT1 | BIT6;
    P2SEL &= ~BIT1; P2OUT |= BIT1; P2DIR &= ~BIT1; P2REN |= BIT1;
    P4SEL &= ~BIT7; P4OUT &= ~BIT7; P4DIR |= BIT7;

    /* Same nominal 1.048576 MHz clock setup used by the robot supervisor. */
    UCSCTL3 = SELREF__REFOCLK;
    __bis_SR_register(SCG0); UCSCTL0 = 0; UCSCTL1 = DCORSEL_2;
    UCSCTL2 = FLLD_1 | 31u;
    UCSCTL4 = SELA__REFOCLK | SELS__DCOCLKDIV | SELM__DCOCLKDIV;
    UCSCTL5 = 0; __bic_SR_register(SCG0); __delay_cycles(32768);
    UCSCTL7 &= ~DCOFFG;

    /* A button held during startup must be released before the ready light. */
#if !defined(AUTO_LED_TEST) || !AUTO_LED_TEST
    while (buttonPressed()) __delay_cycles(10486);
#endif
    P4OUT |= BIT7;
    for (;;) {
#if defined(AUTO_LED_TEST) && AUTO_LED_TEST
        P1OUT ^= BIT0; ++redEdges;
        __delay_cycles(1048576); /* Diagnostic: 1 s ON / 1 s OFF, no button. */
#else
        if (buttonPressed()) {
            __delay_cycles(20972); /* ~20 ms debounce. */
            if (buttonPressed()) {
                ++s2Presses;
                for (flash = 0; flash < 6; ++flash) {
                    P1OUT |= BIT0; ++redEdges;
                    __delay_cycles(262144); /* 250 ms ON. */
                    P1OUT &= ~BIT0; ++redEdges;
                    __delay_cycles(262144); /* 250 ms OFF. */
                }
                while (buttonPressed()) __delay_cycles(10486);
            }
        }
        __delay_cycles(10486);
#endif
    }
}
