# Desk Raspberry Pi Pico W

Current source: [laptop_wifi_bridge/main.cpp](laptop_wifi_bridge/main.cpp).
Firmware identity: **DESK_BRIDGE_V2**.

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
