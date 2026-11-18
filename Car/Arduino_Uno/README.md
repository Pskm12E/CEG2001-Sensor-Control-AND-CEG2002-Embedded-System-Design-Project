# Car Arduino Uno — Zumo line following

**18 November update — firmware versions installed:** 5 cm STOP / 7 cm clearance;
blue-target stop → 3-second spray → token-matched continuation. Uno OG4 raises
the positive turn limit to 250 while straight speed stays 150. Pump gate P1.6,
raw water ADC P6.0. The pump driver is disabled until its electrical rating is
verified. Read [the current cycle/pump guide](../MSP430/robot_supervisor/PUMP_SETUP.md). MSP 5 cm / 7 cm pump-disabled firmware and Pico V3 are installed/verified.
The user-installed Uno OG4 is confirmed by its serial banner. FireBeetle V2
is flashed/hash-verified and identified over USB. Reconnect/power the MSP for a
full link check. Pump output remains disabled pending driver qualification;
physical spraying is not ready. The earlier installed milestone is history below.

## Previous installed milestone — 17 November 2026

Use **[zumo_line_follow](zumo_line_follow/README.md)** for the current
Uno + Zumo Shield robot. The user confirmed it working on 17 November 2026.
It follows a black line on white using the built-in six-sensor array and driver.
MSP430 grants movement and owns ultrasonic stopping.

- First Zumo button press/release: original 80-step calibration. Second: follow.
- Current PD: `kp=1`, `kd=0`, `MAX_SPEED=150`, original upper-only clamps.
- MSP UART: **D6 RX / D13 TX**, 9600 baud; D13 uses the specified 2.2 kΩ/2.2 kΩ
  divider to MSP P3.4. Reserve D13 for TX.
- MSP obstacle threshold: **2 cm**, clearance **4 cm**; missing echoes do not
  stop/block motion. Clearing range never restarts it automatically.
- Uno firmware **OG3** was installed by the user. Cleanup does not upload it.

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
