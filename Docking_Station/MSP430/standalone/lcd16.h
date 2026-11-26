/*
 * Public declarations and control-pin masks for the supplied LCD driver.
 * Original header created 1 December 2011; Gaurav, www.circuitvalley.com.
 * Documentation revision: 2026-11-24; declarations and definitions unchanged.
 * Include this header in source files that call the declared LCD functions.
 * The original header omits lcdcmd(); main.c declares it locally as before.
 */

/* Include guard: skip these declarations if the header was already included. */
#ifndef MSP_EXP430F5529LP_LCD16X2_LCD16_H_
#define MSP_EXP430F5529LP_LCD16X2_LCD16_H_ /* Mark this header as included for the current compilation unit. */

#include <msp430f5529.h> /* Device-specific register definitions and BIT masks. */

#define  RS BIT4 /* P6.4 register-select: LOW for instruction, HIGH for character data. */
#define  RW BIT5 /* P6.5 read/write: held LOW for writes by this driver. */
#define  EN BIT6 /* P6.6 enable: pulsed once for each four-bit transfer. */

void waitlcd(unsigned int x); /* Legacy nested-loop delay; x is an uncalibrated loop count. Returns no value. */

void lcdinit(void); /* Initialise four-bit LCD operation. No arguments or return value. */
/* Print integer as five decimal digits, including leading zeros. Returns nothing. */
void integerToLcd(unsigned int integer );
void lcdData(unsigned char l); /* Write one character code l at the cursor. Returns nothing. */
void prints(char *s); /* Write zero-terminated string s without line padding. Returns nothing. */
/* Set cursor: x=0..39; y=0 first row, nonzero second row. Returns nothing. */
void gotoXy(unsigned char  x,unsigned char y);

#endif /* End the include guard. */
