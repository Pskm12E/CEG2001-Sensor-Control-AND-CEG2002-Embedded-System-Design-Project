# Car FireBeetle ESP32 — Wi-Fi and UART gateway

Board: original **DFRobot FireBeetle ESP32 DFR0478**. Current source:
[robot_wifi_gateway.ino](robot_wifi_gateway/robot_wifi_gateway.ino).

Creates the existing private 2.4 GHz network for the XIAO camera and desk Pico.
Bridges robot status over UART to the main MSP430. It does not run the laptop's
detector and is separate from the XIAO ESP32-S3 camera board.

Build both the current gateway and matching MSP430 firmware from the repo root:

```powershell
python Laptop/Tools/Communication/configure.py
./Laptop/Tools/Communication/build_direct.ps1
```

Private settings stay in ignored
`Laptop/Tools/Communication/local-network.json`; generated `NetworkConfig.h` and
compiled firmware also remain ignored. Reuse the existing settings when building
all radio boards. The build script does not upload or move the robot.

[Wiring](../../Laptop/Tools/Communication/direct-wifi-wiring.md):
IO17/LRCK TX → MSP P4.2 RX; IO16/DI RX ← MSP P4.1 TX; GND ↔ GND.
