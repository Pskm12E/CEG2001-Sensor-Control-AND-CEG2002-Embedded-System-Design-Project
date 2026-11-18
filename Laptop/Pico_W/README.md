# Desk Raspberry Pi Pico W

**18 November update — desk Pico V3 installed and identity verified:** ESP32 DIRECT_WIFI_V2 and
Pico DESK_BRIDGE_V3 support correlated target jobs and STOP. The MSP alone owns
the bounded pump pulse and token-gated continuation; no direct pump-on/start API
is exposed. MSP is updated; user-installed Uno OG4 is confirmed, and FireBeetle V2
is installed/identified. After the MSP UART idle-restart fix, the complete
robot-status route is verified while stopped. Pump remains disabled.

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
Older Pico motor/I2C experiments are in [Car/Archive](../../Car/Archive/README.md).

[Current desk setup](../Tools/Communication/desk-pico-setup.md).
