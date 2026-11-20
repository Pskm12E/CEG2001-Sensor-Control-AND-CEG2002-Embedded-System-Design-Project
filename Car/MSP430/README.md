# Car MSP430 — main controller

**Installed and program-verified, 20 November 2026.** The normal ESP-UART/Zumo
supervisor is running with the three-second P1.6 pump profile enabled. It replaces
the standalone LED diagnostic. The user confirmed the pump running and stopping
in two bench tests. Live Pico/ESP/MSP/Uno checks report `READY=1`, `PUMP=0`,
`RUN=0`, Uno ready and zero communication errors.

Confirmed target jobs stop the Zumo, wait for its acknowledgement and settling,
spray for three seconds, turn the pump off and resume after a fresh matching
camera continuation. Sonar remains **5 cm STOP / 7 cm clearance**. Raw water ADC
uses P6.0. See [the cycle/pump guide](robot_supervisor/PUMP_SETUP.md).
The full physical moving target-cycle trial remains pending.

For a separate **P1.6 control-voltage check**, see
[pump_voltage_test](pump_voltage_test/README.md). It uses MSP S2 for a 3-second
GPIO pulse with the pump disconnected. Installing it temporarily replaces the
supervisor; creating/building it does not change the running robot.

## Coursework minimums in the normal robot firmware

The `-EspUart -Zumo` supervisor meets the minimum requirements independently of
the temporary S2 debug control.

| Requirement | Functional implementation |
| --- | --- |
| Two timers | Timer_A0 for system timing and pump cutoff; Timer_A2 for ultrasonic timing |
| Two interrupts | Five handlers cover USCI_A0, USCI_A1, TIMER0_A0, TIMER2_A0 and PORT2 |
| One ADC | ADC12 channel A0 reads the water sensor on P6.0 |
| One power-saving mode | LPM0 idle sleep with interrupt wakeup |

Timer_A1 and the PORT1/TIMER1_A0 handlers also exist for S2 debugging. S2 is
scheduled for later removal. The standalone LED diagnostic uses fixed delays
and does not exercise these coursework features.

## Previous installed milestone — 17 November 2026

Board: **MSP-EXP430F5529LP**. Current source:
[robot_supervisor/main.c](robot_supervisor/main.c), built for **ESP UART + Zumo**.
The user confirmed the driving setup working on 17 November 2026.

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo -PumpDriverVerified -SpraySeconds 3
```

This compiles only; it produces ignored
`robot_supervisor/Debug_wifi_zumo_pump/robot_supervisor.out`. Paths use the original
Windows CCS installation. In CCS GUI define `SUPERVISOR_ESP_UART`, `ZUMO_BASE=1`
and `PUMP_DRIVER_VERIFIED=1` for the installed pump profile.

The supervisor owns movement grants, HC-SR04 range and STOP/timeout handling.
**Current STOP trigger, updated 18 November, is a valid range ≤5 cm.** Two readings ≥7 cm clear
a recent near inhibit. Missing/invalid/stale echoes do not block movement;
old near data expires after about 300 ms. With the matching Uno OG5 firmware,
line following resumes from an acknowledged obstacle pause after two consecutive
valid readings at least 7 cm away. Manual and communication stops cancel the
pause. These thresholds are configurable. Physical braking distance is unmeasured.

Use [the supervisor guide](robot_supervisor/README.md) for sources/diagnostics
and [the Zumo guide](../Arduino_Uno/zumo_line_follow/README.md) for full wiring
and the button sequence. The installed no-echo update was flashed and verified;
the source cleanup does not flash a replacement image.

Water S → P6.0 / ADC A0 is sampled once per second as raw 12-bit data. The pump
driver is connected to P1.6 and short bench operation is confirmed. The MSP does not run YOLO or camera processing.

`robot_led_test` and `robot_usb_console` are earlier bench programs; flashing one
replaces the supervisor. [Historical IR-only test notes](LEGACY_L298N.md) and
[previous supervisor instructions](robot_supervisor/LEGACY_L298N.md) are retained
for the L298N base. `-Zumo -IrDrivingTest` is deliberately rejected.
