# Arduino Uno two-sensor line follower

Third sketch combining the existing motor pin map and IR contrast calibration.
The user copied/uploaded this sketch and shared its sensor/status output.
The assistant has not physically verified a complete track run. Repair of the
reported motor-supply connection and reliable track calibration remain pending.

## Wiring and placement

- LEFT IR OUT -> D2; RIGHT IR OUT -> D4, viewed from behind facing forward.
  User confirmed these left/right assignments. Both sensor VCC -> 3.3V and
  GND -> common GND. Digital INPUT mode does not enable a 5V pull-up.
- L298N: D7 -> IN1, D8 -> IN2, D9 -> IN3, D10 -> IN4; Uno GND -> driver GND.
  Left motor on OUT1/OUT2; right motor on OUT3/OUT4. ENA/ENB jumpers fitted.
- Retain the motor polarity constants from the working forward test. With
  wheels raised, verify that both commands propel the chassis forward. If
  necessary reverse that motor's leads with power off or its direction constant.
- Mount the IR sensors side by side ahead of the drive axle, pointing down at
  a short fixed height. **Both sensors must fit over black when centred**; use
  a wide strip or position the sensing spots sufficiently close together.
  The exact height/width must be established experimentally with the actual
  sensor modules. A narrow line between two sensors reading white/white is not
  supported by this configuration; that pattern is treated as line loss.

This version uses full-on/off wheel commands with the existing four control
wires, not adjustable PWM speed or encoder feedback. Turning brakes the inside
wheel and drives the outside wheel. Start on a clear floor with a wide strip
and gentle curves after checking steering with the wheels raised. A stuck sensor
or unsuitable sensor spacing cannot be corrected by merging firmware.

## Commands at 115200 baud

1. Keep motor battery off while uploading. Select Arduino Uno and its port.
2. With the robot stationary, place BOTH sensors over white; send `w`.
3. Place BOTH over black; send `b`. Use two patches if necessary. BOTH must
   pass contrast calibration; a still-stuck second sensor blocks starting.
4. Put the car centred on the black strip with BOTH sensors seeing black.
   Connect motor power after the setup check; send `f` to follow.
5. Send `s` to stop. Repeated f while following does not reset recovery timers.

Calibration, clear (`c`), and help (`?`) commands stop motion. Stop wins over
other commands already queued together. Calibration is RAM-only and must be
repeated after reset/power-off. Start is refused until both sensors are
calibrated, stable and over black. No motion is requested automatically at boot.

## Steering

| Left | Right | Command |
| --- | --- | --- |
| Black | Black | Both motors forward |
| Black | White | Left stopped, right forward: steer left |
| White | Black | Left forward, right stopped: steer right |
| White | White | Brief recovery in the most recent correction direction, or stop if no recent direction is known |

During line loss, recovery lasts at most 250 ms and requires a correction in the
previous 250 ms. At LINE_LOST, driving is latched off: reposition on the line and
send a new f. A correction lasting 750 ms without both-black recentering stops
with TURN_TIMEOUT; tune only after observing actual track behaviour. Unstable
signals temporarily stop the motor outputs; after 150 ms continuously waiting,
SIGNAL_FAULT latches driving off. The 8 ms filter and thresholds need track tests.

Example: `L2=BLACK R4=WHITE MODE=TURN_LEFT`. NC means not calibrated, ? means
the signal has not settled. Status describes commands, not confirmed wheel
movement. Reporting skips a frame if the serial buffer is full, keeping steering
non-blocking. The only delay is the 200 ms calibration with motors stopped.

The Uno cannot reliably detect Serial Monitor closing; send s and confirm STOP
before closing it. Keep a motor power switch/connector reachable. Pins may float
during power loss/reset/bootloader, so do not depend on unplugging USB as a stop.

This is a local navigation bench prototype. MSP430 remains the project's main
controller; its dispatch/stop link is still a separate integration task.

## Verification

- Arduino Uno build passed with AVR core 1.8.8: 6,694 bytes flash, 413 bytes RAM.
  The only warnings in the clean build were unused parameters in the installed
  Arduino core's `new.cpp`; the final incremental build reported no new warnings.
- 23 compile-time assertions passed against control helpers extracted directly
  from the sketch: all four sensor patterns, left/right wheel commands, reversed
  sensor polarity, missing/identical calibration, bounded recovery, stale/unknown
  directions, and 32-bit timer rollover. No host executable was run.
- Reproduce helper checks with the bundled Python and
  `../tests/check_line_follow_logic.py`; it invokes the installed MSYS2 g++ in
  syntax-only mode. These checks do not verify the full live serial state machine.
- No upload, motor actuation or physical track run by the assistant. Sensor
  mounting, reliable contrast from BOTH modules, motor polarity, correction
  direction and timing still require the user's physical tests.

References: [ST L298 datasheet](https://www.st.com/resource/en/datasheet/l298.pdf)
for bridge input/enable behaviour; [Pololu reflectance application note](https://www.pololu.com/docs/0J13/all)
for sensitivity to reflectance, sensor height and lighting. These do not identify
the user's exact IR module.
