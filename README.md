# Pest-monitoring and spot-spraying robot

CEG2001 Sensors and Control · CEG2002 Embedded System Design · Group P2-2

The Zumo follows a black line, stops at a confirmed blue marker representing a pest and delivers a timed water spray. A separate refill station detects the robot with a magnet and checks its own water supply before pumping.

## Submission materials

- [Watch the final demonstration on YouTube](https://youtu.be/T4geuTmunvc)
- [View the final 17-slide presentation on Canva](https://www.canva.com/d/4f2vKg5oXtSbtI9)
- [Read the final report on Google Docs](https://docs.google.com/document/d/1eeSYC1oTbA5qsdeJ9ge7zVoWEp7Dm4dpvsCEs_sKDfw/edit) or [open the submitted-format PDF](output/pdf/CEG2001_Report_P2-2.pdf).
- [Hardware block diagram](Laptop/Presentation/Robot%20and%20refill%20station%20-%20hardware%20block%20diagram.pdf) and [presentation notes in slide order](Laptop/Presentation/Robot%20presenter%20notes%20-%2017%20slides.md).

The team demonstrated track following, target and obstacle stops, timed car-pump operation and a separate physical dock refill. A complete automatic return, refill and departure on the track is still to be verified. The test liquid was water and the camera detected a blue marker.

## Source map

| Where | Code | Responsibility |
| --- | --- | --- |
| Car | [MSP430F5529 supervisor](Car/MSP430/robot_supervisor) | Reads sonar and tank level, grants motion and times the spray pump on P1.6. |
| Car | [Arduino Uno and Zumo Shield](Car/Arduino_Uno/zumo_line_follow) | Calibrates six reflectance sensors, follows the line, drives the tracks and sounds the flip alarm. |
| Car | [FireBeetle ESP32](Car/ESP32_Gateway/robot_wifi_gateway) | Hosts the local Wi-Fi access point and bridges commands and status to the car MSP430 over UART. |
| Car | [XIAO ESP32-S3 Sense](Car/XIAO_ESP32S3_Camera/xiao_camera_wifi) | Captures camera frames and sends them to the desk Pico over Wi-Fi. |
| Desk | [Raspberry Pi Pico W](Laptop/Pico_W/laptop_wifi_bridge) | Relays video, status and requests between the private Wi-Fi network and laptop USB. |
| Laptop | [Dashboard and OpenCV detector](Laptop/Dashboard/README.md) | Shows video and readings, confirms the marker and coordinates visits with a connected station. |
| Dock | [Standalone station](Docking_Station/MSP430/standalone) | Handover CCS project. The station's Hall sensor, reservoir comparator, timers and LCD manage a refill locally. |
| Dock | [Laptop-coordinated station](Docking_Station/MSP430/waterlevel) | Alternative CCS project for the same station board. The laptop confirms a stopped car and renews a refill permit. |

Read the [station guide](Docking_Station/README.md) to choose the station image. Each station project contains its own MSP430 source, LCD driver, linker command file and CCS target configuration.

## Run the demonstration

1. Install the [dashboard dependencies](Laptop/Dashboard/README.md#dependencies-and-tests). Power the car boards and connect the desk Pico W to laptop USB. The coordinated station also needs its own USB connection.
2. Open [Start Robot.cmd](Start%20Robot.cmd). The monitor opens at [the local dashboard](http://127.0.0.1:8765). Wait for live camera frames and a ready MSP430-to-Uno link. Choose **Start detection** to enable the blue-marker test.
3. Place the Zumo on the line. On first use, tap the Zumo button and let it sweep the sensors over black and white. Re-centre the robot, then tap again to drive. Later power-ups restore the saved calibration. A full tank at power-up still requires the start button.
4. To enable automatic departure after a refill, open **Calibrate water level** with the probe mounted. Record a stable **empty** and **full** reading. The dashboard sends the resulting threshold to the supervisor. With an incomplete calibration, automatic refill departure stays disabled.
5. During a run, press the Zumo button to stop. For wiring, replacement sensors and recalibration, see the [Zumo guide](Car/Arduino_Uno/zumo_line_follow/README.md) and [car pump guide](Car/MSP430/robot_supervisor/PUMP_SETUP.md).

| Trigger | Programmed response |
| --- | --- |
| Confirmed target during eligible line following | The car requests STOP. After the Uno acknowledges and about 300 ms elapse, the verified P1.6 driver delivers a three-second pump command. |
| Sonar measures 5 cm or closer while following | The car pauses. Two consecutive valid readings of at least 7 cm allow the obstacle pause to resume. |
| Two successive tank readings below 500 while following | The Zumo reverses slowly. A coordinated magnetic arrival requests a stop. Two readings above 500 while reversing can also park it. The sonar faces forward. |
| Parked car after a qualifying low-water event | A calibrated reading strictly above 60% for three seconds can restart line following when the motion interlocks allow it. The saved example of 1836 empty and 2281 full first qualifies at 2104. |
| Qualified arrival at the standalone station | The station waits three seconds, checks its reservoir and commands its own P1.4 refill pump for up to ten seconds. A missing magnet or low reservoir cuts the command. |

## Build the firmware

The following PowerShell commands compile the projects without uploading them. Run them from this folder. For the car install the TI MSP430 compiler, the Arduino AVR and ESP32 cores, the Pololu ZumoShield library and the Raspberry Pi Pico SDK. The [communications guide](Laptop/Tools/Communication/README.md) lists the tools and explains how to generate matching private network settings. For both station projects you can also use **Import CCS Projects** in Code Composer Studio.

```powershell
python Laptop/Tools/Communication/configure.py
./Car/Arduino_Uno/build_zumo.ps1
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo -PumpDriverVerified -SpraySeconds 3
./Laptop/Tools/Communication/build_direct.ps1 -Zumo -PumpDriverVerified
./Car/XIAO_ESP32S3_Camera/build_camera_wifi.ps1
./Laptop/Tools/Communication/build_desk_pico.ps1
./Docking_Station/MSP430/build_station.ps1 -Variant standalone
./Docking_Station/MSP430/build_station.ps1 -Variant coordinated
```

The direct radio build also compiles the car supervisor. Keep the same locally generated network settings when building all three Wi-Fi boards. Network passwords, flashed binaries and camera captures are excluded from the submission.

## Check the software

Run these checks from the repository root with Python and a C/C++ host compiler. Install the dashboard dependencies before its tests. The checks simulate sensors, links and outputs without operating hardware.

```powershell
python Car/Arduino_Uno/tests/check_zumo.py
python Car/MSP430/tests/check_supervisor_logic.py
python Car/MSP430/tests/check_ultrasonic.py
python Car/MSP430/tests/check_console_tx_interrupt.py
python Car/MSP430/tests/check_spray_job.py
python Docking_Station/tests/check_dock.py
python Laptop/Tools/Communication/tests/check_direct.py
python Laptop/Tools/Communication/tests/check_desk_actions.py
python Laptop/Tools/Communication/tests/check_desk_pico.py
python Laptop/Tools/Communication/tests/check_video_receiver.py
python -m unittest discover -s Laptop/Dashboard/tests -p "test_*.py"
python Laptop/Tools/check_layout.py
```

## Embedded implementation

The car supervisor's `init`, `serviceWater` and `serviceSpray` show ADC12 sampling and how a water reading affects the tracks and pump. Its Timer_A0 interrupt enforces the pump deadline. Timer_A2 and a Port 2 interrupt time the sonar echo. USCI_A0 and USCI_A1 carry the Uno and FireBeetle UART traffic. The car sleeps in LPM0 between events. The dock program shows separate Hall and reservoir inputs, Booster LCD output and an independent refill cutoff on Timer_A1.

Earlier bench wiring and software are available in the [project's tagged Git history](https://github.com/Pskm12E/CEG2001-Sensor-Control-AND-CEG2002-Embedded-System-Design-Project/tree/One-Hit-Wounder).

To recreate the submission ZIP from a clean checkout, run `python Laptop/Tools/make_submission.py`. The packager includes the report PDF, presenter notes and diagram alongside the firmware and test sources.
