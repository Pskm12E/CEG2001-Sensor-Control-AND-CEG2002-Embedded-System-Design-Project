# Pest-Monitoring & Spot-Spraying Robot

CEG2001 Sensors and Control · CEG2002 Embedded System Design

## Empty-tank reverse · OG7

With the matching MSP430 supervisor and Uno OG7 firmware, two consecutive
P6.0 readings of **15 or lower** while following the line trigger one slow,
straight reverse for **one second**. The Zumo then parks. The front ultrasonic
sensor covers the forward path only. For a first trial, leave space behind the tracks.

If the tank goes empty during a spray job, the pump switches off and the Zumo
stays parked. Two readings of **30 or higher** rearm the run after a refill.
Tap the Zumo button to start again. The MSP samples once per second and uses
raw ADC counts independently of the dashboard's percentage calibration.

## V2_Working · 20 November 2026

The Zumo follows a black line. Its Arduino Uno runs **OG6**, which reads the
six line sensors and drives the tracks. The **MSP430F5529** grants motion,
reads the ultrasonic and water sensors, and switches the pump. The operator
confirmed that the pump worked after replacing a resistor in the pump circuit.

| Event | Robot behavior |
| --- | --- |
| Camera confirms a blue square while following | The Zumo stops and acknowledges. After about 300 ms, the MSP430 drives the MOSFET gate on **P1.6** for **3 seconds**. A fresh continuation for the same camera job allows line following to resume. |
| Ultrasonic measures **5 cm or closer** while following | The Zumo pauses. Two consecutive valid readings of **7 cm or farther** allow it to resume. Missing echoes leave it paused. |
| Near obstacle, manual stop or link failure during a spray job | The supervisor cancels the job and switches the pump off. Starting again requires a new local request. |
| Zumo stays upside down | The shield buzzer beeps. Hold the parked Zumo's user button for **2 seconds** to toggle the alarm. The Uno remembers the setting. |

The laptop dashboard shows live camera video and the **P6.0 water reading**.
Its Water tank panel shows probe wetness until you save empty and full readings
with the probe mounted in the tank. It then shows estimated tank level.
The pump indicator shows the MSP430 gate command. [Dashboard guide](Laptop/Dashboard/README.md)

## Ultrasonic pause and resume

The HC-SR04 accepts echoes from 2–400 cm. A previous near reading expires after
about 300 ms without a valid echo. This permits a new local start in open
space. An existing obstacle pause still requires two confirmed clear readings.
The 5 cm setting is the sensor threshold. Physical braking distance has not
been measured. [Sonar policy](Car/MSP430/robot_supervisor/README.md#current-sonar-policy)

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
**9600 baud**, source firmware **OG7**.
See [the complete Zumo wiring and operating guide](Car/Arduino_Uno/zumo_line_follow/README.md).

## Find the code

| Folder | Role |
| --- | --- |
| [Car/MSP430](Car/MSP430/README.md) | Main supervisor, sonar, pump cutoff and movement permission |
| [Car/Arduino_Uno](Car/Arduino_Uno/README.md) | Active `zumo_line_follow` sketch; previous L298N sketches retained as history |
| [Car/ESP32_Gateway](Car/ESP32_Gateway/README.md) | FireBeetle private Wi-Fi access point and MSP UART bridge |
| [Car/XIAO_ESP32S3_Camera](Car/XIAO_ESP32S3_Camera/README.md) | Car-mounted wireless camera |
| [Laptop/Dashboard](Laptop/Dashboard/README.md) | Local monitor and OpenCV blue-square practice detector |
| [Laptop/Pico_W](Laptop/Pico_W/README.md) | Desk USB/Wi-Fi video and status relay |
| [Laptop/Tools/Communication](Laptop/Tools/Communication/README.md) | Protocol, private network configuration, build helpers and checks |
| [Docking_Station](Docking_Station/README.md) | Planned dock controller and peripherals |

The camera currently recognizes a blue practice target. Trained insect
recognition and automatic docking/refill are planned.

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
private camera images and local session notes stay out of Git. Build radio
firmware locally with your private network settings.
