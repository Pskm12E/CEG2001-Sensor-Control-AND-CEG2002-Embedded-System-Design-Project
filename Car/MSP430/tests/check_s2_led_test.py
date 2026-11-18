"""Execute the real LED-only main against timed S2 inputs; no device access."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[3]
build=root/'Car/MSP430/build/s2-led-tests'
build.mkdir(parents=True,exist_ok=True)
(build/'msp430.h').write_text(r'''
#include <stdint.h>
#define __MSP430F5529__ 1
#define BIT0 1u
#define BIT1 2u
#define BIT6 64u
#define BIT7 128u
#define WDTPW 0x5a00u
#define WDTHOLD 0x80u
#define SCG0 64u
#define SELREF__REFOCLK 0x20u
#define DCORSEL_2 0x20u
#define FLLD_1 0x1000u
#define SELA__REFOCLK 0x200u
#define SELS__DCOCLKDIV 0x40u
#define SELM__DCOCLKDIV 4u
#define DCOFFG 1u
inline volatile uint8_t P1SEL=0,P1OUT=0,P1DIR=0,P1REN=0,P1IN=0,P4SEL=0,P4OUT=0,P4DIR=0;
inline volatile uint16_t WDTCTL=0,UCSCTL0=0,UCSCTL1=0,UCSCTL2=0,UCSCTL3=0,UCSCTL4=0,UCSCTL5=0,UCSCTL7=0;
void on_delay(unsigned long cycles);
#define __delay_cycles(n) on_delay(n)
#define __bis_SR_register(n) ((void)(n))
#define __bic_SR_register(n) ((void)(n))
''',encoding='utf-8')
source=build/'test.cpp';exe=build/'test.exe'
source.write_text(r'''
#include <cassert>
#include <cstdio>
#include <vector>
#include <utility>
struct End {};
#define main firmware_main
#include "'''+str(root/'Car/MSP430/s2_led_test/main.c').replace('\\','/')+r'''"
#undef main
static unsigned long long cycles=0;
static unsigned checks=0;
static std::vector<std::pair<unsigned long long,bool>> edges;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static bool pressed(double t) {
    return t<.3 || (t>=1.0 && t<5.0) || (t>=6.0 && t<6.1) || (t>=10.5 && t<10.505);
}
void on_delay(unsigned long n) {
    CHECK(!(P1DIR&BIT6));CHECK(!(P1OUT&BIT6));CHECK(P1REN&BIT6);
    bool red=P1OUT&BIT0;
    if(!edges.empty() ? red!=edges.back().second : red)
        edges.push_back({cycles,red});
    if(cycles<300000) { CHECK(!(P4OUT&BIT7));CHECK(!red); }
    cycles+=n;
    if(cycles>11ull*1048576) throw End{};
    if(pressed(double(cycles)/1048576)) P1IN&=~BIT1;
    else P1IN|=BIT1;
}
int main() {
    try { firmware_main(); } catch(End&) {}
    CHECK(s2Presses==2);CHECK(redEdges==24);CHECK(edges.size()==24);
    CHECK(!(P1OUT&BIT0));CHECK(P4OUT&BIT7);
    CHECK(edges[0].first>=1048576); // No startup-held activation.
    CHECK(edges[12].first>=6ull*1048576); // Holding cannot repeat.
    for(unsigned group=0;group<2;group++) {
        for(unsigned i=0;i<12;i++) {
            CHECK(edges[group*12+i].second==(i%2==0));
            if(i) CHECK(edges[group*12+i].first-edges[group*12+i-1].first==262144);
        }
    }
    printf("PASS %u LED-only assertions: real main, debounce, six flashes per press, held input, ready indicator and P1.6 never driven.\n",checks);
}
''',encoding='utf-8')
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++17','-Wall','-Wextra','-Werror','-static',
                '-I'+str(build),str(source),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
