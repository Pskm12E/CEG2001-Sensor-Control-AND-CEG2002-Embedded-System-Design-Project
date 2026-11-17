# HC-SR04 obstacle stopping — robot MSP430 + Uno

**Current Zumo setup, 17 November:** use the
[Zumo firmware/wiring guide](../../Arduino_Uno/zumo_line_follow/README.md).
Sonar P3.2/P2.7 and its divider remain as below, but the Uno link is now **D6 RX
/ D13 TX via 2.2kΩ/2.2kΩ**, and the MSP build must use **-EspUart -Zumo**.
The new Uno sketch controls the Zumo Shield array/motors on a black line.
The rest of this document is **12 November L298N test history**, including its
old UART pins and sonar-bypass build; do not use those instructions for Zumo.

Prepared on 12 November 2026. Both matching programs are required. The robot
MSP430 ESP-UART firmware has been **uploaded, flash-verified and started** using
TI DSLite. The matching Uno update was **uploaded and verified on COM12**, with
its new banner and stopped status received. Live MSP430/Uno communication and
receipt of an MSP STOP are now verified with motor power off. Echo pulses are
being measured, but known-distance accuracy and physical braking are unverified.
The MSP430 measures range, grants start requests and requests STOP; the Uno
executes the motor commands and enforces its own communication timeout.

## Confirmed sensor wiring

| HC-SR04 connection | Robot MSP430F5529 connection |
| --- | --- |
| VCC | 5V supply |
| GND | Common GND with MSP430 and Uno |
| TRIG | P3.2 |
| ECHO | Voltage-divider junction to P2.7, as below |

Divider orientation matters: **ECHO -> 2.2 kOhm -> P2.7 junction -> 3.3 kOhm -> GND**.
The two resistors are in series between ECHO and GND; P2.7 connects between them.
At 5V ECHO, the junction is approximately 3.0V. Keep the HC-SR04 ECHO signal
off a direct MSP input: it uses 5V logic. Confirm the wiring with power off.
See [Adafruit HC-SR04 pinouts](https://learn.adafruit.com/ultrasonic-sonar-distance-sensors/pinouts)
and the [TI MSP430F5529 datasheet](https://www.ti.com/lit/ds/symlink/msp430f5529.pdf).

Existing controller link stays in place:

| From | To |
| --- | --- |
| MSP P3.3 TX | Uno D5 RX |
| Uno D6 TX | Existing 1kOhm / (2.2kOhm parallel 2.2kOhm) divider -> MSP P3.4 RX |
| MSP GND | Uno GND and motor-driver GND |
| MSP P4.1 TX / P4.2 RX | Existing ESP32 IO16 RX / IO17 TX in ESP-UART build |

The ECHO divider and Uno-TX divider are **separate circuits**. The new sensor
does not connect to the motor driver or receive motor current through an MCU.

## Programs to use

1. **MSP430:** [main.c](main.c), with [ultrasonic_hcsr04.h](ultrasonic_hcsr04.h)
   and [obstacle_guard.h](obstacle_guard.h), plus [console_tx.h](console_tx.h),
   in the same project folder.
   Build the normal robot version from the repository root:

   ```powershell
   ./Car/MSP430/build_robot_supervisor.ps1 -EspUart
   ```

   Output: `Debug_wifi/robot_supervisor.out`. This keeps the ESP32 UART route.
   The build command does not upload. A matching flash must use this new output.

2. **Arduino Uno:** [msp_line_follow.ino](../../Arduino_Uno/msp_line_follow/msp_line_follow.ino)
   with its neighbouring `control.h` and `robot_link.h`. Select Arduino Uno in
   Arduino IDE and upload this sketch with motor power off. The old standalone
   `line_follow_car` sketch does not receive this framed MSP430 stop protocol.

The current Uno selects `WHITE_LANE`: drive on the white road inside black
borders. User-confirmed wiring is LEFT OUT -> D4, RIGHT OUT -> D2, sensor
VCC -> Uno 5V and GND -> Uno GND. Both white -> forward; left black -> RIGHT;
right black -> LEFT; both black -> STOP. This supersedes the A0/A1 analogue
and black-between-heads assumptions. Use [the current Uno guide](../../Arduino_Uno/msp_line_follow/README.md).
OUT1/2 is the stated left wheel, OUT3/4 right; output reversal remains false.
Recalibrate w on actual white and b on actual black at the same height. The
digital 0/1 polarity is learned separately for each head. White outside a missed
border cannot be distinguished from white inside it. Physical steering still
needs testing.

## Temporary IR-driving test without obstacle stopping

The normal supervisor refuses motion when sonar readings are missing or stale;
unplugging the HC-SR04 therefore does not bypass its interlock. For the requested
IR-driving test, build an explicit test version from the repository root:

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -IrDrivingTest
```

This defines `IR_DRIVING_TEST=1` and produces a separate image:
`robot_supervisor/Debug_wifi_ir_test/robot_supervisor.out`. Without `-EspUart`,
the USB test variant goes to `Debug_ir_test/robot_supervisor.out`.
**Installed on 12 November:** the user confirmed motor power off and MSP USB
connected; TI DSLite flashed, verified and ran the ESP-UART test image. Flash
usage 6,172 bytes; RAM usage 1,392 bytes. The existing Uno monitor remained
CAL=1, both inputs OK, DRIVE=0. No Uno reset/upload or start command was sent.
Ultrasonic stopping is currently disabled on the robot. The build command above
still compiles only; applying/restoring a build requires flashing it.

Software verification: the actual sonar/supervisor/Uno integration passes 698
checks with the macro absent, 698 with IR_DRIVING_TEST=0 and 732 with it enabled.
Normal ultrasonic tests (3,128) and supervisor tests (68) also pass. These checks
cover default obstacle protection, the explicit bypass, truthful sonar reports,
calibration/centred-start refusal, manual STOP and communication lease expiry.
Physical wheel movement and stopping have not been tested by the assistant.

1. Keep motor power off. Flash and verify the test image on the **robot MSP430**
   using the existing CCS/DSLite setup. Changing or uploading the Uno sketch
   alone does not remove this MSP interlock. Retain the current D4/D2 digital
   `msp_line_follow` Uno sketch and its existing wiring.
2. The ultrasonic sensor may remain connected. Its measurements remain truthful,
   but **obstacle stopping is disabled in this test build even when it detects
   an obstacle**. Missing/stale sonar no longer vetoes an IR-driving start.
3. Retain the existing Uno calibration if it still reports `CAL=1`; after a Uno
   reset, repeat w/b with motor power off. Both heads must be calibrated, stable
   and over white before an explicit `f` request.
   The MSP still authorises starts. Manual/framed STOP, the Uno communication
   lease, line-related stops and no automatic restart remain active.

To restore obstacle stopping, keep motor power off, build the normal version
below, then **flash and verify that normal image on the MSP430**:

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart
```

Use `robot_supervisor/Debug_wifi/robot_supervisor.out`, not the `_ir_test` image.
Rebuilding alone does not change the installed firmware. Before relying on
obstacle stopping, repeat the normal range/STOP checks below; the earlier
known-distance accuracy and physical braking issues remain unresolved.

## Startup and operation — normal obstacle-stop build

1. Keep the motor supply off. Power the MSP430, Uno and ultrasonic sensor with
   their existing controller supplies and common ground.
2. Open the **Uno** Serial Monitor at **115200 baud, New Line**. Close other apps
   holding its USB port. Allow the MSP430/Uno handshake to finish; `w/b/f` prints
   a wait message while there is no session.
3. Put both IR sensors on actual white and send `w`. The Uno queues a request;
   the MSP430 grants the calibration. Wait about one second, until `REQ=0` and
   calibration sampling has completed. Then put both over actual black and
   send `b`; wait for completion. `CAL=1` means both sensors have contrast.
4. Centre both IR sensors over white. Put a flat obstacle beyond 25cm and within
   the sensor's usable range for the first check. The supervisor needs two valid
   clear readings before granting a start. Both black remains a latched stop.
5. With wheels raised for initial direction/stop checks, connect motor power.
   Send `f`: this is a **request**, not a local bypass. The MSP430 grants START
   only when its ultrasonic interlock is clear; the Uno also checks calibration
   and sensor position.
6. Bring the target inside 20cm, measuring from the ultrasonic transducers.
   The MSP430 requests STOP and the Uno must stop both outputs. Confirm physical
   stopping; a printed status alone does not measure wheel motion or stopping distance.
7. Removing the target **does not automatically restart the car**. After two
   valid readings at least 25cm away and the stopped link has recovered, send a
   new `f`. `s` on Uno USB stops locally at any time, and MSP S2 also requests STOP.

If a start request is refused, it is discarded rather than saved for an
automatic future start. Stop and allow resynchronisation before a new request.
Calibration remains in Uno RAM and is lost on board reset/upload, so recalibrate.
The dashboard remains read-only and does not send these movement requests.

## Timing, thresholds and limitations

- Initial stop threshold: **20cm**; release threshold: **25cm**, with two clear
  samples. Constants are in `obstacle_guard.h`. These are bench settings, not a
  validated stopping distance for full-speed travel.
- Trigger period is approximately 100ms, using the existing supervisor tick.
  Timer_A2 ends the approximately 11us TRIG pulse and imposes a 35ms echo deadline.
  Port2 interrupts timestamp ECHO rising/falling edges at the existing 1.048576MHz
  SMCLK. Timer_A0 heartbeat and Timer_A1 button debounce retain their duties.
- UART1 status output uses a bounded, interrupt-drained queue so long reports at
  9600 baud do not block obstacle processing. Echo freshness uses its interrupt
  timestamp, rather than the later time at which the main loop consumes it.
- Distance uses approximate 343m/s sound speed, rounded to centimetres. Validate
  actual distances against a ruler and characterise readings at your test targets.
- Missing echo/out-of-range is **unknown**, not proof of a clear path. Startup is
  inhibited until valid clear readings. Validity expires after three 100ms ticks;
  stale readings or a disconnected/stuck sensor inhibit motion and request STOP.
  A featureless area beyond sensor range can therefore prevent starting.
- STOP has priority over queued START and preempts a silent outstanding request
  after about 100ms. Transport delivery and mechanical stopping add latency. The
  Uno's independent 1000ms lease stops on lost MSP communication. Neither limit
  is a measured guarantee of collision avoidance.
- Slow-corner source now uses the Uno sketch's `TURN_LIMIT_MS=3000`, allowing a
  correction up to 3 seconds. It ends immediately on reacquiring white. Obstacle
  STOP and the independent 1000ms lease still override it. This timing change
  was uploaded and flash-verified on 12 November. The running Uno reports the
  3000ms setting; the preceding image used 750ms.
- A single forward ultrasonic sensor has a limited field of view; small, angled,
  soft or off-axis objects may not produce a reliable echo. This is a lab
  prototype obstacle stop, with physical testing still required.
- Existing dashboard status format remains unchanged. The dashboard's obstacle
  distance placeholder is not populated by this change.

For an optional MSP USB sensor bench test, build without `-EspUart` and use the
MSP Application UART at 9600 baud, New Line: `SONAR` reports `VALID`, `CM`,
`INHIBIT` and `FAULT`. That bench build uses the older USB/I2C route. Restore
the ESP-UART build for the normal car network. Neither build starts driving at boot.

## Live diagnosis — 12 November 2026

- The Uno was found running the standalone `line_follow_car` sketch. Replaced
  it with `msp_line_follow`. The subsequent steering correction disables the
  earlier turn-output swap; 9434 flash bytes verified. Its running banner now
  confirms `D2 BLACK -> RIGHT; D4 BLACK -> LEFT`, the 3000ms corner setting
  and `MSP STOP received`.
- MSP firmware matched the saved ESP-UART image without reflashing it. Debug
  snapshots now show `linked=1`, stopped state, and fresh echo pulse widths.
- An initial observation reported 61–103cm. With the user reporting a target
  held 5–15cm ahead, subsequent readings were 70–95cm and inhibit stayed clear.
  That is a failed near-target check, not proof of accurate range or braking.
  Check sensor orientation/target geometry, actual TRIG/ECHO wiring and their
  separate divider before allowing a powered obstacle-stop trial.
- No start, calibration or spray command was sent. Motor power stayed off.
  The dashboard distance placeholder remains unchanged.

## Software verification

From the project root, using the installed Python and MSYS2 g++ toolchain:

```powershell
python Car/MSP430/tests/check_ultrasonic.py
python Car/MSP430/tests/check_supervisor_logic.py
python Car/Arduino_Uno/tests/check_supervised_control.py
python Laptop/Tools/Communication/tests/check_direct.py
```

These exercise the actual policy, ISR adapter with fake registers, supervisor
request/response functions and Uno controller. The simulated near-echo path ends
in a framed STOP acknowledged by the Uno, and clear readings do not restart it.
They do not verify electrical connections, target detection or physical braking.

Latest checks: 3,128 ultrasonic/console-queue assertions, 68 supervisor assertions
(including the end-to-end simulated near/stale-range stop), 163 Uno control/link
assertions and 60 direct-UART bridge assertions passed. Both MSP build variants
and the matching Uno target compile. The compiled 3-second timing version uses
9,434 bytes flash / 606 bytes global RAM after the steering correction; the preceding uploaded image was
9,120 bytes / 602 bytes. All 58 dashboard regression tests passed for the obstacle
integration; those tests use simulated hardware.
