# Laptop software and desk Pico

| Folder | Purpose |
| --- | --- |
| [Dashboard](Dashboard/README.md) | Local Python app, live video, blue-square detector and tests |
| [Pico_W](Pico_W/README.md) | Current desk Pico firmware; USB to the laptop and Wi-Fi to the car |
| [YOLO_Model](YOLO_Model/README.md) | Intended location for future trained insect model weights; no model yet |
| [Tools/Communication](Tools/Communication/README.md) | Shared radio configuration, protocol library, builders, consoles and checks |
| [Documentation](Documentation/diagrams/README.md) | Wiring notes and diagram gallery |
| [Artifacts](Artifacts/README.md) | Saved diagrams, historical PDF and dated test reports |
| [Deployment](Deployment/README.md) | Hosted-preview instructions; not required for local robot operation |
| Archive | Superseded desk-side ESP32 gateway |

Start the local app with [Dashboard/Start Dashboard.cmd](Dashboard/Start%20Dashboard.cmd).
The live route is camera/car ESP32 → desk Pico → USB → local dashboard.
The laptop can retain its ordinary Wi-Fi/internet connection.
