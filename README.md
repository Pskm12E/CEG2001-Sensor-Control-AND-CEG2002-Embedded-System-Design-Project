# Pest-Monitoring & Spot-Spraying Robot

CEG2001 Sensors and Control · CEG2002 Embedded System Design

**The MSP430 on the car is the main embedded controller.** The laptop provides
local video/display and the current blue-square practice detector. A trained
YOLO insect model and automatic stop/spray jobs remain planned. Demonstration
spraying is intended to use water.

## Find the code

```text
Car/
  MSP430/                   Main robot supervisor
  Arduino_Uno/              IR sensors and L298N wheel control
  ESP32_Gateway/             FireBeetle private Wi-Fi and MSP430 UART
  XIAO_ESP32S3_Camera/       Car-mounted wireless camera
  Archive/                  Earlier Pico/ESP32 experiments
Laptop/
  Dashboard/                Local app and OpenCV blue-square detector
  Pico_W/                   Desk Pico USB/Wi-Fi video and status relay
  YOLO_Model/               Future insect model; no trained weights yet
  Tools/Communication/      Shared protocol, private config, builds and tests
  Documentation/            Wiring and diagram index
  Artifacts/                Diagrams, historical PDF and test evidence
  Deployment/               Hosted-preview notes
  Archive/                  Earlier laptop-side gateway
Docking_Station/
  MSP430/                   Planned second controller; firmware not written
  Booster_Board/            Planned dock peripherals and pin documentation
```

[Car guide](Car/README.md) · [Laptop guide](Laptop/README.md) ·
[Dock plan](Docking_Station/README.md) ·
[Folder migration and path changes](Laptop/Documentation/folder-organisation.md)

## Start the existing system

1. Power the car ESP32, MSP430, Uno and XIAO camera. Keep motor power off for
   camera/communication-only testing.
2. Connect the **desk Pico W** to laptop USB. The camera uses power-bank USB-C;
   its video travels wirelessly.
3. Open **[Laptop/Dashboard/Start Dashboard.cmd](Laptop/Dashboard/Start%20Dashboard.cmd)**.
4. In the local page at **http://127.0.0.1:8765**, select the Pico port and Connect.
5. Start the XIAO camera, then Start detection to test the blue square.

```text
Car camera ── Wi-Fi ── FireBeetle AP ── Wi-Fi ── Desk Pico ── USB ── Laptop
                           |
                      UART 9600
                           |
                    MAIN car MSP430
                           |
                   UART + TX divider
                           |
                     Arduino Uno ── L298N ── wheels
```

Only the desk Pico needs a laptop USB data connection during normal use. The
laptop keeps its usual internet connection. The car controllers still require
their own USB power; wheel motors use the separate AA supply.

The local dashboard sends **read-only checks**. Detection does not send stop,
movement or pump commands. A detected blue square is a colour/shape match, not
insect identification or proof of nozzle alignment.

## Current programs and verification

| Device / feature | Current source | Status |
| --- | --- | --- |
| Main car MSP430 | [robot_supervisor](Car/MSP430/robot_supervisor/README.md), built with `-EspUart` | Supervisor and Uno status link working |
| Arduino Uno | [msp_line_follow](Car/Arduino_Uno/msp_line_follow/README.md) | Integrated controller; physical IR calibration/track testing still needed |
| Car ESP32 | [robot_wifi_gateway](Car/ESP32_Gateway/robot_wifi_gateway/robot_wifi_gateway.ino) | Private AP and UART bridge working |
| XIAO camera | [xiao_camera_wifi](Car/XIAO_ESP32S3_Camera/xiao_camera_wifi/xiao_camera_wifi.ino) | Wireless 320 × 240 video, tested about 15 fps |
| Desk Pico | [laptop_wifi_bridge](Laptop/Pico_W/laptop_wifi_bridge/main.cpp) | Video and robot-status relay working |
| Laptop detection | [blue_detector.py](Laptop/Dashboard/blue_detector.py) | Blue-square test working; positive live test confirmed by project user |
| YOLO / insect recognition | [YOLO_Model](Laptop/YOLO_Model/README.md) | Planned; no trained model files |
| Spray and dock | [Docking_Station](Docking_Station/README.md) | Not integrated |

Before folder reorganisation, 42 dashboard software tests passed and an actual
150-frame annotated stream test measured 15.14 fps with independent robot-status
updates. These are dated results, not a claim of complete autonomous operation.
See the [saved evidence](Laptop/Artifacts/README.md) and the migration document
for checks rerun after moving the source.

## Build without uploading

The current firmware remains on the boards after the folders move. Rebuilding
is needed only when changing firmware. Use the existing private network settings
for all radio builds:

```powershell
python Laptop/Tools/Communication/configure.py
./Laptop/Tools/Communication/build_direct.ps1
./Laptop/Tools/Communication/build_desk_pico.ps1
./Car/XIAO_ESP32S3_Camera/build_camera_wifi.ps1
```

These scripts compile only. They use the original Windows Arduino, CCS and Pico
SDK installations, whose tool paths may need changing on another computer.
Arduino Uno source/sketch folder names remain matched for Arduino IDE.
Older standalone tests are labelled in each device README; flashing them replaces
that board's integrated firmware.

For a new laptop Python environment, follow [the dashboard setup](Laptop/Dashboard/README.md).
Software-only checks from the repository root:

```powershell
python -m unittest discover -s Laptop/Dashboard/tests -p "test_*.py" -v
python Car/Arduino_Uno/tests/check_supervised_control.py
python Car/MSP430/tests/check_supervisor_logic.py
python Laptop/Tools/Communication/tests/check_desk_pico.py
python Laptop/Tools/Communication/tests/check_video_receiver.py
```

## Diagrams, history and files kept local

- [Current boards and wiring](Laptop/Tools/Communication/board-placement.md)
- [Diagram gallery](Laptop/Documentation/diagrams/README.md)
- [Proposed YOLO on the laptop](Laptop/Artifacts/diagrams/yolo-laptop-architecture-2026-11-05.png)
- [Version 1 release history](CHANGELOG.md): tag `v1.0.0` preserves the original layout.
- [Hosted preview configuration](Laptop/Deployment/README.md): the reorganisation
  branch is separate from the currently deployed branch; no deployment is made.

Wi-Fi credentials, generated network headers, compiled firmware, private camera
images, old board backups, local tools and session notes are excluded from Git.
Build output can embed passwords, so build it locally. Dated test JSON and
historical PDFs retain their original contents. Third-party licences are preserved.
