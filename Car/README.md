# Car electronics

**18 November update — firmware versions installed:** 5 cm STOP / 7 cm clearance;
blue-target stop → 3-second spray → token-matched continuation. Uno OG4 raises
the positive turn limit to 250 while straight speed stays 150. Pump gate P1.6,
raw water ADC P6.0. The pump driver is disabled until its electrical rating is
verified. Read [the current cycle/pump guide](MSP430/robot_supervisor/PUMP_SETUP.md). MSP 5 cm / 7 cm pump-disabled firmware and Pico V3 are installed/verified.
The user-installed Uno OG4 is confirmed by its serial banner. FireBeetle V2
is flashed/hash-verified and identified over USB. Reconnect/power the MSP for a
full link check. Pump output remains disabled pending driver qualification;
physical spraying is not ready. The earlier installed milestone is history below.

## Previous installed milestone — 17 November 2026

Current base, **17 November 2026**: **Arduino Uno + Zumo Shield** follows a black
line on white. The **MSP430 is the main controller**, measuring the HC-SR04 and
granting movement. The user confirmed the driving setup is working.

**Current obstacle STOP trigger is 2 cm**, with two readings at least 4 cm
clearing a recent near inhibit. Missing echoes do not stop/block motion; stale
near data expires after about 300 ms. Clearing never restarts it automatically.
These settings are not measured physical braking distances.

| Device | Program / responsibility |
| --- | --- |
| [MSP430](MSP430/README.md) | `robot_supervisor`, `-EspUart -Zumo`; range, grants and STOP |
| [Arduino_Uno](Arduino_Uno/README.md) | `zumo_line_follow`, OG3; array and built-in motor driver |
| [ESP32_Gateway](ESP32_Gateway/README.md) | FireBeetle private Wi-Fi access point and MSP UART bridge |
| [XIAO_ESP32S3_Camera](XIAO_ESP32S3_Camera/README.md) | Wireless camera; USB-C supplies power during use |
| [Archive](Archive/README.md) | Earlier experiments |

Use [the Zumo wiring/button guide](Arduino_Uno/zumo_line_follow/README.md),
[agreed two-plant track](Track/README.md) and
[removable enclosure CAD](Mechanical/Zumo_Enclosure/README.md).
The installed MSP no-echo update was verified, and the user installed Uno OG3.
Cleanup compiles only; neither board is reflashed.

Camera video/status travel through the desk Pico to the laptop; the most recent
separate Pico Wi-Fi issue remains unverified. Driving uses the MSP/Uno UART.
Water S is wired to P6.0 but ADC logic is pending. Pump/driver are not connected;
automatic pest jobs, spraying, dock control and full-track validation remain pending.
