# MSP430 robot supervisor — Zumo

**18 November update — firmware versions installed:** 5 cm STOP / 7 cm clearance;
blue-target stop → 3-second spray → token-matched continuation. Uno OG4 raises
the positive turn limit to 250 while straight speed stays 150. Pump gate P1.6,
raw water ADC P6.0. The pump driver is disabled until its electrical rating is
verified. Read [the current cycle/pump guide](PUMP_SETUP.md). MSP 5 cm / 7 cm pump-disabled firmware and Pico V3 are installed/verified.
The user-installed Uno OG4 is confirmed by its serial banner. FireBeetle V2
is flashed/hash-verified and identified over USB. Reconnect/power the MSP for a
full link check. Pump output remains disabled pending driver qualification;
physical spraying is not ready. The earlier installed milestone is history below.

## Previous installed milestone — 17 November 2026

The MSP430F5529 is the main controller. It grants calibration/following to the
Uno and issues STOP for valid near obstacles, local S2 and communications faults.
The user confirmed the current setup working on **17 November 2026**.

## Current sonar policy

| Setting | Value |
| --- | --- |
| Valid near STOP trigger | **≤2 cm** |
| Clear recent near inhibit | **Two readings ≥4 cm** |
| Expire old near data | **3 × 100 ms ticks** without a fresh valid reading |
| Missing / invalid / stale echo, including startup | Diagnostic fault only; motion allowed with MSP grant |
| Automatic start/restart | Disabled |

The policy is in [obstacle_guard.h](obstacle_guard.h); measurement/Timer_A2/Port2
handling is in [ultrasonic_hcsr04.h](ultrasonic_hcsr04.h). Accepted range is
2–400 cm. A disconnected/failed sonar cannot stop motion under this policy.
The 2 cm setting is a trigger, not a measured physical braking distance.
The Uno still enforces its 1000 ms grant lease and local/frame/session stops.

## Pins and matching firmware

| MSP pin | Connection |
| --- | --- |
| P3.3 TX | Uno D6 RX |
| P3.4 RX | Uno D13 TX via separate 2.2 kΩ / 2.2 kΩ divider |
| P4.1 TX / P4.2 RX | FireBeetle GPIO16 RX / GPIO17 TX; 3.3 V UART |
| P3.2 | HC-SR04 TRIG |
| P2.7 | HC-SR04 ECHO via 2.2 kΩ / 3.3 kΩ divider |
| P6.0 | Water sensor S; ADC not implemented |
| GND | Common ground for all boards and sensors |

Use [the Zumo guide](../../Arduino_Uno/zumo_line_follow/README.md) for complete
divider orientation and operation. The matching Uno source is **zumo_line_follow**,
firmware **OG3**. No L298N/two-IR wiring is used; pump/driver are unconnected.

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo
python Car/MSP430/tests/check_supervisor_logic.py
python Car/MSP430/tests/check_ultrasonic.py
python Car/Arduino_Uno/tests/check_zumo.py
```

Commands run from the repo root and do not upload. The build produces ignored
`Debug_wifi_zumo/robot_supervisor.out`, using TI compiler 21.6.3.LTS. CCS GUI
requires `SUPERVISOR_ESP_UART` and `ZUMO_BASE=1`; the old IR-only sonar bypass is
rejected for Zumo. The shared protocol header remains outside this project in
`Car/Arduino_Uno/msp_line_follow/robot_link.h`; retain the repository layout.

## Diagnostics and installed status

In this build, UART1 is remapped to P4.1/P4.2 for ESP, so the eZ-FET USB UART
console is isolated. USB still supplies/debugs/programs the board. Do not expect
the default USB-console build's serial walkthrough to work on this configuration.
`SONAR` diagnostics include `NO_ECHO_STOP=OFF`; missing/stale range reports
`valid=0/fault=1` after the timeout. Link and console UART errors are counted separately.

Console replies use [console_tx.h](console_tx.h) so long status output does not
block obstacle service. STOP is applied before Uno acknowledgement; clear range
only removes an inhibit and does not issue START. A Zumo button release requests
calibration or following through the framed link; the MSP authorises it.

The no-echo update was flashed/program-verified on 17 November. Clean stopped
readback showed about 23 seconds without an echo, `inhibit=0`, Uno link ready
and zero UART errors. The user subsequently reported the robot working.
See [installed-image evidence](../../../Laptop/Artifacts/verification/msp430-no-echo-ignore-2026-11-17.json).
Physical braking distance and calibrated range accuracy remain unmeasured.

Cleanup builds do not replace installed firmware. The known installed `.out`
and matching map are retained locally under ignored
`build-installed-working-2026-11-17/`; use matching symbols for later debugging.

[Previous L298N supervisor guide](LEGACY_L298N.md) and
[12 November ultrasonic test history](ULTRASONIC_SETUP.md) retain dated results
and old pins. They do not describe the current Zumo operating procedure.
