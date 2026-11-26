"""Exercise the actual bounded job policy; no hardware is opened."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
build = ROOT / "Car/MSP430/build/spray-tests"
build.mkdir(parents=True, exist_ok=True)
source = r'''
#include <cassert>
#include <cstdio>
#include "spray_job.h"
static unsigned checks;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static SprayJob begin(uint16_t now=0) {
    SprayJob s={};
    CHECK(!sprayBegin(&s,now,1,0));
    CHECK(!sprayBegin(&s,now,0,1));
    CHECK(sprayBegin(&s,now,1,1));
    CHECK(!s.pump && !sprayBegin(&s,now,2,1));
    return s;
}
static void settle(SprayJob &s,uint16_t now,uint8_t armed) {
    sprayStopAck(&s,now,1); CHECK(s.phase==SJ_WAIT_LINK && !s.pump);
    sprayTick(&s,now,0,0,armed); CHECK(s.phase==SJ_WAIT_LINK && !s.pump);
    sprayTick(&s,now,1,0,armed); CHECK(s.phase==SJ_SETTLING && !s.pump);
    sprayTick(&s,uint16_t(now+2),1,0,armed); CHECK(!s.pump);
    sprayTick(&s,uint16_t(now+3),1,0,armed);
}
int main() {
    CHECK(PUMP_SPRAY_TICKS==30); // User-selected three-second setting.
    SprayJob s=begin(); settle(s,1,0);
    CHECK(s.phase==SJ_DRIVER_DISABLED && !s.pump && !sprayActive(&s));
    CHECK(!sprayAllowResume(&s,1,1));
    s=begin(); settle(s,1,1);
    CHECK(s.phase==SJ_SPRAYING && s.pump);
    for(uint16_t n=4;n<34;++n) { sprayTick(&s,n,1,0,1); CHECK(s.pump); }
    CHECK(!sprayTick(&s,34,1,0,1));
    CHECK(s.phase==SJ_RESUMING && !s.pump);
    CHECK(!sprayAllowResume(&s,2,1) && !sprayAllowResume(&s,1,0));
    CHECK(sprayAllowResume(&s,1,1) && !sprayAllowResume(&s,1,1));
    sprayResumeAck(&s,1); CHECK(s.phase==SJ_COMPLETE && !s.pump);
    CHECK(!sprayBegin(&s,35,1,1)); // Duplicate job cannot repeat the pump.
    CHECK(sprayBegin(&s,35,2,1) && !s.resumeQueued);
    for(unsigned phase=SJ_STOPPING;phase<=SJ_RESUMING;++phase) {
        s={}; s.phase=phase; s.pump=phase==SJ_SPRAYING;
        sprayCancel(&s); CHECK(s.phase==SJ_ABORTED && !s.pump);
        CHECK(!sprayAllowResume(&s,1,1));
    }
    s=begin(); settle(s,1,1); sprayTick(&s,5,1,1,1);
    CHECK(s.phase==SJ_ABORTED && !s.pump); // Near obstacle cancels during spray.
    s=begin(); settle(s,1,1); sprayTick(&s,5,0,0,1);
    CHECK(s.phase==SJ_ABORTED && !s.pump); // Link/calibration no longer ready.
    s=begin(); sprayStopAck(&s,1,0); CHECK(s.phase==SJ_ABORTED && !s.pump);
    s=begin(); sprayTick(&s,10,0,0,1); CHECK(s.phase==SJ_ABORTED && !s.pump);
    s=begin(); sprayStopAck(&s,1,1); sprayTick(&s,21,0,0,1);
    CHECK(s.phase==SJ_ABORTED && !s.pump);
    s=begin(); settle(s,1,1); sprayTick(&s,34,1,0,1);
    sprayTick(&s,64,1,0,1); CHECK(s.phase==SJ_ABORTED && !s.pump); // No camera continuation.
    s=begin(65530); settle(s,65531,1);
    CHECK(s.pump); sprayTick(&s,28,1,0,1);
    CHECK(!s.pump && s.phase==SJ_RESUMING); // Tick rollover.
    printf("PASS %u bounded spray-job, interlock, disabled-driver, no-replay and continuation assertions.\n",checks);
}
'''
cpp, exe = build / "spray.cpp", build / "spray.exe"
cpp.write_text(source, encoding="utf-8")
subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-static",
                "-I" + str(ROOT / "Car/MSP430/robot_supervisor"), str(cpp), "-o", str(exe)], check=True)
subprocess.run([str(exe)], check=True)
