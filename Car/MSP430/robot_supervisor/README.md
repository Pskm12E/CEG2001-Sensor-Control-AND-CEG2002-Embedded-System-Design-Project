# MSP430 robot supervisor — Zumo

The MSP430F5529 grants calibration and following to the Uno, measures obstacle
range, samples the water probe on P6.0 and controls the three-second pump pulse
on P1.6. Build the ESP-UART/Zumo profile with the pump driver enabled for
`V2_Working`. [Build flags, wiring and spray sequence](PUMP_SETUP.md)

## Current sonar policy

Automatic resume requires the pause acknowledgement introduced in Uno OG5
and supported by the release's OG6 sketch.

| Setting | Value |
| --- | --- |
| Valid near stop trigger | **≤5 cm**. Active line following pauses. A powered calibration stops. |
| Resume from an acknowledged pause | **Two consecutive valid readings ≥7 cm**, with the same healthy Uno session |
| Expire old near data | **3 × 100 ms ticks** without a fresh valid reading |
| Missing / invalid / stale echo | Motion with a local grant is allowed after old near data expires. A paused run waits for valid clearance. |
| Manual stop, link fault, interrupted calibration, or aborted spray | A new local request is required |

The policy is in [obstacle_guard.h](obstacle_guard.h); measurement/Timer_A2/Port2
handling is in [ultrasonic_hcsr04.h](ultrasonic_hcsr04.h). Accepted range is
2–400 cm. A disconnected/failed sonar cannot stop motion under this policy.
The 5 cm setting is a configured trigger. Physical braking distance remains unmeasured.
The Uno still enforces its 1000 ms grant lease and local/frame/session stops.
The pause keeps the Uno session open so a local stop or reboot invalidates the
resume grant. A refused or timed-out pause falls back to a regular STOP.

## Pins and matching firmware

| MSP pin | Connection |
| --- | --- |
| P3.3 TX | Uno D6 RX |
| P3.4 RX | Uno D13 TX via separate 2.2 kΩ / 2.2 kΩ divider |
| P4.1 TX / P4.2 RX | FireBeetle GPIO16 RX / GPIO17 TX; 3.3 V UART |
| P3.2 | HC-SR04 TRIG |
| P2.7 | HC-SR04 ECHO via 2.2 kΩ / 3.3 kΩ divider |
| P1.6 | Pump MOSFET gate; three-second bounded output |
| P6.0 | Water sensor S; raw ADC A0 sampled once per second |
| GND | Common ground for all boards and sensors |

Use [the Zumo guide](../../Arduino_Uno/zumo_line_follow/README.md) for complete
divider orientation and operation. The matching Uno source is **zumo_line_follow**,
firmware **OG6**. The pump driver connects to P1.6.

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo -PumpDriverVerified -SpraySeconds 3
python Car/MSP430/tests/check_supervisor_logic.py
python Car/MSP430/tests/check_ultrasonic.py
python Car/Arduino_Uno/tests/check_zumo.py
```

Commands run from the repo root and do not upload. The build produces ignored
`Debug_wifi_zumo_pump/robot_supervisor.out`, using TI compiler 21.6.3.LTS. CCS GUI
requires `SUPERVISOR_ESP_UART`, `ZUMO_BASE=1` and `PUMP_DRIVER_VERIFIED=1`; the old IR-only sonar bypass is
rejected for Zumo. The shared protocol header remains outside this project in
`Car/Arduino_Uno/msp_line_follow/robot_link.h`; retain the repository layout.

## Diagnostics and installed status

In this build, UART1 is remapped to P4.1/P4.2 for ESP, so the eZ-FET USB UART
console is isolated. USB still supplies/debugs/programs the board. Do not expect
the default USB-console build's serial walkthrough to work on this configuration.
`SONAR` diagnostics include `NO_ECHO_STOP=OFF`; missing/stale range reports
`valid=0/fault=1` after the timeout. Link and console UART errors are counted separately.

Console replies use [console_tx.h](console_tx.h) so long status output does not
block obstacle service. The Uno applies the pause before acknowledging it. The
MSP can then issue one START after confirmed clearance. A Zumo button press
during the pause cancels it. When stopped normally, a button release requests
calibration or following through the framed link.

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

## UART idle-restart correction — 18 November 2026

The queued UART1 transmitter now re-arms TXIFG when starting from idle, before
enabling TXIE. Reading UCA1IV acknowledges the interrupt flag, so enabling TXIE
alone after the final empty-queue interrupt could strand all subsequent replies.
See the [TI USCI UART guide](https://www.ti.com/lit/ug/slau208q/slau208q.pdf),
section 36.3.15.3, and the actual enqueue/ISR regression:

```powershell
python Car/MSP430/tests/check_console_tx_interrupt.py
```

The fixed pump-disabled image is flashed/program-verified. Repeated fresh status
records confirm all robot links ready, stopped motion, disabled pump and no UART
errors. The matching image/map are retained locally under ignored
`build-installed-uart-kick-2026-11-18/`; use these symbols for later debugging.
