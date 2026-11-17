# Historical MSP430 IR-only test

Superseded by the [current Zumo supervisor](robot_supervisor/README.md). The dated installed-state descriptions below do not describe today's firmware.

## Historical temporary IR-driving test — previous base only

The following records the 12 November L298N test. It is superseded by the
17 November Zumo design. **Do not install it for Zumo:** it disables the
required ultrasonic stopping. `-Zumo -IrDrivingTest` is rejected.

For the requested IR-only driving test, the supervisor has an explicit build
option that disables the ultrasonic interlock:

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -IrDrivingTest
```

It defines `IR_DRIVING_TEST=1` and writes
`robot_supervisor/Debug_wifi_ir_test/robot_supervisor.out`; the USB variant without
`-EspUart` uses `Debug_ir_test/robot_supervisor.out`. **The ESP-UART test image
was flashed, verified and started on 12 November after the user confirmed motor
power off. Ultrasonic stopping is currently disabled on the robot MSP430.**
The Uno remains calibrated and stopped; no start command was sent.

Keep motor power off while flashing and verifying this image on the **robot
MSP430**. The current D4/D2 digital Uno sketch stays in use. No physical sonar
disconnect is required: readings remain available, but this test image disables
obstacle stopping even with the sensor connected. Unplugging sonar with the
normal firmware instead inhibits motion.

MSP-authorised starts, calibrated white/white start position, manual/framed STOP,
the Uno lease and no automatic start/restart remain active. See the
[test procedure](robot_supervisor/ULTRASONIC_SETUP.md#temporary-ir-driving-test-without-obstacle-stopping).

To restore obstacle stopping, build with `-EspUart` **without** `-IrDrivingTest`,
then flash and verify `robot_supervisor/Debug_wifi/robot_supervisor.out` with motor
power off. A build alone does not change the running firmware. Repeat the normal
range/STOP checks before relying on obstacle stopping.
