# Zumo black-line follower with MSP430 stopping

**18 November update — installation partly complete:** 5 cm STOP / 7 cm clearance;
blue-target stop → 3-second spray → token-matched continuation. Uno OG4 raises
the positive turn limit to 250 while straight speed stays 150. Pump gate P1.6,
raw water ADC P6.0. The pump driver is disabled until its electrical rating is
verified. Read [the current cycle/pump guide](../../MSP430/robot_supervisor/PUMP_SETUP.md). MSP 5 cm / 7 cm pump-disabled firmware and Pico V3 are installed/verified.
The user will upload Uno OG4; FireBeetle V2 is deferred. Full automatic spraying
is not yet ready for physical use. The earlier installed milestone is history below.

## Previous installed milestone — 17 November 2026

Current setup, **17 November 2026**: Uno + Zumo Shield control the six reflectance
sensors and motors. MSP430F5529 measures the HC-SR04 and grants movement.
The user confirmed the driving setup is working. Uno **OG3** is user-installed;
the MSP no-echo update was flashed and program-verified. Source cleanup does not
upload firmware or change the original follower settings.

## Current stopping settings

| Condition | Result |
| --- | --- |
| Valid measured distance ≤ **2 cm** | MSP sends STOP; blocks a new sweep/start while near |
| Two valid readings ≥ **4 cm** | Clears the recent near inhibit |
| No fresh valid reading for about **300 ms** | Expires the old near inhibit |
| Missing / invalid echo, including startup | Diagnostic fault only; does not stop or block motion |
| Range clears after a STOP | Stays stopped until another local request |

The thresholds live in [obstacle_guard.h](../../MSP430/robot_supervisor/obstacle_guard.h).
Only 2–400 cm measurements are accepted; readings below 2 cm are invalid.
**2 cm is a configured trigger, not a validated physical braking distance.**
A failed/disconnected sonar cannot stop the car under this requested policy.
Manual STOP, corrupt UART/session handling and the Uno's **1000 ms lease** remain
active. No echo does not mean an obstacle-free path.

## Button sequence

1. Power both controllers and the Zumo motor supply. Put the array over the
   black line on white with room for the sweep to cross both colours.
2. Once the MSP/Uno link is ready, **press and release once** to request
   calibration. Following the MSP grant, it waits one second and runs the
   original 80-step sweep at ±200, with 20 ms gaps and sensor sampling.
3. Completion stops the motors and sets `CAL=1`. Re-centre if needed, then
   **press and release again** to request line following.
4. Press during motion to stop locally; the same press's release is consumed.
   MSP S2 also requests STOP. A new press/release requests a restart.

An interrupted sweep leaves `CAL=0`, so the next request repeats calibration.
An Uno reset clears calibration. Opening Serial Monitor can reset the Uno.
USB connection itself does not deliberately request a second calibration.

The original algorithm is preserved: `readLine(sensors)`, centre **2500**,
`kp=1`, `kd=0`, `MAX_SPEED=150`, and **upper-only** speed clamps; negative motor
commands remain possible. Sweep direction changes at the original step ranges.
A completed 80-step sweep is accepted without an added contrast-rejection gate.
Expose the array to real black and white for useful calibration. The sweep is
serviced in steps so MSP STOP/lease checks continue during it.

## Connections

All grounds join the common GND rail. The two voltage dividers are separate.

| From | To |
| --- | --- |
| MSP430 P3.3 TX | Zumo/Uno D6 RX |
| Uno D13 TX | 2.2 kΩ → junction → MSP430 P3.4 RX |
| Same Uno-TX junction | 2.2 kΩ → GND |
| ESP32 GPIO17 / LRCK TX | MSP430 P4.2 RX |
| MSP430 P4.1 TX | ESP32 GPIO16 / DI RX |
| HC-SR04 VCC / GND | 5 V / common GND |
| MSP430 P3.2 | HC-SR04 TRIG |
| HC-SR04 ECHO | 2.2 kΩ → junction → MSP430 P2.7 |
| Same ECHO junction | 3.3 kΩ → GND |
| Water sensor V/+ and G/- | MSP430 3.3 V and common GND |
| Water sensor S | MSP430 P6.0 / ADC A0 |
| Uno, MSP430, ESP32, sonar and water sensor GND | Common GND |

The Uno-TX divider nominally gives 2.5 V from 5 V; the ECHO divider gives 3.0 V.
These are calculated values, not voltage measurements. Do not connect either
5 V signal directly to an MSP input. ESP/MSP UART uses 3.3 V logic directly.
Common ground does not require joining different positive supply outputs.

`SoftwareSerial(6, 13)` means **RX first, TX second**, at **9600 baud, 8N1**.
D13 is also the shield's yellow LED, so UART activity may light it. Reserve it
for TX; do not use `LED_BUILTIN` as a run indicator. Default array inputs are
D4/A3/D11/A0/A2/D5, emitter control D2, motors D7/D8/D9/D10, user button D12.
See [Pololu's shield pin table](https://www.pololu.com/docs/0J57/5),
[array connections](https://www.pololu.com/docs/0J57/2.c), and the
[MSP430F5529 datasheet](https://www.ti.com/lit/ds/symlink/msp430f5529.pdf).

The Uno plugs directly into the shield. **No L298N or separate two-IR wiring
is used.** Water ADC logic is pending; **pump/MOSFET/driver are not connected**.

## USB diagnostics

Use **9600 baud and newline**. Commands are case-insensitive.

| Command | Effect |
| --- | --- |
| `C` | Request a powered calibration from MSP |
| `F` | Request following; requires calibration and MSP grant |
| `S` / `STOP` | Stop locally |
| `STATUS` | Request the two status lines |

Periodic status identifies **`FW=OG3`**. `CAL` is calibration complete, `SWEEP`
is calibration active, `RUN` is following, and `REQ` is a pending local request.
`STEP=n/80` shows sweep progress. `UP` is seconds since reset. `LAST` retains
the last motion event across stopped MSP STOP/HELLO exchanges; `REASON` can
return to zero during resynchronisation.

| `LAST` | Meaning |
| --- | --- |
| `BOOT` | No accepted sweep/start since reset |
| `SWEEP` / `CAL_DONE` / `FOLLOWING` | Sweep active / completed / following |
| `MSP_STOP` | MSP interrupted motion; inspect MSP diagnostics for its cause |
| `MSP_RESYNC` | A new MSP session interrupted motion |
| `HEARTBEAT_LOST` | One-second Uno motion lease expired |
| `UART_ERROR` | Corrupt/partial frame or receive overflow |
| `LOCAL_STOP` | Button or USB STOP |
| `SESSION_ERROR` | Session/sequence or other protocol failure |

`MSP_STOP` alone does not identify an ultrasonic stop. The MSP distinguishes
near-obstacle messages from link/manual STOP, and its `SONAR` diagnostics report
`NO_ECHO_STOP=OFF`. The laptop dashboard is read-only; Wi-Fi cannot grant starts
or calibration. Motion is never started automatically at boot or after a fault.

## Build and verification

From the repository root:

```powershell
./Car/Arduino_Uno/build_zumo.ps1
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo
python Car/Arduino_Uno/tests/check_zumo.py
python Car/MSP430/tests/check_ultrasonic.py
```

These commands compile/test only. The Uno build uses Pololu **ZumoShield 2.1.0**,
AVR core **1.8.8**, Wire and SoftwareSerial. Arduino IDE uploads remain manual:
open `zumo_line_follow.ino`, select Arduino Uno, and keep both headers beside it.
The [source ZIP](../../../Laptop/Artifacts/setup/zumo_line_follow_OG3.zip) contains
the complete sketch folder and this guide.

Arduino copies the sketch into its build directory. Its bundled `robot_link.h`
must remain byte-identical to `../msp_line_follow/robot_link.h`, used by MSP code;
both the builder and host test check this. The MSP output is
`Car/MSP430/robot_supervisor/Debug_wifi_zumo/robot_supervisor.out`. CCS GUI builds
must define `SUPERVISOR_ESP_UART` and `ZUMO_BASE=1`. The `IR_DRIVING_TEST` bypass
is rejected for Zumo. Do not upload the previous L298N sketches.

Host checks exercise the actual sketch, MSP scheduler, sonar adapter and bridge
parser with simulated hardware. The user reported the robot working after the
installed no-echo update; full-track performance, range accuracy and physical
braking distance remain unmeasured. Dated reports are kept in
[verification](../../../Laptop/Artifacts/verification).
