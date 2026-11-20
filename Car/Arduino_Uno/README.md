# Car Arduino Uno — Zumo line following

**Uno OG6 adds a switchable flip alarm.** Hold the parked Zumo's user button for
two seconds to turn it off or on. [Flip alarm controls](zumo_line_follow/README.md#flip-alarm)

The six-sensor array follows a black line. A short press requests calibration
on startup and line following after calibration. Pressing during motion or an
obstacle pause stops the run. Straight speed is 150 and the outside-track turn
limit is 250.

The MSP430 pauses the Zumo at 5 cm or closer. Resuming that run requires two
consecutive valid readings of at least 7 cm. The Uno receives MSP commands on
D6 and replies on D13 at 9600 baud. [Wiring and button sequence](zumo_line_follow/README.md)

Compile and run host checks from the repository root:

```powershell
./Car/Arduino_Uno/build_zumo.ps1
python Car/Arduino_Uno/tests/check_zumo.py
```

Use the matching MSP `-EspUart -Zumo` build. See the linked Zumo guide for full
wiring, USB commands, source ZIP and stopping-policy limits.

## Earlier sketches

[Previous L298N setup and test history](LEGACY_L298N.md) is retained separately.
`line_follow_car`, `msp_line_follow`, `ir_line_test`, `ir_analog_calibration` and
`uart_link_bench` belong to earlier bases/bench work. Their pins, baud rates and
motor assumptions differ; do not upload them to the current Zumo. The canonical
framed-link header remains in `msp_line_follow/robot_link.h` for compatibility.
