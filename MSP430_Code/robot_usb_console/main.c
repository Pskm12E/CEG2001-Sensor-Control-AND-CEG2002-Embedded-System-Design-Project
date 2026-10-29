/* Robot MSP430 USB/serial bench, v1.0, 2026-10-29.
 * AI-assisted project-team starter, MSP-EXP430F5529LP / MSP430F5529.
 * LED1 double-blinks. S2 toggles LED2. USB UART1 accepts text commands.
 * UART0 is reserved for the future level-shifted Arduino link.
 * No motor, pump, movement, pest decision or navigation commands exist here.
 */
#include <msp430.h>
#include <stdint.h>
#include <string.h>

#if !defined(__MSP430F5529__)
#error This project requires MSP430F5529.
#endif

#define RX_SIZE 128u
#define RX_MASK (RX_SIZE - 1u)
#define LINE_SIZE 48u

typedef struct {
    volatile uint8_t data[RX_SIZE];
    volatile uint8_t head, tail, lost;
} RxRing;
typedef struct {
    char text[LINE_SIZE];
    uint8_t used, discard;
} Line;
static RxRing usbRx, linkRx;
static Line usbLine, linkLine;
static volatile uint16_t ticks, buttonCount, uartErrors, rxDrops;
static volatile uint8_t buttonLatched, pressedSamples, releasedSamples;
static volatile uint8_t buttonEvent;
enum { IDLE, WAIT_REPLY, LOOPBACK };
static uint8_t linkMode, loopIndex;
static uint16_t linkStarted;
static const char *expectedReply;
static const uint8_t loopPattern[] = {
    0x55, 0xaa, 0x00, 0xff, 0x01, 0x7f, 0x80, 'M', 'S', 'P', '\r', '\n'
};

/* Single producer (ISR), single consumer (main); byte indexes are atomic. */
static void receiveByte(RxRing *ring, uint8_t byte, uint8_t error)
{
    uint8_t next = (ring->head + 1u) & RX_MASK;
    if (error) {
        ++uartErrors;
        ring->lost = 1;
    } else if (next == ring->tail) {
        ++rxDrops;
        ring->lost = 1;
    } else {
        ring->data[ring->head] = byte;
        ring->head = next;
    }
}

static int readByte(RxRing *ring)
{
    uint8_t byte;
    if (ring->tail == ring->head) return -1;
    byte = ring->data[ring->tail];
    ring->tail = (ring->tail + 1u) & RX_MASK;
    return byte;
}

static uint8_t takeLost(RxRing *ring)
{
    uint8_t lost;
    uint16_t saved = __get_SR_register() & GIE;
    __disable_interrupt();
    lost = ring->lost;
    ring->lost = 0;
    if (saved) __enable_interrupt();
    return lost;
}

/* Only short bench messages use polling TX. Interrupts remain enabled. */
static uint8_t sendByte(uint8_t link, uint8_t byte)
{
    uint16_t start = ticks;
    while (!((link ? UCA0IFG : UCA1IFG) & UCTXIFG)) {
        if ((uint16_t)(ticks - start) >= 10u) return 0;
    }
    if (link) UCA0TXBUF = byte;
    else UCA1TXBUF = byte;
    return 1;
}

static void print(const char *text)
{
    while (*text) if (!sendByte(0, (uint8_t)*text++)) return;
}

static void number(uint16_t value)
{
    char digits[6];
    uint8_t n = 0;
    do { digits[n++] = (char)('0' + value % 10u); value /= 10u; } while (value);
    while (n) sendByte(0, (uint8_t)digits[--n]);
}

static void clockInit(void)
{
    /* 32 * 32768 = nominal 1,048,576 Hz MCLK/SMCLK. REFO also clocks ACLK. */
    UCSCTL3 = SELREF__REFOCLK;
    __bis_SR_register(SCG0);
    UCSCTL0 = 0;
    UCSCTL1 = DCORSEL_2;
    UCSCTL2 = FLLD_1 | 31u;
    UCSCTL4 = SELA__REFOCLK | SELS__DCOCLKDIV | SELM__DCOCLKDIV;
    UCSCTL5 = 0;
    __bic_SR_register(SCG0);
    __delay_cycles(32768);         /* Allow the FLL to settle at startup. */
    UCSCTL7 &= ~DCOFFG;
}

static void linkUartInit(uint8_t internalLoop)
{
    uint16_t saved = __get_SR_register() & GIE;
    __disable_interrupt();
    UCA0CTL1 = UCSWRST | UCSSEL__SMCLK;
    UCA0CTL0 = 0;                 /* 8 data bits, no parity, one stop bit. */
    UCA0BR0 = 109;                /* 1048576 / 9600 = 109.227. */
    UCA0BR1 = 0;
    UCA0MCTL = UCBRS_2;
    UCA0STAT = internalLoop ? UCLISTEN : 0;
    linkRx.head = linkRx.tail = linkRx.lost = 0;
    linkLine.used = linkLine.discard = 0;
    UCA0CTL1 &= ~UCSWRST;
    UCA0IE = UCRXIE;
    if (saved) __enable_interrupt();
}

static void init(void)
{
    WDTCTL = WDTPW | WDTHOLD;
    clockInit();
    P1SEL &= ~(BIT0 | BIT1);
    P1OUT |= BIT0 | BIT1;         /* First red flash; pull-up for S2. */
    P1DIR = (P1DIR | BIT0) & ~BIT1;
    P1REN |= BIT1;
    P1IES |= BIT1;
    P1IFG &= ~BIT1;
    P1IE |= BIT1;
    P4SEL &= ~BIT7;
    P4OUT &= ~BIT7;
    P4DIR |= BIT7;

    /* USB backchannel UART1, P4.4 TX / P4.5 RX, through existing jumpers. */
    P4SEL |= BIT4 | BIT5;
    UCA1CTL1 = UCSWRST | UCSSEL__SMCLK;
    UCA1CTL0 = 0;
    UCA1BR0 = 109;
    UCA1BR1 = 0;
    UCA1MCTL = UCBRS_2;
    UCA1CTL1 &= ~UCSWRST;
    UCA1IE = UCRXIE;

    /* Future external UART0: P3.3 TX, P3.4 RX. No 5V connection permitted. */
    P3OUT |= BIT4;
    P3REN |= BIT4;                /* Keep an unconnected receive input idle. */
    P3SEL |= BIT3 | BIT4;
    linkUartInit(0);

    TA1CTL = TASSEL__ACLK | MC__STOP | TACLR;
    TA1CCR0 = 655u - 1u;          /* About 20 ms for button debounce. */
    TA1CCTL0 = 0;
    TA0CCR0 = 3277u - 1u;         /* About 100 ms for LED pattern/timeouts. */
    TA0CCTL0 = CCIE;
    TA0CTL = TASSEL__ACLK | MC__UP | TACLR;
    __enable_interrupt();
}

static void status(void)
{
    print("STATUS BOARD=MSP430F5529 LED2=");
    print((P4OUT & BIT7) ? "ON" : "OFF");
    print(" S2_PRESSES="); number(buttonCount);
    print(" UART0=");
    print(linkMode == IDLE ? "IDLE" : linkMode == LOOPBACK ? "LOOPBACK" : "WAIT_REPLY");
    print(" UART_ERRORS="); number(uartErrors);
    print(" RX_DROPS="); number(rxDrops);
    print(" BENCH_ONLY\r\n");
}

static void finishLoop(uint8_t success)
{
    linkMode = IDLE;
    linkUartInit(0);
    print(success ? "LOOPBACK PASS: 12 bytes, internal UART0 only\r\n"
                  : "LOOPBACK FAIL: mismatch, receive error or timeout\r\n");
}

static void startLoop(void)
{
    uint8_t i;
    if (linkMode != IDLE) { print("ERR BUSY\r\n"); return; }
    linkUartInit(1);
    loopIndex = 0;
    linkStarted = ticks;
    linkMode = LOOPBACK;
    for (i = 0; i < sizeof(loopPattern); ++i) {
        if (!sendByte(1, loopPattern[i])) { finishLoop(0); return; }
    }
}

static void request(const char *command, const char *expected)
{
    if (linkMode != IDLE) { print("ERR BUSY\r\n"); return; }
    linkUartInit(0);
    expectedReply = expected;
    linkStarted = ticks;
    linkMode = WAIT_REPLY;
    print("LINK SENT: "); print(command); print("\r\n");
    while (*command) {
        if (!sendByte(1, (uint8_t)*command++)) {
            linkMode = IDLE;
            print("LINK FAIL: transmit timeout\r\n");
            return;
        }
    }
    sendByte(1, '\n');
}

static void command(char *line)
{
    if (!strcmp(line, "HELP") || !strcmp(line, "?")) {
        print("COMMANDS: PING, STATUS, ON, OFF, LOOPBACK\r\n");
        print("AFTER CONVERTER/WIRING: LINK PING, LINK ON, LINK OFF\r\n");
        print("S2 toggles local LED2. No motor or pump commands.\r\n");
    } else if (!strcmp(line, "PING")) print("PONG MSP430\r\n");
    else if (!strcmp(line, "STATUS")) status();
    else if (!strcmp(line, "ON")) { P4OUT |= BIT7; print("OK LED2 ON\r\n"); }
    else if (!strcmp(line, "OFF")) { P4OUT &= ~BIT7; print("OK LED2 OFF\r\n"); }
    else if (!strcmp(line, "LOOPBACK")) startLoop();
    else if (!strcmp(line, "LINK PING")) request("PING", "PONG UNO");
    else if (!strcmp(line, "LINK ON")) request("LED ON", "ACK LED ON");
    else if (!strcmp(line, "LINK OFF")) request("LED OFF", "ACK LED OFF");
    else print("ERR UNKNOWN COMMAND\r\n");
}

static void reply(const char *line)
{
    if (linkMode == WAIT_REPLY && !strcmp(line, expectedReply)) {
        linkMode = IDLE;
        print("LINK PASS: "); print(line); print("\r\n");
    } else {
        print("LINK UNEXPECTED: "); print(line); print("\r\n");
    }
}

static void parse(Line *line, uint8_t byte, uint8_t fromLink)
{
    if (byte == '\r' || byte == '\n') {
        if (line->discard) print(fromLink ? "LINK ERR INVALID LINE\r\n" : "ERR INVALID LINE\r\n");
        else if (line->used) {
            line->text[line->used] = 0;
            if (fromLink) reply(line->text);
            else command(line->text);
        }
        line->used = line->discard = 0;
    } else if (!line->discard) {
        if (byte < 32u || byte > 126u || line->used >= LINE_SIZE - 1u) {
            line->discard = 1;
            line->used = 0;
        } else {
            if (byte >= 'a' && byte <= 'z') byte -= 'a' - 'A';
            line->text[line->used++] = (char)byte;
        }
    }
}

int main(void)
{
    int byte;
    uint8_t budget;
    init();
    print("ROBOT MSP430 USB CONSOLE v1.0 | 9600 baud | BENCH ONLY\r\n");
    print("Type HELP then Enter.\r\n");
    for (;;) {
        if (takeLost(&usbRx)) { usbLine.used = 0; usbLine.discard = 1; }
        for (budget = 0; budget < 64u && (byte = readByte(&usbRx)) >= 0; ++budget)
            parse(&usbLine, (uint8_t)byte, 0);

        if (takeLost(&linkRx)) {
            if (linkMode == LOOPBACK) finishLoop(0);
            else { linkLine.used = 0; linkLine.discard = 1; }
        }
        for (budget = 0; budget < 64u && (byte = readByte(&linkRx)) >= 0; ++budget) {
            if (linkMode == LOOPBACK) {
                if ((uint8_t)byte != loopPattern[loopIndex]) finishLoop(0);
                else if (++loopIndex == sizeof(loopPattern)) finishLoop(1);
            } else parse(&linkLine, (uint8_t)byte, 1);
        }
        if (linkMode != IDLE && (uint16_t)(ticks - linkStarted) >= 10u) {
            if (linkMode == LOOPBACK) finishLoop(0);
            else {
                linkMode = IDLE;
                print("LINK TIMEOUT: no confirmed Arduino reply\r\n");
            }
        }
        if (buttonEvent) {
            buttonEvent = 0;
            print("BUTTON S2: LED2 "); print((P4OUT & BIT7) ? "ON\r\n" : "OFF\r\n");
        }
        /* Atomic idle check prevents sleeping with a newly arrived byte queued. */
        __disable_interrupt();
        if (usbRx.head != usbRx.tail || linkRx.head != linkRx.tail || buttonEvent)
            __enable_interrupt();
        else __bis_SR_register(LPM0_bits | GIE); /* SMCLK stays available for UART. */
    }
}

#pragma vector=USCI_A1_VECTOR
__interrupt void usb_uart_isr(void)
{
    if (UCA1IV == 2) {
        uint8_t error = UCA1STAT & UCRXERR;
        uint8_t byte = UCA1RXBUF;
        receiveByte(&usbRx, byte, error);
        __bic_SR_register_on_exit(LPM0_bits);
    }
}

#pragma vector=USCI_A0_VECTOR
__interrupt void link_uart_isr(void)
{
    if (UCA0IV == 2) {
        uint8_t error = UCA0STAT & UCRXERR;
        uint8_t byte = UCA0RXBUF;
        receiveByte(&linkRx, byte, error);
        __bic_SR_register_on_exit(LPM0_bits);
    }
}

#pragma vector=TIMER0_A0_VECTOR
__interrupt void blink_timer_isr(void)
{
    static uint8_t step;
    ++ticks;
    if (++step >= 10u) step = 0;
    if (step == 0u || step == 2u) P1OUT |= BIT0;
    else P1OUT &= ~BIT0;
    __bic_SR_register_on_exit(LPM0_bits);
}

#pragma vector=PORT1_VECTOR
__interrupt void button_isr(void)
{
    if (P1IFG & BIT1) {
        P1IE &= ~BIT1;
        P1IFG &= ~BIT1;
        buttonLatched = pressedSamples = releasedSamples = 0;
        TA1CCTL0 = CCIE;
        TA1CTL = TASSEL__ACLK | MC__UP | TACLR;
    }
}

#pragma vector=TIMER1_A0_VECTOR
__interrupt void debounce_timer_isr(void)
{
    if (!(P1IN & BIT1)) {
        releasedSamples = 0;
        if (!buttonLatched && ++pressedSamples >= 2u) {
            P4OUT ^= BIT7;
            buttonLatched = 1;
            ++buttonCount;
            buttonEvent = 1;
            __bic_SR_register_on_exit(LPM0_bits);
        }
    } else {
        pressedSamples = 0;
        if (++releasedSamples >= 2u) {
            TA1CCTL0 = 0;
            TA1CTL = TASSEL__ACLK | MC__STOP | TACLR;
            P1IFG &= ~BIT1;
            P1IE |= BIT1;
        }
    }
}
