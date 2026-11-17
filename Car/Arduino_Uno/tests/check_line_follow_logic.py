"""Evaluate control-logic assertions at C++ compile time; no test EXE is run."""
from pathlib import Path
import subprocess

project = Path(__file__).resolve().parents[1]
source = (project / "line_follow_car" / "line_follow_car.ino").read_text(encoding="utf-8")
start = source.index("// BEGIN CONTROL LOGIC")
end = source.index("// END CONTROL LOGIC")

checks = r'''
static_assert(steerFor(false, false) == FORWARD, "both white -> forward");
static_assert(steerFor(true, false) == TURN_RIGHT, "left black border -> steer right");
static_assert(steerFor(false, true) == TURN_LEFT, "right black border -> steer left");
static_assert(steerFor(true, true) == STOP, "both black -> stop, never guess");
static_assert(motorOutputFor(FORWARD, true) == FORWARD, "reversal keeps forward unchanged");
static_assert(motorOutputFor(STOP, true) == STOP, "reversal keeps stop unchanged");
static_assert(motorOutputFor(TURN_LEFT, true) == TURN_RIGHT, "reverse left turn outputs");
static_assert(motorOutputFor(TURN_RIGHT, true) == TURN_LEFT, "reverse right turn outputs");
static_assert(motorOutputFor(FORWARD, false) == FORWARD, "standard forward unchanged");
static_assert(motorOutputFor(STOP, false) == STOP, "standard stop unchanged");
static_assert(motorOutputFor(TURN_LEFT, false) == TURN_LEFT, "standard left retained");
static_assert(motorOutputFor(TURN_RIGHT, false) == TURN_RIGHT, "standard right retained");
static_assert(leftWheelOn(FORWARD) && rightWheelOn(FORWARD), "both forward");
static_assert(!leftWheelOn(TURN_LEFT) && rightWheelOn(TURN_LEFT), "left turn wheels");
static_assert(leftWheelOn(TURN_RIGHT) && !rightWheelOn(TURN_RIGHT), "right turn wheels");
static_assert(!leftWheelOn(STOP) && !rightWheelOn(STOP), "stop both");
static_assert(!contrast(-1, 1) && !contrast(0, -1), "missing calibration blocked");
static_assert(!contrast(1, 1) && !contrast(0, 0), "stuck signals blocked");
static_assert(blackReading(1, 0, 1) && !blackReading(0, 0, 1), "high means black");
static_assert(blackReading(0, 1, 0) && !blackReading(1, 1, 0), "low means black");
static_assert(!blackReading(1, 1, 1) && !blackReading(0, -1, 0), "no false black before calibration");
static_assert(whiteReading(0, 0, 1) && !whiteReading(1, 0, 1), "low means white");
static_assert(whiteReading(1, 1, 0) && !whiteReading(0, 1, 0), "high means white");
static_assert(!whiteReading(0, 0, 0) && !whiteReading(0, 0, -1), "no false white before calibration");
static_assert(steerFor(blackReading(0, 0, 1), blackReading(1, 1, 0)) == FORWARD, "independent polarity both white");
static_assert(steerFor(blackReading(1, 0, 1), blackReading(1, 1, 0)) == TURN_RIGHT, "independent polarity left black");
static_assert(steerFor(blackReading(0, 0, 1), blackReading(0, 1, 0)) == TURN_LEFT, "independent polarity right black");
static_assert(!expired(499, UINT32_MAX - 499, 1000), "timer before wrapped deadline");
static_assert(expired(500, UINT32_MAX - 499, 1000), "timer at wrapped deadline");
'''
build = project / "build"
build.mkdir(exist_ok=True)
test_source = build / "line_follow_logic_checks.cpp"
test_source.write_text(
    "#include <cstdint>\n" + source[start:end] + checks,
    encoding="utf-8",
)
subprocess.run(
    [r"C:\msys64\ucrt64\bin\g++.exe", "-std=c++11", "-Wall", "-Wextra",
     "-Werror", "-fsyntax-only", str(test_source)], check=True,
)
print(f"PASS: {checks.count('static_assert')} compile-time checks evaluated on actual sketch control logic.")
