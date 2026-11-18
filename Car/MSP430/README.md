# Car MSP430 — main controller

**Temporary bench mode, 18 November:** the standalone
[P1.6 voltage test](pump_voltage_test/README.md) is currently installed and running.
MSP S2 starts a three-second GPIO pulse with red LED1 blinking and the pump
disconnected. The robot
supervisor must be restored before driving; UART supervision and ultrasonic
stopping are unavailable in this bench program. Keep motor power off.

**18 November update — firmware versions installed:** 5 cm STOP / 7 cm clearance;
blue-target stop → 3-second spray → token-matched continuation. Uno OG4 raises
the positive turn limit to 250 while straight speed stays 150. Pump gate P1.6,
raw water ADC P6.0. The pump driver is disabled until its electrical rating is
verified. Read [the current cycle/pump guide](robot_supervisor/PUMP_SETUP.md). MSP 5 cm / 7 cm pump-disabled firmware and Pico V3 are installed/verified.
The user-installed Uno OG4 is confirmed by its serial banner. FireBeetle V2
is flashed/hash-verified and identified over USB. The MSP UART idle-restart
fix is installed; live robot links are verified while stopped, with zero UART
errors. Calibration is needed. Pump remains disabled pending driver qualification;
physical spraying is not ready. The earlier installed milestone is history below.

For a separate **P1.6 control-voltage check**, see
[pump_voltage_test](pump_voltage_test/README.md). It uses MSP S2 for a 3-second
GPIO pulse with the pump disconnected. Installing it temporarily replaces the
supervisor; creating/building it does not change the running robot.

## Previous installed milestone — 17 November 2026

Board: **MSP-EXP430F5529LP**. Current source:
[robot_supervisor/main.c](robot_supervisor/main.c), built for **ESP UART + Zumo**.
The user confirmed the driving setup working on 17 November 2026.

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo
```

This compiles only; it produces ignored
`robot_supervisor/Debug_wifi_zumo/robot_supervisor.out`. Paths use the original
Windows CCS installation. In CCS GUI define `SUPERVISOR_ESP_UART` and `ZUMO_BASE=1`.

The supervisor owns movement grants, HC-SR04 range and STOP/timeout handling.
**Current STOP trigger: valid measured range ≤2 cm.** Two readings ≥4 cm clear
a recent near inhibit. Missing/invalid/stale echoes do not block movement;
old near data expires after about 300 ms. Manual and communication STOP remain,
and no clearance/fault recovery automatically restarts the car. These are
configured thresholds, not measured physical braking distances.

Use [the supervisor guide](robot_supervisor/README.md) for sources/diagnostics
and [the Zumo guide](../Arduino_Uno/zumo_line_follow/README.md) for full wiring
and the button sequence. The installed no-echo update was flashed and verified;
the source cleanup does not flash a replacement image.

Water S → P6.0 / ADC A0 is wired but ADC logic is pending. Pump/driver are not
connected. The MSP does not run YOLO or camera processing.

`robot_led_test` and `robot_usb_console` are earlier bench programs; flashing one
replaces the supervisor. [Historical IR-only test notes](LEGACY_L298N.md) and
[previous supervisor instructions](robot_supervisor/LEGACY_L298N.md) are retained
for the L298N base. `-Zumo -IrDrivingTest` is deliberately rejected.
