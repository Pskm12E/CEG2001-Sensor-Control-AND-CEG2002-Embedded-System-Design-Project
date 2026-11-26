# Car Arduino Uno — Zumo line following

**Uno OG9** saves the six line-sensor ranges in EEPROM. Hold the parked Zumo's user button for
two seconds to turn the flip alarm off or on. [Flip alarm controls](zumo_line_follow/README.md#flip-alarm)

The six-sensor array follows a black line. A short press requests calibration
on first use and line following once calibration is saved. Pressing during motion or an
obstacle pause stops the run. Straight speed is 90/400 and the outside-track turn
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
wiring, USB commands, and stopping-policy limits.
