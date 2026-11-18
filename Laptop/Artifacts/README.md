# Saved project artifacts

## Target-cycle source — 18 November 2026

[Installed-board status](verification/target-spray-installation-2026-11-18.json) ·
[Source/build test report](verification/target-spray-source-2026-11-18.json) ·
[Complete Uno OG4 source ZIP](setup/zumo_line_follow_OG4.zip) ·
[Pump wiring and current installation limits](../../Car/MSP430/robot_supervisor/PUMP_SETUP.md).
New source uses 5 cm STOP / 7 cm clearance and a three-second target spray cycle.
Default pump output is disabled pending driver qualification. Builds/software
tests do not mean that these images have been flashed or physically validated.

Current diagrams: [boards and wiring](diagrams/robot-system-connections-2026-11-05.png)
and [proposed laptop YOLO](diagrams/yolo-laptop-architecture-2026-11-05.png).
Dated reports cover the October bench release and November integration work.
Private camera images and compiled firmware are kept local, outside this index.

| Folder/file | Contents | Status |
| --- | --- | --- |
| [diagrams/plant-care-robot-concept.png](diagrams/plant-care-robot-concept.png) | Earlier illustrated system concept | Historical; board roles have changed |
| [diagrams/plant-care-robot-concept.prompt.txt](diagrams/plant-care-robot-concept.prompt.txt) | Concept illustration generation/edit prompts | Historical source |
| [pdf/plant-care-robot-setup-guide.pdf](pdf/plant-care-robot-setup-guide.pdf) | Early setup guide, 6 October | Historical; use current wiring notes |
| [setup/build_robot_setup.py](setup/build_robot_setup.py) | ReportLab source for that PDF | Early design; local path in script |
| [setup/uno_sensor_bench](setup/uno_sensor_bench) | Earlier standalone sensor bench sketch | Check its own pins; not the current line follower |
| [verification/](verification) | Saved dashboard screenshots and JSON test reports | Dated bench, integration and Zumo reports |

For the current system layout, use the [diagram gallery](../Documentation/diagrams/README.md)
and [board-placement guide](../Tools/Communication/board-placement.md).

These files document tested components and earlier designs. They do not certify
complete pest recognition, autonomous navigation, spraying, docking or charging.


## Current Zumo milestone — 17 November 2026

- [User-confirmed milestone and cleanup checks](verification/zumo-working-cleanup-2026-11-17.json)
- [Complete OG3 source package](setup/zumo_line_follow_OG3.zip)
- [Installed MSP no-echo policy and readback](verification/msp430-no-echo-ignore-2026-11-17.json)
- [Earlier MSP stop-source diagnosis](verification/msp430-stop-source-2026-11-17.json)

The user reported the driving setup working after the no-echo update. The
current configured trigger is **2 cm**, clearance **4 cm**; missing echoes do not
stop motion. Historical reports above retain the settings that applied on their
dates. They are not physical braking-distance guarantees. See the
[current Zumo operating guide](../../Car/Arduino_Uno/zumo_line_follow/README.md).
