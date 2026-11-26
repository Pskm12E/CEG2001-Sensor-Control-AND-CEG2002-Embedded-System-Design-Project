"""Exercise real console enqueue/ISR code with USCI interrupt-flag behavior.

Reading UCA1IV acknowledges TXIFG. An idle ISR can therefore leave TXIFG clear;
the next software burst must explicitly restart transmission. No hardware used.
"""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
source=(ROOT/'Car/MSP430/robot_supervisor/main.c').read_text()


def function(prefix):
    start=source.index(prefix)
    brace=source.index('{',start)
    end,depth=brace+1,1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}')
        end+=1
    return source[start:end]+'\n'


prefix=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <string>
#include "console_tx.h"
#define __interrupt
#define __bic_SR_register_on_exit(x) ((void)(x))
enum { UCTXIE=2,UCTXIFG=2,UCRXIE=1,UCRXERR=4,UCFE=8,UCOE=16,UCPE=32,UCBRK=64,LPM0_bits=0 };
static uint8_t UCA1IE=UCRXIE,UCA1IFG=UCTXIFG,UCA1STAT,UCA1RXBUF;
static uint16_t UCA1IV,ticks;
static uint8_t UCA0IFG=UCTXIFG,UCA0TXBUF;
static bool interrupts=true,busy=false,servicing=false;
static ConsoleTx consoleTx={};
static int usbRx;
static std::string transmitted;
static void receive(int*,uint8_t,uint8_t) {}
static void service();
static void __disable_interrupt() { interrupts=false; }
static void __enable_interrupt() { interrupts=true; service(); }
struct TxBuffer {
    void operator=(uint8_t byte) {
        assert(!busy); // A spurious flag must not overwrite an occupied TX buffer.
        transmitted+=char(byte); busy=true; UCA1IFG&=~UCTXIFG;
    }
} UCA1TXBUF;
'''
tests=r'''
static void service() {
    if(servicing || !interrupts) return;
    servicing=true;
    for(unsigned n=0;n<2000 && (UCA1IE&UCTXIE) && (UCA1IFG&UCTXIFG);++n) {
        UCA1IFG&=~UCTXIFG; // UCA1IV read automatically acknowledges this flag.
        UCA1IV=4;
        interrupts=false; usb_uart_isr(); interrupts=true;
        if(busy) { busy=false; UCA1IFG|=UCTXIFG; } // Hardware finishes this byte.
    }
    servicing=false;
}
static unsigned checks;
#define CHECK(x) do { if(!(x)) { std::fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); return 1; } ++checks; } while(0)
int main(int argc,char**) {
    CHECK(put(0,'A') && put(0,'B')); service();
    CHECK(transmitted=="AB" && !(UCA1IE&UCTXIE) && !(UCA1IFG&UCTXIFG));
    CHECK(put(0,'C') && put(0,'D')); service();
    if(argc>1) {
        CHECK(transmitted=="AB" && consoleTx.head!=consoleTx.tail);
        std::printf("REPRODUCED: second console burst stalls after idle TX interrupt acknowledgement.\n");
        return 0;
    }
    CHECK(transmitted=="ABCD" && consoleTx.head==consoleTx.tail);
    for(unsigned i=0;i<2048;++i) {
        CHECK(put(0,uint8_t('a'+i%26))); service();
        CHECK(transmitted.size()==5+i && consoleTx.head==consoleTx.tail);
    }
    CHECK(!(UCA1IE&UCTXIE) && !(UCA1IFG&UCTXIFG));
    CHECK(put(1,0x55) && UCA0TXBUF==0x55); // Uno link behavior unchanged.
    // Full queue refuses promptly and leaves interrupts enabled.
    for(unsigned i=0;i<511;++i) CHECK(consoleTxPush(&consoleTx,uint8_t(i)));
    CHECK(!put(0,42) && interrupts);
    std::printf("PASS %u actual console/ISR idle-restart, FIFO-wrap, no-overwrite and full-queue assertions.\n",checks);
}
'''
build=ROOT/'Car/MSP430/build/console-interrupt-tests'
build.mkdir(parents=True,exist_ok=True)
cpp,exe=build/'console.cpp',build/'console.exe'
cpp.write_text(prefix+function('static uint8_t put(')+function('__interrupt void usb_uart_isr(')+tests,encoding='utf-8')
subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',
                '-Wno-unused-function','-static','-I'+str(ROOT/'Car/MSP430/robot_supervisor'),str(cpp),'-o',str(exe)],check=True)
subprocess.run([str(exe)]+(['--expect-stall'] if '--expect-stall' in sys.argv else []),check=True)
