# Car MSP430 — main controller

Board: **MSP-EXP430F5529LP**. Current source:
[robot_supervisor/main.c](robot_supervisor/main.c).

Use the **ESP-UART** configuration for the integrated robot:

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart
```

This compiles only; it does not upload. It produces the ignored
`robot_supervisor/Debug_wifi/robot_supervisor.out`. Tool paths refer to the
existing Windows CCS installation and may need adjustment on another computer.

- ESP32 IO17 TX → MSP P4.2 RX; MSP P4.1 TX → ESP32 IO16 RX; common GND.
- MSP P3.3 TX → Uno D5 RX; Uno D6 TX → existing divider → MSP P3.4 RX.
- Owns supervision, command checks and timeout behaviour. It does not run YOLO.
- `robot_led_test` and `robot_usb_console` are earlier standalone bench programs.
  Uploading one would replace the supervisor already installed on the board.

Reopen/import the project from this new folder in CCS if its old workspace entry
points to the previous location. Source/project names are retained.
