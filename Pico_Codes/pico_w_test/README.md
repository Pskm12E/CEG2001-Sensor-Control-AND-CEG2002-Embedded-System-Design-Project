# Pico W first connection test

**Historical standalone test.** The current Pico program is the
[wireless robot link](../../Wireless_Link/README.md). Uploading this LED test
will replace it. Wheel control now belongs to the Arduino Uno.

**Setup completed on 9 October 2026:** imported into VS Code, compiled successfully,
and uploaded to the connected Pico W. Five consecutive USB heartbeat messages were
received on **COM11**, confirming that the program runs on the board.

This C++ project blinks the Pico W's onboard LED and prints a USB message once per
second. It is the first step before connecting sensors and motor drivers. No
external components are needed. Use just the Pico W and a micro-USB **data** cable
for this test; leave the robot battery and actuator wiring disconnected.

## Folder contents

```text
Pico_Codes/
  pico_w_test/
    main.cpp                 Your program: start editing here
    CMakeLists.txt           Build settings and Pico W board selection
    pico_sdk_import.cmake   Official helper for loading the Pico SDK
    README.md               These instructions
    .gitignore              Excludes generated build files from Git
    build/                  Created when the project is compiled
```

`main.cpp` is a file, not a folder. You do not need another folder called
`Pico_Software` inside this project. The extension manages the SDK and tools
separately from your source code.

## Import and compile in VS Code

This project has already been imported on this computer. For everyday use, open
this `pico_w_test` folder in VS Code, edit `main.cpp`, and click **Compile** on the
bottom status bar. The steps below are for setting up the project again or on a
different computer.

1. Press **Ctrl+Shift+P** and run **Raspberry Pi Pico: Import Pico Project**.
2. Select the project folder:
   `D:\Programing\Sensor Joined Prj\Pico_Codes\pico_w_test`.
   Select this folder, rather than the parent `Pico_Codes` folder.
3. If asked for the board, select **Pico W / pico_w**. Use the C/C++ project
   workflow and the SDK/toolchain versions offered by the extension. Let it
   download any missing tools and finish importing/configuring the project.
4. If the imported project does not open automatically, use **File > Open Folder**
   and open the `pico_w_test` folder itself. The extension may add `.vscode` settings
   and update the CMake configuration during import; keep those generated files.
5. Run **Raspberry Pi Pico: Compile Pico Project** from the command palette.
6. A successful build creates `build\pico_w_test.uf2`. There is no need to create
   the `build` folder yourself.

The official Raspberry Pi Pico extension is already installed on this computer.
The separate MicroPico extension is for MicroPython; use the official Pico C/C++
workflow for this project.

## Transfer the program to the board

1. Unplug the Pico W from USB.
2. Hold its **BOOTSEL** button while plugging the USB data cable into the computer.
3. Release BOOTSEL when a drive called **RPI-RP2** appears in Windows File Explorer.
4. Copy `build\pico_w_test.uf2` onto that drive. This replaces the program on the
   Pico, so save any existing board program you need before doing this.
5. The drive should disappear and the board should restart. Its LED should stay on
   for half a second, then off for half a second, repeatedly.

On this computer, use the UF2 copy method above for uploading. The extension's
**Run Project** action uses picotool, which currently cannot access the BOOTSEL
device because its optional Windows driver is missing. The USB drive method was
tested successfully and does not require that driver. A debug probe is also not
needed for this method.

## See USB messages

After the program starts, look in Windows **Device Manager > Ports (COM & LPT)**
for the new USB serial COM port. Open it using a serial monitor, such as the one
in Arduino IDE, at **115200 baud**. Only one serial application can use the port
at a time. Expect a new line each second:

```text
Pico W connected | heartbeat 12 | LED ON
```

The number may already be above zero because the program starts before the
monitor opens. The LED should still blink without a monitor connected. The text
confirms this test program is running; it does not mean Wi-Fi is connected.

The verified port for this board after upload is **COM11**. Windows previously
used COM10 for its old MicroPython firmware. Check Device Manager again if the
port changes after reconnecting or changing firmware.

If there is no RPI-RP2 drive in BOOTSEL mode, try another known data cable and USB
port. If compilation reports a missing SDK, complete the Pico extension's import
and SDK setup first. If there is no serial port after copying the UF2, check that
the copy completed and that this USB-enabled firmware is running.

## Next project stages

After this test works, add one sensor at a time, then motor-driver control after
identifying the driver and motor ratings. Keep these simple bench tests separate
from the later integrated robot application.

For the finished robot, the **MSP430 remains the main controller**. The current
Pico role is the robot's wireless link; the Arduino Uno handles wheel control
and line sensing. The Pico-to-MSP bridge and spray-controller assignment still
need integration. This historical starter implements only onboard LED/USB output.

## Verification status and references

Verified on 9 October 2026:

- Pico SDK 2.3.1, Arm toolchain 15_2_Rel1, CMake 4.3.4 and Ninja 1.13.2 installed
  by the official Pico extension under `C:\Users\pyies\.pico-sdk`.
- Release build completed successfully for `pico_w` (RP2040).
- Output: `build\pico_w_test.uf2` (549,376 bytes).
- Uploaded through the board's RPI-RP2 USB drive.
- Five successive messages, heartbeat 18 through 22, received on COM11 at 115200.
- The program reports successful LED-driver initialization. Physical LED blinking
  was not visually inspected remotely.

The board's eight original MicroPython program/library files were backed up to
`..\board_backup_2026-10-09` before upload. The saved `main.py` and `boot.py` hashes
match the originals. This is a file backup, not a complete firmware image. The
board now starts this C++ test instead of its previous MicroPython application.
The backup folder is excluded from Git because old programs may contain
connection settings.

- [Official Raspberry Pi Pico VS Code extension](https://github.com/raspberrypi/pico-vscode)
- [Official Pico SDK C/C++ documentation](https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html)
- [Official LED example](https://github.com/raspberrypi/pico-examples/tree/master/blink)
- `pico_sdk_import.cmake` is the official SDK helper, downloaded from
  [Raspberry Pi's repository](https://raw.githubusercontent.com/raspberrypi/pico-sdk/master/external/pico_sdk_import.cmake)
  on 9 October 2026. Its upstream licence notice is retained in the file.
