# Robot communications

The FireBeetle ESP32 on the car hosts the private access point. Both the XIAO camera and the desk Pico W join it. The laptop uses its USB connection to the desk Pico for video and commands. The FireBeetle relays control and telemetry between the Pico and the car MSP430. The station's application UART connects separately to laptop USB for coordinated refilling.

| Connection | What it carries |
| --- | --- |
| XIAO camera → Pico W, Wi-Fi TCP 4243 | JPEG frames, sequence number and CRC |
| Pico W ↔ laptop, USB | Dashboard commands, current readings and video |
| Pico W ↔ FireBeetle, Wi-Fi | Robot status and bounded requests |
| FireBeetle ↔ car MSP430, 3.3 V UART at 9600 baud | Supervisor requests, replies and readings |
| Car MSP430 ↔ Uno, UART at 9600 baud | Motion permission, STOP and acknowledgement |
| Station MSP430 ↔ laptop, USB backchannel at 9600 baud | Dock visit, pump state, hold permit and full indication |

## Build on Windows

1. Install Python 3, Arduino IDE 2 or Arduino CLI with cores `arduino:avr` and `esp32:esp32`, and the Pololu ZumoShield library. Install TI's MSP430 compiler and device headers for the car and dock.
2. For the Pico W, install the Raspberry Pi Pico C/C++ SDK, ARM toolchain, CMake, Ninja and Pico tools. The PowerShell helper uses the versioned layout of the Windows Pico SDK installation. Its paths are at the top of [build_desk_pico.ps1](build_desk_pico.ps1).
3. Run `python Laptop/Tools/Communication/configure.py` once on the build computer. This creates local Wi-Fi credentials and the generated header used by the FireBeetle, XIAO and desk Pico. Reuse those settings across builds.
4. Build the board images with the commands in the [main README](../../../README.md#build-the-firmware). Keep generated settings and board images on the build computer.

For another Windows installation, set `ARDUINO_CLI` or put Arduino CLI on PATH. Set `MSP430_CGT_ROOT` and `MSP430_DEVICE_ROOT` to your TI compiler and device-support directories. Use `ROBOT_PYTHON` to select a particular Python executable.

[Board wiring](board-placement.md) · [FireBeetle UART](direct-wifi-wiring.md) · [Desk Pico setup](desk-pico-setup.md)
