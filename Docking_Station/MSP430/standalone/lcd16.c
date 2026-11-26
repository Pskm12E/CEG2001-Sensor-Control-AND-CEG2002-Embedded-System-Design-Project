/*
 * 16x2 character LCD driver - four-bit, write-only interface.
 * Original supplied driver: Gaurav, www.circuitvalley.com.
 * Existing AI adaptations: explicit EN pulse timing and four-bit startup.
 * Documentation revision: 2026-11-24; executable statements unchanged.
 * D4-D7 use P6.0-P6.3; RS=P6.4, RW=P6.5, EN=P6.6.
 * Each byte is sent high nibble first, then low nibble; RW remains LOW.
 * Delays assume reset-default MCLK approximately 1 MHz; no busy flag is read.
 * Delay values are intended allowances, not measured LCD hardware timings.
 * waitlcd(), prints() and integerToLcd() remain available but are not called
 * by the current docking main.c. Existing source attribution is retained.
 */

#include "lcd16.h"

/* lcd_nibble()
 * Purpose: Send the low four bits of value to the LCD data bus.
 * Parameters: value: nibble in bits 0..3; higher bits are ignored.
 * Returns/effects: None; pulses EN while preserving RS and other upper port bits.
 * Operation: RW stays LOW. Delay cycles provide data setup, EN HIGH pulse width and settling
 *   after EN falls.
 */
static void lcd_nibble(unsigned char value)
{
    P6OUT &= ~(EN | RW); /* Keep EN LOW before changing data and force write-only mode. */
    /* Replace only the four data bits; preserve the upper control bits including RS. */
    P6OUT = (P6OUT & 0xF0u) | (value & 0x0Fu);
    __delay_cycles(10); /* Short setup/pulse/hold allowance (about 10 us at 1 MHz). */
    P6OUT |= EN; /* Raise enable so the LCD sees a valid data/command nibble. */
    __delay_cycles(10); /* Short setup/pulse/hold allowance (about 10 us at 1 MHz). */
    P6OUT &= ~EN; /* Lower enable to complete the nibble transfer. */
    __delay_cycles(10); /* Short setup/pulse/hold allowance (about 10 us at 1 MHz). */
}

/* lcdcmd()
 * Purpose: Send an LCD instruction rather than a displayed character.
 * Parameters: cmd: controller command byte.
 * Returns/effects: None.
 * Operation: RS=0 selects the instruction register. Clear/home need a longer delay than
 *   ordinary commands; this driver does not poll the busy flag.
 */
void lcdcmd(unsigned char cmd)
{
    P6OUT &= ~(RS | RW); /* RS LOW selects instruction register; RW LOW selects write. */
    lcd_nibble(cmd >> 4); /* Send the upper four bits of the command first. */
    lcd_nibble(cmd); /* Then send the lower four bits; lcd_nibble masks the upper bits away. */
    /* Clear display / return home need a longer processing allowance (about 3 ms). */
    if (cmd == 0x01 || cmd == 0x02) __delay_cycles(3000);
    else __delay_cycles(100); /* Allow about 100 us for an ordinary command. */
}

/* lcdData()
 * Purpose: Send one character byte to the current LCD cursor position.
 * Parameters: data: character code to display.
 * Returns/effects: None; the LCD normally advances its cursor automatically.
 * Operation: RS=1 selects the data register. Send upper/lower nibbles in order and allow
 *   processing time.
 */
void lcdData(unsigned char data)
{
    P6OUT &= ~RW; /* Keep the bus in write mode; no LCD data/busy flag is read. */
    P6OUT |= RS; /* RS HIGH selects a displayed character rather than an instruction. */
    lcd_nibble(data >> 4); /* Send the upper nibble of the character byte. */
    lcd_nibble(data); /* Send its lower nibble. */
    __delay_cycles(100); /* Allow character-write processing time before another transfer. */
}

/* lcdinit()
 * Purpose: Initialise the character LCD into four-bit, two-line mode.
 * Parameters: None.
 * Returns/effects: None; clears the display and leaves cursor/blink hidden.
 * Operation: The repeated 0x03 startup nibbles establish a known interface before 0x02 selects
 *   four-bit mode. Later instructions set function, entry and display options.
 */
void lcdinit(void)
{
    P6SEL &= ~0x7Fu; /* Select GPIO on the seven LCD data/control pins. */
    P6OUT &= ~0x7Fu; /* Start data/control outputs LOW, including RW and EN. */
    P6DIR |= 0x7Fu; /* Configure LCD pins as outputs. */
    __delay_cycles(60000); /* Wait about 60 ms for LCD power-up before the startup handshake. */
    lcd_nibble(0x03); /* Repeat the startup function-set nibble to establish a known initial interface. */
    __delay_cycles(6000); /* Long allowance after the first startup nibble (about 6 ms). */
    lcd_nibble(0x03); /* Repeat the startup function-set nibble to establish a known initial interface. */
    __delay_cycles(300); /* Shorter allowance between later startup steps (about 300 us). */
    lcd_nibble(0x03); /* Repeat the startup function-set nibble to establish a known initial interface. */
    __delay_cycles(300); /* Shorter allowance between later startup steps (about 300 us). */
    lcd_nibble(0x02); /* Select four-bit interface; subsequent commands use two nibble transfers. */
    __delay_cycles(300); /* Shorter allowance between later startup steps (about 300 us). */
    lcdcmd(0x28); /* Four-bit data bus, two display lines and 5x8 character font. */
    lcdcmd(0x08); /* Turn display OFF while setup is completed. */
    lcdcmd(0x01); /* Clear display memory and return cursor to the starting position. */
    lcdcmd(0x06); /* Increment cursor after writes; do not automatically shift the display. */
    lcdcmd(0x0C); /* Turn display ON with cursor and blink hidden. */
}

/* waitlcd()
 * Purpose: Retain the original software-delay utility.
 * Parameters: x: loop count; values 0 or 1 produce no outer iterations.
 * Returns/effects: None.
 * Operation: Legacy API, unused by this docking application. Nested loops are not a calibrated
 *   time source and depend on clock/compiler settings.
 */
void waitlcd(volatile unsigned int x)
{
	volatile unsigned int i; /* Retain the inner delay-loop counter rather than optimise it away. */
	for (x;x>1;x--) /* Original outer countdown; its iterations depend on x, not an exact time unit. */
	{
		for (i=0;i<=110;i++); /* Empty inner busy-wait loop; semicolon is intentional in the supplied utility. */
	}
}

/* prints()
 * Purpose: Write a zero-terminated string at the current LCD position.
 * Parameters: str: pointer to the string; the pointer advances after each byte.
 * Returns/effects: None.
 * Operation: This legacy helper does not pad or limit a line to 16 characters. Docking code
 *   instead uses lcd_line().
 */
void prints(char *str)
{
    while (*str) /* Continue until the zero terminator of the string. */
    {
    	lcdData(*str); /* Display the character currently addressed by str. */
    	str++; /* Advance to the next character in the string. */
    }
}

/* gotoXy()
 * Purpose: Position the LCD cursor using its display-memory address.
 * Parameters: x: column 0..39; y: zero for first row, nonzero for second.
 * Returns/effects: None; ignores x >= 40.
 * Operation: Second-row memory starts at 0x40; OR with 0x80 creates a set-DDRAM-address
 *   command. The physical screen exposes only 16 columns per row.
 */
void gotoXy(unsigned char x, unsigned char y)
{
	if(x<40) /* Accept a controller-memory column below 40; visible screen width is only 16. */
	{
		if(y) x |= 0x40; /* For nonzero y, add the second-row DDRAM base address. */
		x |=0x80; /* Set the command bit for assigning a DDRAM cursor address. */
		lcdcmd(x); /* Send the computed cursor-position command. */
	}
}

/* integerToLcd()
 * Purpose: Write an unsigned integer as five decimal digits.
 * Parameters: integer: unsigned value (16-bit on this MSP430).
 * Returns/effects: None; writes all five digits, including leading zeros.
 * Operation: Division and remainder extract each decimal place; adding 0x30 converts a digit to
 *   its ASCII character code. Unused by current main.c.
 */
void integerToLcd(unsigned int integer)
{
	unsigned char tenthousands,thousands,hundreds,tens,ones;

	tenthousands = integer / 10000; /* Extract the ten-thousands decimal digit. */
	lcdData(tenthousands + 0x30); /* Convert that digit to ASCII and display it. */

	thousands = integer % 10000 / 1000; /* Discard higher digits, then extract the thousands digit. */
	lcdData(thousands + 0x30); /* Write the thousands digit, including zero if present. */

	hundreds = integer % 1000 / 100; /* Extract the hundreds digit. */
	lcdData(hundreds + 0x30); /* Write the hundreds digit. */

	tens= integer % 100 / 10; /* Extract the tens digit. */
	lcdData(tens + 0x30); /* Write the tens digit. */

	ones=integer % 10; /* Extract the units digit. */
	lcdData(ones + 0x30); /* Write the units digit, completing the five-character number. */
}
