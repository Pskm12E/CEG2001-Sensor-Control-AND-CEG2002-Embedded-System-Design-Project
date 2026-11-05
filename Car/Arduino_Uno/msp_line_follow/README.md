# Uno line follower controlled by the robot MSP430

This is the **current Uno program**, uploaded on 3 November 2026. It combines
the earlier D2/D4 line follower with a framed UART link on D5/D6. The MSP430
authorises start/stop; the Uno handles steering and local stop limits.

See [the complete setup, calibration and test guide](../../MSP430/robot_supervisor/README.md).

- MSP USB console: COM13, 9600 baud. `W`, `B`, `STATUS`, `F`, `S`.
- Uno USB console: COM12, 115200 baud. `STATUS` and local `S`; no USB start.
- Starts stopped and uncalibrated. Calibration is lost on reset.
- Keepalives expire after 1000ms; communication recovery does not resume driving.
- D7-D10 motor wiring and full-drive ENA/ENB configuration are unchanged.

`control.h` contains the host-tested calibration, navigation and lease logic.
`robot_link.h` is the shared C/C++ frame definition used by both boards.
`msp_line_follow.ino` connects that logic to GPIO, serial and the watchdog.

Compiled/uploaded: 8268 bytes flash, 559 bytes global RAM. Communication and
start refusal passed live tests with the motor battery disconnected. Actual
track steering and motor-stop timing still require a physical test.
