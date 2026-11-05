# Car XIAO ESP32-S3 Sense — wireless camera

Current source: [xiao_camera_wifi.ino](xiao_camera_wifi/xiao_camera_wifi.ino).
Firmware identity: **CAMERA_WIFI_V1**. The detected camera is OV3660.

The board joins the FireBeetle private network and streams JPEG video through
the desk Pico to the laptop. The tested stream is 320 × 240 at about 15 fps.
USB-C provides power from the power bank; video does not need a laptop USB cable.

```powershell
python Laptop/Tools/Communication/configure.py
./Car/XIAO_ESP32S3_Camera/build_camera_wifi.ps1
```

This compiles only. Arduino target: `esp32:esp32:XIAO_ESP32S3:PSRAM=opi`.
The camera's possible future onboard AI deployment is separate work. The current
blue-square detector, and the proposed trained YOLO model, run on the laptop.

`Archive/xiao_camera_usb` and its builder are superseded USB bench software.
They are retained for history and are not the current wireless camera firmware.
