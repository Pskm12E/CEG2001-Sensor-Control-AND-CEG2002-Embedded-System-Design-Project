# Car FireBeetle ESP32 — Wi-Fi and UART gateway

**Installed 18 November 2026: DIRECT_WIFI_V2**, flashed on COM20 with all four
segments hash-verified. USB PING, STATUS and STATE confirm V2 and AP ready.
The desk Pico Wi-Fi link and live camera recovered after the restart. The user
initially unplugged the MSP430 for upload. After reconnecting it, corrected an
MSP UART idle-transmit bug; fresh MSP/Uno status now reaches the dashboard with
zero UART errors while stopped. The current car supervisor controls the verified
P1.6 spray output. The FireBeetle relays its commands and status.

Board: **DFRobot FireBeetle ESP32 DFR0478**. Source:
[robot_wifi_gateway.ino](robot_wifi_gateway/robot_wifi_gateway.ino).
It owns the private 2.4 GHz access point and UART bridge. Correlated target jobs
and token-matched continuation are supervised by the MSP; no unrestricted START
or pump-on command is exposed. USB identity and JSON identity both report V2.

Build from the repository root:

```powershell
python Laptop/Tools/Communication/configure.py
./Laptop/Tools/Communication/build_direct.ps1 -Zumo -PumpDriverVerified
```

For a deliberate installation, use the FireBeetle's current USB port. The
example below uses the port assigned on the project laptop.

```powershell
./Laptop/Tools/Communication/upload_esp32.ps1 -Port COM20
```

The helper always selects the car gateway image. It checks CH340 USB identity
and uses the uncompressed ROM-loader method. Older commands with `-Direct`
also select the car gateway.
Compilation alone does not upload. Private settings, generated network headers
and compiled images stay ignored; reuse the saved network settings across boards.

[Wiring](../../Laptop/Tools/Communication/direct-wifi-wiring.md):
GPIO17/LRCK TX → MSP P4.2 RX; GPIO16/DI RX ← MSP P4.1 TX; common GND.
[Flash/readback evidence](../../Laptop/Artifacts/verification/firebeetle-v2-flash-2026-11-18.json).
