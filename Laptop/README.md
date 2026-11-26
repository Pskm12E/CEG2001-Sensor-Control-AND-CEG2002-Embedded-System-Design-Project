# Laptop software and desk Pico

| Folder | Purpose |
| --- | --- |
| [Dashboard](Dashboard/README.md) | Local Python app, live video, blue-square detector and tests |
| [Pico_W](Pico_W/README.md) | Current desk Pico firmware; USB to the laptop and Wi-Fi to the car |
| [YOLO_Model](YOLO_Model/README.md) | Intended location for future trained insect model weights; no model yet |
| [Tools/Communication](Tools/Communication/README.md) | Shared radio configuration, protocol library, builders, consoles and checks |
| [Documentation](Documentation/diagrams/README.md) | Wiring notes and diagram gallery |
| [Artifacts](Artifacts/README.md) | Saved diagrams, historical PDF and dated test reports |

Start the local app with [Start Robot.cmd](../Start%20Robot.cmd) at the project root.
It opens the dashboard, connects the desk Pico and starts wireless video.
[Dashboard/Start Dashboard.cmd](Dashboard/Start%20Dashboard.cmd) runs the same sequence.
The live route is camera/car ESP32 → desk Pico → USB → local dashboard.
Open [the local dashboard](http://127.0.0.1:8765) on this laptop. The robot uses its own private Wi-Fi network.
