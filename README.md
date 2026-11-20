# Pest-Monitoring & Spot-Spraying Robot

CEG2001 Sensors and Control · CEG2002 Embedded System Design

The **MSP430 is the main embedded controller**. An Arduino Uno + Zumo Shield
follows a black line on white using the six-sensor array and built-in motor
driver. The MSP430 measures the HC-SR04 and sends obstacle STOP commands.
The user confirmed the current driving setup is working on **17 November 2026**.

## Integrated pump update — 20 November 2026

The user confirmed two successful **three-second P1.6 pump runs**, each followed
by automatic cutoff. The normal MSP430 supervisor has now replaced the LED test
and is flashed/program-verified with its pump profile enabled.

The sequence is **blue target → Zumo STOP acknowledgement → 300 ms settling →
three-second pump pulse → pump off → matching continuation → line following**.
The laptop supplies continuation from fresh camera observations. Manual STOP,
an ultrasonic obstacle or a communication fault cancels the job with the pump off.

Live checks through Pico V3 and FireBeetle V2 report `READY=1`, `PUMP=0`, `RUN=0`,
the Uno link ready and zero UART/framing/drop errors. Uno OG4 remains installed
with straight speed 150 and outside-track turn speed up to 250. The ultrasonic
setting remains **5 cm STOP / 7 cm clearance**. Calibrate the line array before
following. MSP S2 remains a temporary debug STOP control.

The combined sequence passes software integration checks. The full physical
target-to-spray-to-resume trial is still to be observed on the track. See the
[pump/cycle guide](Car/MSP430/robot_supervisor/PUMP_SETUP.md) and
[installation record](Laptop/Artifacts/verification/pump-integration-2026-11-20.json).

The installed desk Pico video fix keeps completed frames while receiving the
next JPEG. The 18 November live checks measured **12.9–13.3 fps**, with longest
gaps of 281–328 ms. See the
[video measurement record](Laptop/Artifacts/verification/video-stability-2026-11-18.json).

## Ultrasonic pause and resume

The pause update requires the matching MSP430 supervisor and **Uno OG5**. The
20 November pump installation above records the hardware state before this
source update. Upload both updated firmwares to use automatic obstacle resume.

| Setting | Current behavior |
| --- | --- |
| Obstacle detected during line following | The Zumo pauses at a valid measured range **5 cm or closer** |
| Obstacle clears during the pause | The Zumo resumes after two consecutive valid readings **7 cm or farther** |
| Missing / invalid / stale echo | Logged as a sensor fault after the timeout. Automatic resume waits for valid readings. |
| Old near reading | Expires after about **300 ms** without a fresh valid reading |
| Manual STOP, interrupted calibration, or link fault | A new local request is required |

The sonar accepts valid echoes from 2–400 cm. The thresholds are configured
distances. Physical braking distance remains unmeasured. With no echo, the
robot can still start on a local request under the existing sonar policy.
The firmware requires valid echoes to resume a paused run automatically.
See the [MSP430 sonar policy](Car/MSP430/robot_supervisor/README.md#current-sonar-policy).

## Calibrate and drive

1. Power the MSP430 and Uno, enable the Zumo motor supply, and put the array over
   the black line with room to rotate across both black and white.
2. After the MSP/Uno link is ready, **press and release the Zumo user button
   once**. It requests permission, waits one second, then performs the original
   80-step rotating calibration at ±200. Completion leaves it stopped, `CAL=1`.
3. Re-centre on the line if needed, then **press and release again** to follow it.
4. Press the Zumo button during motion or an obstacle pause to stop. MSP S2
   also requests STOP.
   After an interrupted calibration, repeat the sweep before starting.

Calibration is held in RAM and must be repeated after an Uno reset. The original
PD settings remain `kp=1`, `kd=0`, centre 2500 and `MAX_SPEED=150`, with a positive turn cap of 250 and reverse cap of 400. USB status is
**9600 baud**, source firmware **OG5**.
See [the complete Zumo wiring and operating guide](Car/Arduino_Uno/zumo_line_follow/README.md).

The obstacle pause and resume sequence passed host integration tests. The
updated firmware awaits a physical track test.

## Find the code

| Folder | Role |
| --- | --- |
| [Car/MSP430](Car/MSP430/README.md) | Main supervisor, sonar and movement permission; build with `-EspUart -Zumo` |
| [Car/Arduino_Uno](Car/Arduino_Uno/README.md) | Active `zumo_line_follow` sketch; previous L298N sketches retained as history |
| [Car/ESP32_Gateway](Car/ESP32_Gateway/README.md) | FireBeetle private Wi-Fi access point and MSP UART bridge |
| [Car/XIAO_ESP32S3_Camera](Car/XIAO_ESP32S3_Camera/README.md) | Car-mounted wireless camera |
| [Laptop/Dashboard](Laptop/Dashboard/README.md) | Local monitor and OpenCV blue-square practice detector |
| [Laptop/Pico_W](Laptop/Pico_W/README.md) | Desk USB/Wi-Fi video and status relay |
| [Laptop/Tools/Communication](Laptop/Tools/Communication/README.md) | Protocol, private network configuration, build helpers and checks |
| [Docking_Station](Docking_Station/README.md) | Planned dock controller and peripherals |

Water sensor P6.0 raw ADC reporting and the bounded target spray cycle are
implemented and the pump profile is installed; wet/dry calibration and the full
physical target-cycle trial are pending. Trained YOLO insect recognition and dock/refill control remain planned.

## Laptop monitor

1. Power the car FireBeetle, camera and controllers; connect the **desk Pico W**
   to laptop USB.
2. Double-click **[Start Robot.cmd](Start%20Robot.cmd)**. It opens
   **http://127.0.0.1:8765**, finds the Pico and requests wireless video.
3. Select **Start detection** for the blue-square practice test, or launch with
   `"Start Robot.cmd" --detect`. The default launcher does not calibrate or start
   motors; enabling detection permits the bounded cycle once all required
   firmware and the verified pump driver are installed.

[Start Dashboard.cmd](Laptop/Dashboard/Start%20Dashboard.cmd) uses the same
launcher. Keep its server window open. Missing hardware leaves the dashboard
available with a setup message; see [launcher options](Laptop/Dashboard/README.md#launcher-options).
Press **Ctrl+C** in the launcher terminal to close its dashboard, video and
detection. Use the robot's stop control to stop independent line following.

```text
Car camera ── Wi-Fi ── FireBeetle AP ── Wi-Fi ── Desk Pico ── USB ── Laptop
                           |
                      UART 9600
                           |
                    Main car MSP430 ── HC-SR04
                           |
                   UART + TX divider
                           |
                     Arduino Uno ── Zumo Shield ── tracks
```

The user confirmed target and ultrasonic stopping on 18 November, then confirmed
P1.6-controlled pump operation twice on 20 November. The integrated pump profile
is installed. A full physical target-to-spray-to-resume trial remains pending.

Driving/calibration use the MSP/Uno link directly. Each board needs its own
appropriate supply; common GND does not power the boards. Motors use the AA supply.

## Build and check

From the repository root, compile without uploading:

```powershell
./Car/Arduino_Uno/build_zumo.ps1
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo -PumpDriverVerified -SpraySeconds 3
```

Radio builds reuse the existing private configuration:

```powershell
python Laptop/Tools/Communication/configure.py
./Laptop/Tools/Communication/build_direct.ps1 -Zumo -PumpDriverVerified
./Laptop/Tools/Communication/build_desk_pico.ps1
./Car/XIAO_ESP32S3_Camera/build_camera_wifi.ps1
```

The helpers use the original Windows Arduino/CCS/Pico toolchains; installation
paths may need adjustment elsewhere. For dashboard dependencies, use its guide.
Software-only regression checks do not open hardware:

```powershell
python Car/Arduino_Uno/tests/check_zumo.py
python Car/MSP430/tests/check_ultrasonic.py
python Car/MSP430/tests/check_console_tx_interrupt.py
python Car/MSP430/tests/check_spray_job.py
python Laptop/Tools/Communication/tests/check_desk_actions.py
python Car/MSP430/tests/check_supervisor_logic.py
python Laptop/Tools/Communication/tests/check_direct.py
python -m unittest discover -s Laptop/Dashboard/tests -p "test_*.py"
python Laptop/Tools/check_layout.py
```

## Design and history

- [Agreed two-plant track](Car/Track/README.md)
- [Zumo enclosure CAD and print guide](Car/Mechanical/Zumo_Enclosure/README.md)
- [Current boards and wiring](Laptop/Tools/Communication/board-placement.md)
- [Diagram gallery](Laptop/Documentation/diagrams/README.md)
- [Saved verification evidence](Laptop/Artifacts/README.md) and [changelog](CHANGELOG.md)
- [Folder migration](Laptop/Documentation/folder-organisation.md) and [hosted preview](Laptop/Deployment/README.md)

Wi-Fi credentials, generated network headers, compiled firmware, board backups,
private camera images and local session notes stay out of Git. Build output can
embed passwords; build it locally. Historical reports retain their dated results,
and third-party licences are preserved. Pushing this project branch does not
change the separate hosted-preview branch.
