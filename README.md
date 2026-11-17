# Pest-Monitoring & Spot-Spraying Robot

CEG2001 Sensors and Control · CEG2002 Embedded System Design

The **MSP430 is the main embedded controller**. An Arduino Uno + Zumo Shield
follows a black line on white using the six-sensor array and built-in motor
driver. The MSP430 measures the HC-SR04 and sends obstacle STOP commands.
The user confirmed the current driving setup is working on **17 November 2026**.

## Current stopping distance

| Setting | Current behavior |
| --- | --- |
| Obstacle STOP | Valid measured range **2 cm or closer** |
| Clear a recent near inhibit | Two valid readings **4 cm or farther** |
| Missing / invalid / stale echo | Does **not** stop or block calibration or driving, including startup |
| Old near reading | Expires after about **300 ms** without a fresh valid reading |
| Restart after STOP | Manual request required; clearing range never restarts the car |

These are the current configured thresholds in
[obstacle_guard.h](Car/MSP430/robot_supervisor/obstacle_guard.h), not a measured
physical braking distance. The accepted measurement range is 2–400 cm; readings
below that range are invalid. A disconnected or failed sonar therefore also
cannot stop motion under the requested no-echo policy. Local/manual STOP,
UART/session faults and the Uno's one-second communication lease remain active.

## Calibrate and drive

1. Power the MSP430 and Uno, enable the Zumo motor supply, and put the array over
   the black line with room to rotate across both black and white.
2. After the MSP/Uno link is ready, **press and release the Zumo user button
   once**. It requests permission, waits one second, then performs the original
   80-step rotating calibration at ±200. Completion leaves it stopped, `CAL=1`.
3. Re-centre on the line if needed, then **press and release again** to follow it.
4. Press the Zumo button during motion to stop; MSP S2 also requests STOP.
   After an interrupted calibration, repeat the sweep before starting.

Calibration is held in RAM and must be repeated after an Uno reset. The original
PD settings remain `kp=1`, `kd=0`, centre 2500 and `MAX_SPEED=150`, with the
original upper-only speed clamps. USB status is **9600 baud**, firmware **OG3**.
See [the complete Zumo wiring and operating guide](Car/Arduino_Uno/zumo_line_follow/README.md).

The MSP no-echo update was flashed and program-verified; the user installed Uno
OG3, confirmed by its serial output. The source cleanup does not reflash either
board. The full track, calibrated range accuracy and physical braking distance
have not been independently measured.

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

The water sensor is wired to MSP P6.0; ADC integration remains pending.
**Pump/MOSFET/driver are not connected.** Trained YOLO insect recognition,
automatic detection-triggered stop/spray jobs and dock/refill control remain
planned. The current blue-square detector does not command movement or spraying.

## Laptop monitor

1. Power the car FireBeetle, camera and controllers; connect the **desk Pico W**
   to laptop USB.
2. Double-click **[Start Robot.cmd](Start%20Robot.cmd)**. It opens
   **http://127.0.0.1:8765**, finds the Pico and requests wireless video.
3. Select **Start detection** for the blue-square practice test, or launch with
   `"Start Robot.cmd" --detect`. The launcher does not calibrate or start motors.

[Start Dashboard.cmd](Laptop/Dashboard/Start%20Dashboard.cmd) uses the same
launcher. Keep its server window open. Missing hardware leaves the dashboard
available with a setup message; see [launcher options](Laptop/Dashboard/README.md#launcher-options).

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

The last separate Pico check reported its USB link working but its private
Wi-Fi link down. That issue was set aside and has not been reverified as fixed.
Driving/calibration use the MSP/Uno link directly. Each board needs its own
appropriate supply; common GND does not power the boards. Motors use the AA supply.

## Build and check

From the repository root, compile without uploading:

```powershell
./Car/Arduino_Uno/build_zumo.ps1
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo
```

Radio builds reuse the existing private configuration:

```powershell
python Laptop/Tools/Communication/configure.py
./Laptop/Tools/Communication/build_direct.ps1 -Zumo
./Laptop/Tools/Communication/build_desk_pico.ps1
./Car/XIAO_ESP32S3_Camera/build_camera_wifi.ps1
```

The helpers use the original Windows Arduino/CCS/Pico toolchains; installation
paths may need adjustment elsewhere. For dashboard dependencies, use its guide.
Software-only regression checks do not open hardware:

```powershell
python Car/Arduino_Uno/tests/check_zumo.py
python Car/MSP430/tests/check_ultrasonic.py
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
