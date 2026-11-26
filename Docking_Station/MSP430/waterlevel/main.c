/*
 * MSP430F5529 docking station - sensor monitoring and timed refill control.
 * Coordinated refill over the station USB backchannel.
 * 1. Boot with pump command OFF; initialise GPIO, LCD and UART.
 * 2. Use nominal 32768 Hz REFO as ACLK; retain reset-default MCLK for LCD delays.
 * 3. Timer A0 provides a nominal 100 ms scheduler and immediate input interlocks.
 * 4. Five processed LOW Hall samples confirm arrival; HIGH clears dock status.
 * 5. Five processed absent samples arm one refill attempt for the next visit.
 * 6. Wait for the car stop acknowledgement, then settle 3 s before refilling.
 * 7. Start Timer A1 and the pump command after an atomic final sensor check.
 * 8. Timer A1 counts 40960 ticks at ACLK/8 = 4096 Hz: nominal 10 s cutoff.
 * 9. Timer A0 stops pumping on raw Hall HIGH or reservoir comparator LOW.
 * 10. Update LCD status/countdowns and send state-change messages to the PC.
 * 11. Low water cycles four Booster LEDs with alternating ON/all-OFF intervals.
 * 12. Require another undock/dock visit before another attempt; no keypad control.
 *
 * PIN MAP (port names must match the physical connections):
 * P2.4: conditioned Hall input, LOW = magnet present, internal pull-up enabled.
 * P3.2: LM339 output, LOW = low water, HIGH = sufficient; external 3.3 V pull-up.
 * P1.4: active-HIGH driver IN command; motor power comes from the driver supply.
 * P1.0: LaunchPad dock LED. Booster alarm LEDs: P1.2, P1.3, P8.1, P8.2.
 * LCD D4-D7: P6.0-P6.3; RS: P6.4; RW: P6.5 held LOW; EN: P6.6.
 * UART UCA1: P4.4 TX / P4.5 RX, 9600 baud, 8 data bits, no parity, 1 stop bit.
 *
 * IMPLEMENTATION LIMITS:
 * The laptop renews a per-visit HOLD only from the stopped car acknowledgement.
 * FULL for the held visit ends refill above the car's calibrated 60% threshold.
 * No ADC, keypad, manual stop or low-power sleep is implemented in this version.
 * An externally pulled-up, disconnected comparator signal can appear water-OK.
 * Residual wetness can delay the physical low-water signal; code cannot fix this.
 * Qualification/display timings depend on foreground processing; raw interlocks
 * run in the timer ISR, nominally every 100 ms while interrupts can be serviced.
 * Pump command OFF is not proof that the motor or water flow stops immediately.
 * Keep pump power disconnected when halting/debugging; a halt can delay cutoffs.
 * AI-assisted firmware; this documentation edit is not physical validation.
 * Supplied LCD driver credit: Gaurav, circuitvalley.com (see lcd16.c/.h).
 */

#include <msp430.h> /* Device register names, bit masks and compiler intrinsics for the selected MSP430. */
#include "lcd16.h" /* LCD pin definitions and function declarations shared with the driver. */

#define HALL_BIT BIT4 /* Use bit 4 on PORT 2; LOW means magnet present. */
#define WATER_OK_BIT BIT2 /* Use bit 2 on PORT 3; HIGH means the comparator reports water available. */
#define WATER_LED_ACTIVE_HIGH 1 /* 1 means a HIGH GPIO level turns an alarm LED on; 0 inverts the LED masks. */

#define PUMP_DURATION_SECONDS 10u /* Common duration setting for the hardware cutoff and LCD remaining time. */
#define PUMP_TIMER_HZ 4096UL /* Nominal REFO ACLK 32768 Hz divided by 8 for Timer A1. */
/* 4096 x 10 = 40960 timer counts; this fits the 16-bit timer. */
#define PUMP_TIMER_COUNTS (PUMP_TIMER_HZ * PUMP_DURATION_SECONDS)

void lcdcmd(unsigned char cmd); /* Local declaration retained because the supplied LCD header omits this API. */

volatile unsigned char robot_docked = 0; /* Qualified Hall status; 0 = absent, 1 = docked. */
volatile unsigned char reservoir_low = 0; /* Qualified water warning; read together with water_known. */
static unsigned char water_known = 0; /* Prevent pumping until an initial low/OK condition has been established. */
volatile unsigned char pump_running = 0; /* Shared ISR/foreground flag recording an active pump command. */
/* One pending-work flag, not a queue; delayed foreground calls may coalesce ticks. */
static volatile unsigned char tick_pending = 0;
static volatile unsigned char pump_stop_event = 0; /* Pending stop reason for the next foreground UART report. */
/* 16-bit nominal 100 ms counter; volatile prevents cached reads across interrupts. */
static volatile unsigned int system_ticks = 0;
static unsigned char dock_waiting = 0; /* True while the nonblocking pre-pump countdown is active. */
static unsigned int dock_wait_start = 0; /* Tick snapshot used to measure the 3-second wait. */
static unsigned char dock_wait_seconds = 0; /* Rounded-up pre-pump seconds shown on the LCD. */
static void uart_send(const char *s); /* Forward declaration lets earlier functions send event messages. */

enum DockPhase { BOOT, CLEAR, ARRIVAL, SETTLE, FILL, DONE, FAULT };
static volatile enum DockPhase phase = BOOT;
static volatile unsigned int visit, hold_tick;
static volatile unsigned char hold_valid;
static volatile unsigned char refill_satisfied;
#define HOLD_TIMEOUT_TICKS 25u
static unsigned char hold_fresh(void);

/* UART RX is interrupt-driven so LCD writes cannot lose a multi-byte grant. */
/* Read the UART RX byte from UCA1. Only a complete HOLD or FULL line with the current visit
 * number can change the pump permit. */
#pragma vector=USCI_A1_VECTOR
__interrupt void dock_rx_isr(void)
{
    static unsigned char length, invalid, full_command;
    static unsigned int id;
    unsigned char error, c;
    if (UCA1IV != 2) return;
    error = UCA1STAT & UCRXERR;
    c = UCA1RXBUF;
    if (error) invalid = 1;
    if (c == '\n') {
        if (!invalid && length > 5 && id && id == visit &&
            (phase == ARRIVAL || phase == SETTLE || phase == FILL) &&
            !(P2IN & HALL_BIT)) {
            if (!full_command) {
                hold_tick = system_ticks;
                hold_valid = 1;
            } else if (hold_fresh() && robot_docked && (phase == SETTLE || phase == FILL)) {
                refill_satisfied = 1;
            }
        }
        length = invalid = 0;
        id = 0;
    } else if (!invalid) {
        if (length == 0) full_command = c == 'F';
        if (length < 5) invalid = c != (full_command ? "FULL " : "HOLD ")[length];
        else if (length >= 10 || c < '0' || c > '9' ||
                 id > 6553u || (id == 6553u && c > '5')) invalid = 1;
        else id = id * 10u + c - '0';
        ++length;
    }
}

/* Return true while the current visit's hold permit is younger than its timeout in 100 ms ticks. */
static unsigned char hold_fresh(void)
{
    return hold_valid && (unsigned int)(system_ticks - hold_tick) < HOLD_TIMEOUT_TICKS;
}

/* Transmit the Hall input, commanded pump output, visit number and named phase to the laptop. */
static void report_phase(void)
{
    static const char *const names[] = {"BOOT", "CLEAR", "ARRIVAL", "SETTLE", "FILL", "DONE", "FAULT"};
    char digits[6];
    unsigned int n = visit, i = 5;
    digits[i] = 0;
    do { digits[--i] = (char)('0' + n % 10); n /= 10; } while (n);
    /* Report the actual Hall input even when the station boots already occupied.
     * Keep the original DOCK1 phase line for existing laptop installations. */
    uart_send("HALL1 ");
    uart_send((P2IN & HALL_BIT) ? "0" : (robot_docked ? "1" : "?"));
    uart_send(pump_running ? " PUMP=1\n" : " PUMP=0\n");
    uart_send("DOCK1 "); uart_send(digits+i); uart_send(" "); uart_send(names[phase]); uart_send("\n");
}

/* ticks_now()
 * Purpose: Read the shared 16-bit scheduler counter without ISR interference.
 * Parameters: None.
 * Returns/effects: Snapshot of system_ticks; each tick is nominally 100 ms.
 * Operation: Save/restore GIE so callers already inside a critical section stay protected.
 *   Unsigned short-interval subtraction tolerates counter wrap.
 */
static unsigned int ticks_now(void)
{
    unsigned int value;
    /* Remember whether global interrupts were enabled before this operation. */
    unsigned int saved_gie = __get_SR_register() & GIE;
    __disable_interrupt(); /* Begin a critical section so ISR and foreground updates cannot interleave here. */
    value = system_ticks; /* Read the shared tick counter while protected. */
    if (saved_gie) __enable_interrupt(); /* Restore interrupts only if the caller originally had them enabled. */
    return value; /* Return the captured value rather than rereading the changing counter. */
}

/* pump_off()
 * Purpose: Remove the driver command and stop the pump deadline timer.
 * Reasons: 1 = timeout, 2 = dock lost, 3 = low station water, 4 = hold lost,
 * 5 = car refill threshold reached.
 * Returns/effects: None; updates P1.4, Timer A1, pump_running and a pending log event.
 * Operation: Callable from an ISR or foreground. GPIO is cleared before bookkeeping; UART is
 *   deferred to the foreground.
 */
static void pump_off(unsigned char reason)
{
    P1OUT &= ~BIT4; /* Drive driver IN at P1.4 LOW first: remove the pump ON command. */
    TA1CTL = MC_0; /* Stop Timer A1; a later start reconfigures its clock and clears its count. */
    TA1CCTL0 = 0; /* Disable CCR0 interrupts and clear its control/flag state. */
    /* Record a transition only if the pump was actually commanded running. */
    if (pump_running) pump_stop_event = reason;
    pump_running = 0; /* Publish the stopped state for foreground control and LCD status. */
}

#pragma vector=TIMER1_A0_VECTOR /* Bind the following handler to Timer A1 CCR0 interrupt vector. */
/* pump_deadline_isr()
 * Purpose: Handle Timer A1 CCR0 expiry and end the nominal 10 s pump interval.
 * Parameters: None; invoked by TIMER1_A0_VECTOR.
 * Returns/effects: None (interrupt handler).
 * Operation: Uses the dedicated cutoff rather than relying on LCD updates or a blocking delay.
 *   This is software control, not an independent hardware power switch.
 */
__interrupt void pump_deadline_isr(void)
{
    pump_off(1); /* Timeout event: stop the pump at the dedicated timer deadline. */
}

#pragma vector=TIMER0_A0_VECTOR /* Bind the following handler to Timer A0 CCR0 interrupt vector. */
/* sensor_tick_isr()
 * Purpose: Check raw pump interlocks and schedule foreground work.
 * Parameters: None; invoked by TIMER0_A0_VECTOR.
 * Returns/effects: None (interrupt handler); advances system_ticks and sets tick_pending.
 * Operation: A HIGH Hall input or LOW water input stops an active command on this tick. If both
 *   occur, dock-lost has priority in the event message.
 */
__interrupt void sensor_tick_isr(void)
{
    ++system_ticks;
    if (hold_valid && !hold_fresh()) hold_valid = 0;
    if (pump_running) { /* Handle this branch only while a pump command is active. */
        /* Raw Hall HIGH means dock lost: stop without waiting for foreground filtering. */
        if (P2IN & HALL_BIT) pump_off(2);
        /* Raw comparator LOW means insufficient station water: stop on this tick. */
        else if (!(P3IN & WATER_OK_BIT)) pump_off(3);
        else if (!hold_fresh()) pump_off(4);
        else if (refill_satisfied) pump_off(5);
    }
    tick_pending = 1; /* Request sensor/control/display processing in the foreground. */
}

/* Announce the first raw arrival before qualification or LCD work. Report
 * again every 500 ms so the host can detect a disconnected USB cable. */
static void pump_test_update(void)
{
    static unsigned char absent_count;
    static unsigned int last_report;
    enum DockPhase previous = phase;
    unsigned int now = ticks_now();
    unsigned char cutoff = pump_stop_event;
    if (cutoff) {
        pump_stop_event = 0;
        phase = (cutoff == 1 || cutoff == 5) ? DONE : FAULT;
    }
    if (P2IN & HALL_BIT) {
        refill_satisfied = hold_valid = dock_waiting = dock_wait_seconds = 0;
        if (absent_count < 5) ++absent_count;
        if (absent_count >= 5) phase = CLEAR;
        else if (phase != CLEAR && phase != BOOT) phase = FAULT;
    } else {
        absent_count = 0;
        if (phase == CLEAR) {
            if (++visit == 0) ++visit;
            hold_valid = 0;
            phase = ARRIVAL;
        }
        if (phase == ARRIVAL && robot_docked && hold_fresh()) {
            if (!water_known || reservoir_low || !(P3IN & WATER_OK_BIT)) phase = FAULT;
            else {
                phase = SETTLE;
                dock_waiting = 1;
                dock_wait_start = now;
            }
        }
        if (phase == SETTLE) {
            unsigned int elapsed = (unsigned int)(now - dock_wait_start);
            if (!hold_fresh() || !water_known || reservoir_low || !(P3IN & WATER_OK_BIT)) phase = FAULT;
            else if (refill_satisfied) phase = DONE;
            else if (elapsed < 30u) dock_wait_seconds = (unsigned char)((30u-elapsed+9u)/10u);
            else {
                __disable_interrupt();
                if (!hold_fresh() || (P2IN & HALL_BIT) || !(P3IN & WATER_OK_BIT)) phase = FAULT;
                else if (refill_satisfied) phase = DONE; /* FULL may have arrived just before interrupts were masked. */
                else {
                    TA1CTL = MC_0;
                    TA1CCR0 = (unsigned int)(PUMP_TIMER_COUNTS-1UL);
                    TA1CCTL0 = CCIE;
                    TA1CTL = TASSEL_1 | ID_3 | MC_1 | TACLR;
                    pump_running = 1;
                    P1OUT |= BIT4;
                    phase = FILL;
                }
                __enable_interrupt();
            }
            if (phase != SETTLE) dock_waiting = dock_wait_seconds = 0;
        }
    }
    if (phase != previous || (unsigned int)(now-last_report) >= 5u) {
        report_phase();
        last_report = now;
    }
}

/* pump_seconds_left()
 * Purpose: Calculate the displayed pump countdown from Timer A1.
 * Parameters: None; reads TA1R, CCIFG and pump_running.
 * Returns/effects: Remaining whole seconds rounded UP, or zero if stopped/expired.
 * Operation: Read the asynchronous timer until two samples agree. This formats the display; the
 *   Timer A1 ISR remains responsible for cutoff.
 */
static unsigned char pump_seconds_left(void)
{
    unsigned int a, b;
    /* Remember whether global interrupts were enabled before this operation. */
    unsigned int saved_gie = __get_SR_register() & GIE;
    unsigned char seconds = 0; /* Default countdown is zero while the pump is stopped. */
    __disable_interrupt(); /* Begin a critical section so ISR and foreground updates cannot interleave here. */
    if (pump_running) { /* Handle this branch only while a pump command is active. */
        /* Accept two matching reads of the timer running asynchronously to the CPU. */
        do { a = TA1R; b = TA1R; } while (a != b);
        /* If the deadline flag is already pending, show zero rather than wrapping the display. */
        if (TA1CCTL0 & CCIFG) seconds = 0;
        /* Remaining counts divided by 4096, rounded UP for the visible countdown. */
        else seconds = (unsigned char)((PUMP_TIMER_COUNTS - a + PUMP_TIMER_HZ - 1UL) / PUMP_TIMER_HZ);
    }
    if (saved_gie) __enable_interrupt(); /* Restore interrupts only if the caller originally had them enabled. */
    return seconds; /* Return a display value; this function never decides when to stop the pump. */
}

/* uart_send()
 * Purpose: Transmit a zero-terminated event message through UCA1.
 * Parameters: s: pointer to a valid, zero-terminated character string.
 * Returns/effects: None; advances through the string and writes the transmit buffer.
 * Operation: Blocking foreground function. Polling waits for TX buffer availability; interrupts
 *   remain available unless the caller disabled them.
 */
static void uart_send(const char *s)
{
    while (*s) { /* Continue until the zero terminator of the supplied message. */
        while (!(UCA1IFG & UCTXIFG)) { } /* Wait until the UART transmit buffer can accept another byte. */
        UCA1TXBUF = (unsigned char)*s++; /* Queue one character and move the pointer to the next character. */
    }
}

/* uart_init()
 * Purpose: Configure the USB-backchannel UART peripheral.
 * Parameters: None.
 * Returns/effects: None; configures P4.4/P4.5 and UCA1.
 * Operation: Select ACLK, divider 3 and UCBRS_3 modulation for nominal 9600 baud. CTL0=0
 *   selects asynchronous 8N1. RX accepts visit-scoped HOLD commands.
 */
static void uart_init(void)
{
    P4SEL |= BIT4 | BIT5; /* Select UCA1 TX/RX peripheral functions on P4.4/P4.5. */
    UCA1CTL1 = UCSWRST; /* Hold UART in software reset while configuring it. */
    UCA1CTL0 = 0; /* Select asynchronous UART with eight data bits, no parity and one stop bit. */
    UCA1CTL1 |= UCSSEL_1; /* Use ACLK as the UART baud-rate clock. */
    UCA1BR0 = 3; /* Low byte of the integer baud divider: 32768 / 9600 is approximately 3.41. */
    UCA1BR1 = 0; /* High byte of the baud divider is zero. */
    UCA1MCTL = UCBRS_3; /* Fractional bit-time modulation supplements the integer divider. */
    UCA1CTL1 &= ~UCSWRST;
    UCA1IE |= UCRXIE; /* Receive the laptop's visit-scoped permit. */
}

/* booster_alarm_pattern()
 * Purpose: Apply a logical four-LED mask without disturbing other port bits.
 * Parameters: mask bits 0..3: P1.2, P1.3, P8.1, P8.2 respectively.
 * Returns/effects: None; changes only those LED output bits.
 * Operation: Build separate port masks, optionally invert for active-LOW LEDs, and protect the
 *   P1 read/modify/write against interrupt-driven pump changes while preserving the dock
 *   indicator.
 */
static void booster_alarm_pattern(unsigned char mask)
{
    unsigned char p1 = 0, p8 = 0; /* Build independent output masks for the LEDs on each port. */
    /* Remember whether global interrupts were enabled before this operation. */
    unsigned int saved_gie = __get_SR_register() & GIE;
    if (mask & BIT0) p1 |= BIT2; /* Logical LED 0 maps to Booster P1.2. */
    if (mask & BIT1) p1 |= BIT3; /* Logical LED 1 maps to Booster P1.3. */
    if (mask & BIT2) p8 |= BIT1; /* Logical LED 2 maps to Booster P8.1. */
    if (mask & BIT3) p8 |= BIT2; /* Logical LED 3 maps to Booster P8.2. */
#if !WATER_LED_ACTIVE_HIGH /* Compile this inversion only for an active-LOW LED configuration. */
    p1 ^= BIT2 | BIT3; /* Invert the two Port 1 alarm LED levels only. */
    p8 ^= BIT1 | BIT2; /* Invert the two Port 8 alarm LED levels only. */
#endif
    __disable_interrupt(); /* Begin a critical section so ISR and foreground updates cannot interleave here. */
    /* Replace alarm LED bits while preserving the P1.0 dock LED and P1.4 pump. */
    P1OUT = (P1OUT & ~(BIT2 | BIT3)) | p1;
    P8OUT = (P8OUT & ~(BIT1 | BIT2)) | p8; /* Replace only the two Port 8 alarm LED bits. */
    if (saved_gie) __enable_interrupt(); /* Restore interrupts only if the caller originally had them enabled. */
}

/* water_led()
 * Purpose: Set the initial low-water LED state.
 * Parameters: on: nonzero turns on the first alarm LED; zero turns all four off.
 * Returns/effects: None.
 * Operation: The repeating chase is subsequently advanced by water_blink_tick().
 */
static void water_led(unsigned char on)
{
    booster_alarm_pattern(on ? BIT0 : 0); /* Select first LED for alarm entry, otherwise all four OFF. */
}

/* gpio_init()
 * Purpose: Configure sensor inputs and driver/LED outputs at startup.
 * Parameters: None.
 * Returns/effects: None; pump starts commanded OFF.
 * Operation: SEL clears choose GPIO, DIR sets direction, OUT sets the initial level and REN
 *   controls resistors. Hall has an internal pull-up; water uses its external pull-up.
 */
static void gpio_init(void)
{
    P1OUT &= ~(BIT0 | BIT4); /* Preload dock LED and pump output LOW before enabling their outputs. */
    P1SEL &= ~(BIT0 | BIT4); /* Select GPIO rather than peripheral functions for P1.0/P1.4. */
    P1DIR |= BIT0 | BIT4; /* Configure dock indicator and pump command pins as outputs. */
    water_led(0); /* Clear all four alarm LEDs; also used when sufficient water is confirmed. */
    P1SEL &= ~(BIT2 | BIT3); /* Select GPIO for the first two Booster LEDs. */
    P1DIR |= BIT2 | BIT3; /* Make the first two Booster LED pins outputs. */
    P8SEL &= ~(BIT1 | BIT2); /* Select GPIO for the remaining two Booster LEDs. */
    P8DIR |= BIT1 | BIT2; /* Make the remaining two Booster LED pins outputs. */
    P2SEL &= ~HALL_BIT; /* Select GPIO for the Hall input at P2.4. */
    P2DIR &= ~HALL_BIT; /* Configure P2.4 as an input. */
    P2OUT |= HALL_BIT; /* Select pull-UP rather than pull-down for the Hall input resistor. */
    P2REN |= HALL_BIT; /* Enable the Hall input internal resistor; signal still must be 3.3 V compatible. */
    P3SEL &= ~WATER_OK_BIT; /* Select GPIO for the conditioned water input at P3.2. */
    P3DIR &= ~WATER_OK_BIT; /* Configure P3.2 as an input, not an analogue ADC channel. */
    P3OUT &= ~WATER_OK_BIT; /* Clear its output latch; this does not pull down while REN is disabled. */
    P3REN &= ~WATER_OK_BIT; /* Disable internal resistors; the LM339 output uses an external 3.3 V pull-up. */
}

/* lcd_line()
 * Purpose: Write exactly one visible 16-character LCD row.
 * Parameters: row: 0 or 1; s: zero-terminated text to display.
 * Returns/effects: None; pads unused columns with spaces and truncates text after 16 chars.
 * Operation: Padding erases characters left over from a previous longer message without
 *   clearing the whole LCD.
 */
static void lcd_line(unsigned char row, const char *s)
{
    unsigned char i;
    gotoXy(0, row); /* Move to the beginning of the requested LCD row. */
    for (i = 0; i < 16; ++i) { /* Always overwrite all 16 visible positions. */
        if (*s) lcdData((unsigned char)*s++); /* Write another character if text remains. */
        else lcdData(' '); /* Fill the rest of the row with spaces to erase stale characters. */
    }
}

/* lcd_update()
 * Purpose: Refresh dock/countdown and reservoir LCD messages when needed.
 * Parameters: None; reads current states and the hardware-timer countdown.
 * Returns/effects: None; updates the LCD and cached display values.
 * Operation: 255 invalidates cached states. Every ten calls, force dock/water repaint. The pump
 *   deadline does not depend on LCD refresh timing.
 */
static void lcd_update(void)
{
    /* Persistent cache; 255 cannot be a valid binary dock state, forcing first update. */
    static unsigned char old_dock = 255;
    static unsigned char old_water = 255; /* Persistent cache of last displayed water status. */
    static unsigned char old_pump = 255; /* Persistent cache of the last displayed pump state. */
    static unsigned char old_seconds = 255; /* Persistent cache of the hardware-based countdown. */
    /* Read the display countdown from the same timer used for cutoff. */
    unsigned char seconds_left = pump_seconds_left();
    static unsigned char old_wait = 255; /* Persistent cache of the pre-pump countdown value. */
    static unsigned char refresh_ticks = 0; /* Count foreground display calls; not a separate hardware timer. */

    if (++refresh_ticks >= 10) { /* Force a periodic dock/water repaint every ten calls (nominally one second). */
        refresh_ticks = 0; /* Begin the next refresh-call interval. */
        old_dock = 255; /* Invalidate the cached dock value so the next row comparison redraws it. */
        old_water = 255; /* Invalidate the cached water value for repaint. */
    }
    /* Encode 0 = OK, 1 = low, 2 = not yet established. */
    unsigned char water_status = water_known ? reservoir_low : 2;
    /* Rewrite the top row when dock, pump or countdown state differs. */
    if (old_dock != robot_docked || old_pump != pump_running || old_wait != dock_wait_seconds || old_seconds != seconds_left) {
        if (dock_waiting) { /* Handle the active pre-pump countdown state. */
            /* Editable text buffer; the digit at index 12 is replaced below. */
            char countdown[] = "Starting in 3s";
            /* Convert the single wait digit to its ASCII character. */
            countdown[12] = (char)('0' + dock_wait_seconds);
            lcd_line(0, countdown); /* Display the settling countdown on the first row. */
        } else {
            if (pump_running) { /* Handle this branch only while a pump command is active. */
                /* Editable top-row message with two countdown digit positions. */
                char pumping[] = "PUMP WATER: 00s";
                /* Put the tens digit of remaining pump seconds at index 12. */
                pumping[12] = (char)('0' + seconds_left / 10u);
                pumping[13] = (char)('0' + seconds_left % 10u); /* Put the units digit at index 13. */
                lcd_line(0, pumping); /* Show the current pump countdown. */
            } else {
                /* When not waiting/pumping, display the qualified docking state. */
                lcd_line(0, robot_docked ? "Robot: DOCKED" : "Robot:NOT DOCKED");
            }
        }
        old_wait = dock_wait_seconds; /* Remember the wait value just rendered. */
        old_dock = robot_docked; /* Remember the dock state just rendered. */
        old_pump = pump_running; /* Remember the pump state just rendered. */
        old_seconds = seconds_left; /* Remember the pump countdown just rendered. */
    }
    if (old_water != water_status) { /* Rewrite the lower row only if water status changed or was invalidated. */
        if (!water_known) lcd_line(1, ""); /* Keep the water row blank until status has been established. */
        /* Display the comparator-derived reservoir condition. */
        else lcd_line(1, reservoir_low ? "WATER LEVEL LOW" : "WATER LEVEL OK");
        old_water = water_status; /* Store the newly displayed status. */
    }
}

/* water_blink_tick()
 * Purpose: Advance the four-LED low-water chase without a delay loop.
 * Parameters: None; uses the scheduler tick counter and water status.
 * Returns/effects: None; writes an LED mask.
 * Operation: Two nominal 100 ms ticks per phase give 0.2 s ON then 0.2 s all OFF; four LEDs
 *   make an approximately 1.6 s repeating cycle.
 */
static void water_blink_tick(void)
{
    static unsigned char was_low = 0; /* Remember whether the chase was already active on the previous call. */
    static unsigned int start_tick = 0; /* Time origin of the current alarm pattern. */
    unsigned int now = ticks_now(); /* Read the scheduler timebase without blocking the main loop. */
    unsigned char phase;
    if (!water_known || !reservoir_low) { /* Unknown/OK water: reset the pattern and keep all alarm LEDs OFF. */
        was_low = 0; /* Reset so a later low-water event restarts with the first LED. */
        booster_alarm_pattern(0); /* Switch all four Booster alarm LEDs OFF. */
        return;
    }
    if (!was_low) { /* On a new low-water event, establish the pattern origin once. */
        was_low = 1; /* Record that the alarm pattern is now active. */
        start_tick = now; /* Start phase timing at this low-water event. */
    }
    /* Two ticks per phase; modulo eight cycles through four ON phases and four OFF gaps. */
    phase = (unsigned char)(((unsigned int)(now - start_tick) / 2u) % 8u);
    if (phase & 1u) booster_alarm_pattern(0); /* Odd phases: all LEDs OFF. */
    /* Even phases: turn on the next single LED (mask 1, 2, 4, then 8). */
    else booster_alarm_pattern((unsigned char)(1u << (phase / 2u)));
}

/* sensors_check()
 * Purpose: Qualify sensor states for indicators, the countdown and messages.
 * Parameters: None; samples Hall P2.4 and comparator P3.2.
 * Returns/effects: None; updates robot_docked, reservoir_low, water_known and LEDs.
 * Operation: Five processed Hall LOW samples qualify arrival; one HIGH clears it. One water LOW
 *   raises the alarm; three HIGH samples clear it. Foreground/UART delays can lengthen
 *   qualification.
 */
static void sensors_check(void)
{
    static unsigned char hall_count = 0; /* Consecutive processed samples with magnet present. */
    /* Consecutive processed samples with comparator reporting sufficient water. */
    static unsigned char wet_count = 0;

    if (!(P2IN & HALL_BIT)) { /* Hall LOW is the active magnet-present state. */
        if (hall_count < 5) ++hall_count; /* Saturate the arrival sample counter at five. */
        /* Publish a new arrival only after qualification, once per state change. */
        if (hall_count >= 5 && !robot_docked) {
            robot_docked = 1; /* Set the qualified docking status. */
            P1OUT |= BIT0; /* Turn on the LaunchPad P1.0 dock indicator. */
            uart_send("Robot docked: magnet detected\r\n");
        }
    } else {
        hall_count = 0; /* A Hall HIGH breaks the consecutive present-sample sequence. */
        if (robot_docked) { /* Send departure feedback only when changing from docked to absent. */
            robot_docked = 0; /* Clear the qualified docking status on this HIGH sample. */
            P1OUT &= ~BIT0; /* Turn off the LaunchPad dock LED without changing the pump bit. */
            uart_send("Robot left: magnet removed\r\n");
        }
    }

    if (!(P3IN & WATER_OK_BIT)) { /* Comparator LOW is interpreted as low station reservoir water. */
        wet_count = 0; /* A low reading interrupts the consecutive-water-OK recovery sequence. */

        if (!water_known || !reservoir_low) { /* Raise/log a new alarm or establish the initial low-water state. */
            reservoir_low = 1; /* Set the reservoir alarm state. */
            water_known = 1; /* Record that an initial low/OK state has now been established. */
            water_led(1); /* Start the visual warning with the P1.2 Booster LED. */
            uart_send("WARNING: WATER LEVEL LOW - REFILL NEEDED\r\n");
        }
    } else {
        if (wet_count < 3) ++wet_count; /* Require three processed HIGH samples before clearing the warning. */
        if (wet_count >= 3) { /* Accept sufficient water after the recovery qualification. */
            reservoir_low = 0; /* Clear the low-water warning; this does not itself restart pumping. */
            water_known = 1; /* Record that an initial low/OK state has now been established. */
            water_led(0); /* Clear all four alarm LEDs; also used when sufficient water is confirmed. */
        }
    }
}

/* main()
 * Purpose: Initialise peripherals, then repeatedly service scheduled work.
 * Parameters: None.
 * Returns/effects: Does not normally return; the while(1) loop runs continuously.
 * Operation: Timer ISRs handle tick scheduling and pump cutoffs. The foreground handles
 *   qualification, state updates, UART and LCD; it busy-waits instead of entering a low-power
 *   mode.
 */
int main(void)
{
    WDTCTL = WDTPW | WDTHOLD; /* Write the watchdog password and hold bit to prevent watchdog resets. */
    gpio_init(); /* Configure inputs/outputs first so pump command starts OFF. */

    /* Change only ACLK selection to nominal 32768 Hz REFO; leave MCLK at reset default. */
    UCSCTL4 = (UCSCTL4 & ~SELA_7) | SELA__REFOCLK;
    uart_init(); /* Prepare PC event logging before any startup messages. */

    P6SEL &= ~0x7F; /* Select GPIO for LCD data/control bits P6.0 through P6.6. */
    P6OUT &= ~0x7F; /* Preload LCD signals LOW, including RW for write-only access. */
    P6DIR |= 0x7F; /* Drive the seven LCD signals as outputs. */
    lcdinit(); /* Perform the LCD power-up handshake and configuration commands. */
    lcdcmd(0x0C); /* Display ON, cursor OFF, cursor blink OFF. */
    lcd_line(0, "DOCK LCD TEST"); /* Show the startup title on the first LCD row. */
    lcd_line(1, "Starting..."); /* Show the startup status on the second row. */
    /* Approximately one-second startup display delay; pump is OFF and timers not started yet. */
    __delay_cycles(1000000);
    lcd_update(); /* Refresh the visible state from the current software flags. */

    TA0CCR0 = 3277 - 1; /* 3277 ACLK counts at nominal 32768 Hz give about 100.006 ms per tick. */
    TA0CCTL0 = CCIE; /* Enable Timer A0 CCR0 interrupts and clear any old compare flag. */
    TA0CTL = TASSEL_1 | MC_1 | TACLR; /* Start Timer A0 from ACLK in up mode after clearing its count. */
    __enable_interrupt(); /* Allow timer ISRs to run; subsequent foreground operations can be interrupted. */
    uart_send("Dock USB relay required. Undock first to arm.\r\n");
    sensors_check(); /* Sample/qualify Hall and water states; report changes and update indicators. */
    lcd_update(); /* Refresh the visible state from the current software flags. */
    while (1) { /* Run continuously; no low-power sleep instruction is used. */
        __disable_interrupt(); /* Begin a critical section so ISR and foreground updates cannot interleave here. */
        if (tick_pending) { /* Check/consume the shared flag atomically to avoid losing a new ISR request here. */
            tick_pending = 0; /* Consume the pending foreground-work request. */
            /* Allow timer ISRs to run; subsequent foreground operations can be interrupted. */
            __enable_interrupt();
            sensors_check(); /* Sample/qualify Hall and water states; report changes and update indicators. */
            pump_test_update(); /* Advance arming/countdown/pump-start logic and report stop events. */
            water_blink_tick(); /* Update the nonblocking four-LED alarm phase. */
            lcd_update(); /* Refresh the visible state from the current software flags. */
        } else {
            /* Allow timer ISRs to run; subsequent foreground operations can be interrupted. */
            __enable_interrupt();
        }
    }
}
