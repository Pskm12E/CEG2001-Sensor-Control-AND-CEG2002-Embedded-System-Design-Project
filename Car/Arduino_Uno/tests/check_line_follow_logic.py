"""Evaluate control-logic assertions at C++ compile time; no test EXE is run."""
from pathlib import Path
import re
import subprocess

project = Path(__file__).resolve().parents[1]
source = (project / "line_follow_car" / "line_follow_car.ino").read_text(encoding="utf-8")
start = source.index("// BEGIN CONTROL LOGIC")
end = source.index("// END CONTROL LOGIC")
recovery = re.search(r"const uint32_t RECOVERY_MS = (\d+);", source)
assert recovery, "Recovery timeout declaration missing"

checks = r'''
static_assert(steerFor(true, true) == FORWARD, "centred -> forward");
static_assert(steerFor(true, false) == TURN_LEFT, "line on left -> left");
static_assert(steerFor(false, true) == TURN_RIGHT, "line on right -> right");
static_assert(steerFor(false, false) == LOST, "no black -> lost, never forward");
static_assert(leftWheelOn(FORWARD) && rightWheelOn(FORWARD), "both forward");
static_assert(!leftWheelOn(TURN_LEFT) && rightWheelOn(TURN_LEFT), "left turn wheels");
static_assert(leftWheelOn(TURN_RIGHT) && !rightWheelOn(TURN_RIGHT), "right turn wheels");
static_assert(!leftWheelOn(STOP) && !rightWheelOn(STOP), "stop both");
static_assert(!leftWheelOn(LOST) && !rightWheelOn(LOST), "lost alone drives nothing");
static_assert(!contrast(-1, 1) && !contrast(0, -1), "missing calibration blocked");
static_assert(!contrast(1, 1) && !contrast(0, 0), "stuck signals blocked");
static_assert(blackReading(1, 0, 1) && !blackReading(0, 0, 1), "high means black");
static_assert(blackReading(0, 1, 0) && !blackReading(1, 1, 0), "low means black");
static_assert(!blackReading(1, 1, 1) && !blackReading(0, -1, 0), "no false black before calibration");
static_assert(recoveryFor(101, 100, 99, TURN_LEFT) == TURN_LEFT, "recent left recovery");
static_assert(recoveryFor(101, 100, 99, TURN_RIGHT) == TURN_RIGHT, "recent right recovery");
static_assert(recoveryFor(101, 100, 99, STOP) == STOP, "unknown direction stops");
static_assert(recoveryFor(101, 100, 99, FORWARD) == STOP, "no blind forward recovery");
static_assert(recoveryFor(350, 100, 349, TURN_LEFT) == STOP, "recovery deadline enforced");
static_assert(recoveryFor(350, 349, 100, TURN_RIGHT) == STOP, "stale direction rejected");
static_assert(!expired(499, UINT32_MAX - 499, 1000), "timer before wrapped deadline");
static_assert(expired(500, UINT32_MAX - 499, 1000), "timer at wrapped deadline");
static_assert(recoveryFor(32, 0, UINT32_MAX - 15, TURN_LEFT) == TURN_LEFT, "wrapped recent direction");
'''
build = project / "build"
build.mkdir(exist_ok=True)
test_source = build / "line_follow_logic_checks.cpp"
test_source.write_text(
    "#include <cstdint>\nconstexpr uint32_t RECOVERY_MS = "
    + recovery.group(1) + ";\n" + source[start:end] + checks,
    encoding="utf-8",
)
subprocess.run(
    [r"C:\msys64\ucrt64\bin\g++.exe", "-std=c++11", "-Wall", "-Wextra",
     "-Werror", "-fsyntax-only", str(test_source)], check=True,
)
print(f"PASS: {checks.count('static_assert')} compile-time checks evaluated on actual sketch control logic.")
