"""Run the station firmware with simulated GPIO, RX bytes and timer ticks."""
from pathlib import Path
import shutil
import subprocess
import tempfile

project = Path(__file__).resolve().parents[1] / "MSP430/waterlevel"
hardware = """
#pragma once
enum { BIT0=1,BIT1=2,BIT2=4,BIT3=8,BIT4=16,BIT5=32,BIT6=64,
       GIE=1,UCRXERR=1,UCRXIE=1,UCTXIFG=2,CCIE=16,CCIFG=1,
       MC_0=0,MC_1=16,TACLR=4,ID_3=192,TASSEL_1=256,
       WDTPW=1,WDTHOLD=2,SELA_7=7,SELA__REFOCLK=2,
       UCSWRST=1,UCSSEL_1=64,UCBRS_3=6 };
static unsigned P1OUT,P1DIR,P1SEL,P2IN,P2DIR,P2OUT,P2REN,P2SEL,
    P3IN,P3DIR,P3OUT,P3REN,P3SEL,P4SEL,P6DIR,P6OUT,P6SEL,P8DIR,P8OUT,P8SEL;
static unsigned TA0CCR0,TA0CCTL0,TA0CTL,TA1CCR0,TA1CCTL0,TA1CTL,TA1R;
static unsigned UCA1IV,UCA1STAT,UCA1RXBUF,UCA1TXBUF,UCA1CTL0,UCA1CTL1,
    UCA1BR0,UCA1BR1,UCA1MCTL,UCA1IE,UCA1IFG=UCTXIFG,UCSCTL4,WDTCTL;
#define __interrupt
#define __disable_interrupt() ((void)0)
#define __enable_interrupt() ((void)0)
#define __get_SR_register() GIE
#define __delay_cycles(n) ((void)0)
"""
harness = r"""
#include <assert.h>
#include <stdio.h>
#define main station_main
#include "main.c"
#undef main
void lcdinit(void) {}
void lcdcmd(unsigned char c) {}
void lcdData(unsigned char c) {}
void gotoXy(unsigned char x, unsigned char y) {}

static void samples(int present, int water, unsigned count) {
    P2IN = present ? 0 : HALL_BIT;
    P3IN = water ? WATER_OK_BIT : 0;
    while(count--) { sensor_tick_isr(); sensors_check(); pump_test_update(); }
}
static void receive(const char *text) {
    UCA1IV = 2;
    while (*text) { UCA1RXBUF = *text++; dock_rx_isr(); }
}
static void arrive(void) {
    samples(0,1,5); assert(phase==CLEAR);
    samples(1,1,1); assert(phase==ARRIVAL && !robot_docked && !pump_running);
    samples(1,1,4); assert(robot_docked);
}
static void fill(void) {
    char permit[24]; snprintf(permit,sizeof(permit),"HOLD %u\n",visit);
    receive(permit); samples(1,1,1); assert(phase==SETTLE);
    samples(1,1,19); receive(permit); samples(1,1,10);
    assert(!pump_running); samples(1,1,1);
    assert(phase==FILL && (P1OUT&BIT4) && TA1CCR0==40959);
}
int main(void) {
    samples(1,1,50); assert(phase==BOOT && !pump_running);
    arrive(); receive("HOLD 2\nHOLD 65537\nHOLD 1junk\n");
    samples(1,1,40); assert(phase==ARRIVAL && !pump_running);
    fill(); pump_deadline_isr(); samples(1,1,1);
    assert(phase==DONE && !(P1OUT&BIT4)); receive("HOLD 1\n");
    samples(1,1,60); assert(phase==DONE && !pump_running);
    arrive(); receive("HOLD 1\n"); samples(1,1,40); assert(phase==ARRIVAL);
    fill(); samples(1,1,26); assert(phase==FAULT && !(P1OUT&BIT4));
    arrive(); fill(); samples(0,1,1); assert(phase==FAULT && !(P1OUT&BIT4));
    arrive(); fill(); samples(1,0,1); assert(phase==FAULT && !(P1OUT&BIT4));
    arrive(); receive("HOLD 5\n"); samples(1,1,27);
    assert(phase==FAULT && !pump_running);
    puts("PASS station arrival, stopped-car permit, three-second settling, refill cutoff, stale permits, link loss, water and magnet interlocks");
}
"""
with tempfile.TemporaryDirectory() as directory:
    tmp = Path(directory)
    (tmp/"msp430.h").write_text(hardware)
    (tmp/"msp430f5529.h").write_text('#include "msp430.h"\n')
    (tmp/"dock.c").write_text(harness)
    exe = tmp/"dock-test.exe"
    subprocess.run([shutil.which("gcc") or "gcc", "-std=c11", "-I", str(tmp),
                    "-I", str(project), str(tmp/"dock.c"), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
