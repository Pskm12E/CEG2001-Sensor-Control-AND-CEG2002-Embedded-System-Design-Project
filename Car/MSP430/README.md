# Car MSP430 — main controller

The current supervisor grants motion to the Uno OG9, stops the tracks for
a confirmed target and drives the pump gate on **P1.6 for three seconds**.
The HC-SR04 pauses line following at **5 cm**. Resume requires two consecutive
valid readings of **7 cm or farther**. The P6.0 ADC reports water-probe
readings to the dashboard. [Supervisor build and pump wiring](robot_supervisor/PUMP_SETUP.md)

For a separate **P1.6 control-voltage check**, see
[pump_voltage_test](pump_voltage_test/README.md). It uses MSP S2 for a 3-second
GPIO pulse with the pump disconnected. Installing it temporarily replaces the
supervisor; creating/building it does not change the running robot.

## Coursework minimums in the normal robot firmware

The `-EspUart -Zumo` supervisor meets the minimum requirements with the timer, sensor and communications code identified below.

| Requirement | Functional implementation |
| --- | --- |
| Two timers | Timer_A0 for system timing and pump cutoff; Timer_A2 for ultrasonic timing |
| Two interrupts | Five handlers cover USCI_A0, USCI_A1, TIMER0_A0, TIMER2_A0 and PORT2 |
| One ADC | ADC12 channel A0 reads the water sensor on P6.0 |
| One power-saving mode | LPM0 idle sleep with interrupt wakeup |

P1.1 (S2) requests an immediate stop. Timer_A1 debounces its release before the port interrupt is re-armed.

## Build the car supervisor

Board: **MSP-EXP430F5529LP**. Current source:
[robot_supervisor/main.c](robot_supervisor/main.c), built for **ESP UART + Zumo**.
On 24 November the car MSP430 was flashed and verified by readback with the
calibrated refill threshold of 2104. The physical refill departure is pending.

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
old near data expires after about 300 ms. With the matching Uno OG9 firmware,
line following resumes from an acknowledged obstacle pause after two consecutive
valid readings at least 7 cm away. Manual and communication stops cancel the
pause. These thresholds are configurable. Physical braking distance is unmeasured.

Use [the supervisor guide](robot_supervisor/README.md) for sources/diagnostics
and [the Zumo guide](../Arduino_Uno/zumo_line_follow/README.md) for full wiring
and the button sequence. The installed no-echo update was flashed and verified;
the source cleanup does not flash a replacement image.

Water S → P6.0 / ADC A0 is sampled once per second as raw 12-bit data. The pump
driver is connected to P1.6 and short bench operation is confirmed. The MSP does not run YOLO or camera processing.
