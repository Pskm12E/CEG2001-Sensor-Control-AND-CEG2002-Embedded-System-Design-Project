"""Run the real voltage-test pulse state machine; no serial ports or hardware."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
build = ROOT/'Car/MSP430/build/pump-voltage-tests'
build.mkdir(parents=True, exist_ok=True)
source, exe = build/'pulse_test.cpp', build/'pulse_test.exe'
source.write_text(r'''
#include <cassert>
#include <cstdio>
#include "pulse_test.h"
static unsigned checks;
#define CHECK(x) do { assert(x); ++checks; } while (0)
static void off(PulseTest &p, bool pressed, unsigned ticks) {
    while(ticks--) { CHECK(!pulseTick(&p,pressed));CHECK(!pulseLedOn(&p)); }
}
static void start(PulseTest &p) {
    off(p,false,3); // Startup release arms the button; it never starts a pulse.
    off(p,true,2);
    CHECK(pulseTick(&p,true)); // Starts on the PRESS, before release.
    CHECK(p.remaining==300);
    CHECK(pulseLedOn(&p));
}
int main() {
    PulseTest p={0,0,0};
    off(p,true,500); // A held startup button must never energise the output.
    off(p,false,500);
    // Contact bounce cannot count as a press or trigger the output.
    for(unsigned i=0;i<100;++i) { off(p,true,2); off(p,false,2); }
    start(p);
    unsigned lit=1,transitions=0;bool previous=true;
    for(unsigned i=1;i<300;++i) {
        CHECK(pulseTick(&p,false)); // Gate stays HIGH through every LED blink.
        bool led=pulseLedOn(&p);lit+=led;transitions+=led!=previous;previous=led;
        CHECK(led==((i/25)%2==0));
    }
    CHECK(lit==150 && transitions==11); // Six 2-Hz flashes, no extra gate pulses.
    CHECK(!pulseTick(&p,false));
    CHECK(!pulseLedOn(&p));
    CHECK(p.remaining==0);
    off(p,false,500); // No periodic/automatic pulse after the cutoff.
    // Another press cancels early and cannot retrigger while held.
    start(p);
    for(unsigned i=0;i<3;++i) CHECK(pulseTick(&p,false)); // Release arms cancel.
    CHECK(pulseTick(&p,true));CHECK(pulseTick(&p,true));
    CHECK(!pulseTick(&p,true));
    off(p,true,500);
    off(p,false,500);
    // Holding the original press through expiry cannot retrigger or cancel.
    start(p);
    for(unsigned i=1;i<300;++i) CHECK(pulseTick(&p,true));
    CHECK(!pulseTick(&p,true));off(p,true,500);off(p,false,3);
    // Repeated pulses each require a new press/release and expire exactly once.
    for(unsigned repeat=0;repeat<5;++repeat) {
        start(p);
        for(unsigned i=1;i<300;++i) CHECK(pulseTick(&p,false));
        CHECK(!pulseTick(&p,false));
    }
    // A reset abandons the pulse, including a button held during that reset.
    start(p);p=PulseTest{0,0,0};off(p,true,500);off(p,false,500);
    // Invalid state and exhausted active state fail off instead of underflow.
    p.phase=255;p.remaining=100;CHECK(!pulseTick(&p,false));CHECK(p.remaining==0);
    p.phase=PT_ACTIVE_HELD;p.remaining=0;CHECK(!pulseTick(&p,false));CHECK(p.remaining==0);
    printf("PASS %u pump voltage-test assertions: press trigger, LED blinking, steady gate, cutoff, cancel, reset and no repeat.\n",checks);
}
''', encoding='utf-8')
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++17','-Wall','-Wextra','-Werror','-static',
                '-I'+str(ROOT/'Car/MSP430/pump_voltage_test'),str(source),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
