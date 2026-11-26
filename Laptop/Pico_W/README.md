# Desk Raspberry Pi Pico W

**18 November update — desk Pico V3 installed and identity verified:** ESP32 DIRECT_WIFI_V2 and
Pico DESK_BRIDGE_V3 support correlated target jobs and STOP. The MSP alone owns
the bounded pump pulse and token-gated continuation; no direct pump-on/start API
is exposed. The current car runs the OG9 Uno sketch and the P1.6 pump-enabled
MSP supervisor. [Car and docking behavior](../../README.md)

The 18 November video-buffer fix is also installed. A completed JPEG now remains
available while the next frame arrives in arbitrary TCP fragments. Two bounded
32 KiB buffers swap on completion; older completed frames can be replaced, but
partial frames never erase or overwrite a publishable image. Live receive rate
improved from 4.4–6.6 to 12.9–13.3 fps, with no >400 ms gaps in either updated
150-frame check. [Evidence](../Artifacts/verification/video-stability-2026-11-18.json).

Current source: [laptop_wifi_bridge/main.cpp](laptop_wifi_bridge/main.cpp).
Firmware identity: **DESK_BRIDGE_V3** (V2 remains supported for monitoring only).

This Pico belongs beside the laptop, connected by USB data/power. It joins the
car's ESP32 private Wi-Fi and relays continuous camera video plus robot status.
It has no GPIO wires to the car and does not run YOLO or drive the motors.

```powershell
./Laptop/Tools/Communication/build_desk_pico.ps1
```

This builds only, using the existing Pico SDK/toolchain. The generated UF2 is
ignored. `cmake/pico_sdk_import.cmake` retains Raspberry Pi's original licence.
The desk Pico relays messages. The Uno controls the track motors.

[Current desk setup](../Tools/Communication/desk-pico-setup.md).
