# Zumo black-line follower with MSP430 stopping

**20 November update.** The MSP430 now runs the integrated three-second pump
profile after two user-confirmed bench runs. P1.6 drives the MOSFET gate and
P6.0 supplies raw water ADC readings. The normal supervisor has replaced the
LED test and is flashed/program-verified. Live status shows `READY=1`, `PUMP=0`,
`RUN=0`, all communication links ready and zero communication errors.

The confirmed-target sequence is stop, acknowledge, settle, spray for three
seconds, turn the pump off and resume with a fresh matching camera continuation.
The ultrasonic settings are **5 cm STOP / 7 cm clearance**. The installed Uno OG5 uses straight
speed 150 and an outside-track turn limit of 250. See [the cycle/pump guide](../../MSP430/robot_supervisor/PUMP_SETUP.md).
The full physical target-to-spray-to-resume trial remains pending.

## Previous installed milestone — 17 November 2026

Current setup, **17 November 2026**: Uno + Zumo Shield control the six reflectance
sensors and motors. MSP430F5529 measures the HC-SR04 and grants movement.
The user confirmed the driving setup is working. Uno **OG3** is user-installed;
the MSP no-echo update was flashed and program-verified. Source cleanup does not
upload firmware or change the original follower settings.

## Current stopping settings

| Condition | Result |
| --- | --- |
| Valid measured distance ≤ **5 cm** | MSP sends STOP; blocks a new sweep/start while near |
| Two valid readings ≥ **7 cm** | Clears the recent near inhibit |
| No fresh valid reading for about **300 ms** | Expires the old near inhibit |
| Missing / invalid echo, including startup | Diagnostic fault only; does not stop or block motion |
| Two consecutive valid readings ≥ **7 cm** after a line-following pause | Resumes if the Uno session is still healthy |
| Missing echo during a pause | Waits for valid clearance readings |
| Manual STOP, interrupted calibration, or link fault | A new local request is required |

The thresholds live in [obstacle_guard.h](../../MSP430/robot_supervisor/obstacle_guard.h).
Only 2–400 cm measurements are accepted; readings below 2 cm are invalid.
**The configured STOP trigger is 5 cm. Physical braking distance remains unmeasured.**
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
4. Press during motion or an obstacle pause to stop locally. Release the
   button, then press and release again to make a new request. MSP S2 also
   requests STOP.

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

Periodic status identifies **`FW=OG5`**. `CAL` is calibration complete, `SWEEP`
is calibration active, `RUN` is following, and `REQ` is a pending local request.
`STEP=n/80` shows sweep progress. `UP` is seconds since reset. `LAST` retains
the last motion event across stopped MSP STOP/HELLO exchanges; `REASON` can
return to zero during resynchronisation.

| `LAST` | Meaning |
| --- | --- |
| `BOOT` | No accepted sweep/start since reset |
| `SWEEP` / `CAL_DONE` / `FOLLOWING` | Sweep active / completed / following |
| `MSP_STOP` | MSP interrupted motion; inspect MSP diagnostics for its cause |
| `OBSTACLE_PAUSE` | MSP paused line following for a near ultrasonic reading |
| `MSP_RESYNC` | A new MSP session interrupted motion |
| `HEARTBEAT_LOST` | One-second Uno motion lease expired |
| `UART_ERROR` | Corrupt/partial frame or receive overflow |
| `LOCAL_STOP` | Button or USB STOP |
| `SESSION_ERROR` | Session/sequence or other protocol failure |

`OBSTACLE_PAUSE` identifies a pause eligible for automatic resume. The MSP
requires two consecutive valid clear readings and the same healthy Uno session.
Its `SONAR` diagnostics report `NO_ECHO_STOP=OFF` for the no-echo policy during
normal driving. The camera-based spray job has its own continuation rules.

## Build and verification

From the repository root:

```powershell
./Car/Arduino_Uno/build_zumo.ps1
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo -PumpDriverVerified -SpraySeconds 3
python Car/Arduino_Uno/tests/check_zumo.py
python Car/MSP430/tests/check_ultrasonic.py
```

These commands compile and run host tests. Upload Uno **OG5** and the matching
MSP430 supervisor to enable automatic resume. The Uno build uses Pololu
**ZumoShield 2.1.0**, AVR core **1.8.8**, Wire and SoftwareSerial. In Arduino IDE,
open the repository sketch `zumo_line_follow.ino`, select Arduino Uno, and keep
both headers beside it.

Arduino copies the sketch into its build directory. Its bundled `robot_link.h`
must remain byte-identical to `../msp_line_follow/robot_link.h`, used by MSP code;
both the builder and host test check this. The MSP output is
`Car/MSP430/robot_supervisor/Debug_wifi_zumo_pump/robot_supervisor.out`. CCS GUI
builds for this profile define `SUPERVISOR_ESP_UART`, `ZUMO_BASE=1` and
`PUMP_DRIVER_VERIFIED=1`. The `IR_DRIVING_TEST` bypass
is rejected for Zumo. Do not upload the previous L298N sketches.

Host checks exercise the actual sketch, MSP scheduler, sonar adapter and bridge
parser with simulated hardware. The user reported the robot working after the
installed no-echo update; full-track performance, range accuracy and physical
braking distance remain unmeasured. Dated reports are kept in
[verification](../../../Laptop/Artifacts/verification).
