# Zumo black-line follower with MSP430 stopping

## Empty-tank reverse

During an active line run, two consecutive P6.0 readings below 500 switch
OG9 to straight reverse. Both tracks run at −100 while the MSP430 renews the
reverse command. Two consecutive readings above 500
return a reversing robot to forward line following. Exactly 500 keeps the
current direction.
The Zumo button, MSP STOP, a front obstacle, or loss of the drive link can
also stop it. Keep the path behind the robot clear. A manual stop requires a
new local start even if the probe subsequently gets wet.

USB status reports `LAST=EMPTY_REVERSE` during reverse. The Uno stops if it
goes one second without a fresh reverse grant. The supervisor stops renewing
grants if the water ADC goes three seconds without a completed conversion.

## Flip alarm

The Uno uses the Zumo Shield's accelerometer to detect a flip. On the first
line calibration after installing this firmware, place the car flat on its
tracks before tapping the Zumo button. During the one-second pause before
the tracks spin, the Uno learns which direction is upright. It saves that
direction across power cycles. Later line calibrations can update it if the
sensor mounting changes. Turning the robot over at power-up cannot change it.

The alarm starts enabled and waits quietly for a valid upright reference.
About 0.4 seconds upside down triggers a short beep every 0.75 seconds.
Placing the robot on its side or back on its tracks silences it.

With the robot parked, hold the **Zumo user button** for two seconds to toggle the
alarm. Release it before making another selection. The Uno saves the setting
across power cycles. A short tap still requests calibration or line following.
During motion or an obstacle pause, pressing the button stops the run first.

On Uno USB at 9600 baud, send `ALARM OFF` or `ALARM ON` with a newline.
`STATUS` shows the setting, sensor connection, flipped flag, raw vertical
acceleration (`Z`) and saved upright direction (`UP_Z`). A value of
`UP_Z=0` means the reference is still needed. Repeat the calibration with
the robot flat and still. A learned reference reads `UP_Z=1` or `UP_Z=-1`.
If `FLIPPED=1` appears while inverted but the buzzer is silent, check the
shield's buzzer jumper. The two pins marked **328P** connect BZ to Uno D3.
[Pololu jumper guide](https://www.pololu.com/docs/0J57/3.c)

## MSP430 spray and obstacle settings

The MSP430 owns the ultrasonic pause and the target-triggered spray sequence.
The Uno applies a stop to both tracks before acknowledging it. The MSP then
waits about 300 ms before starting its three-second P1.6 pulse.
[Pump wiring and job sequence](../../MSP430/robot_supervisor/PUMP_SETUP.md)

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
2. On first use, once the MSP/Uno link is ready, **press and release once** to request
   calibration. Following the MSP grant, it waits one second and runs the
   original 80-step sweep at ±200, with 20 ms gaps and sensor sampling.
3. Completion stops the motors and sets `CAL=1`. The Uno saves each sensor's
   minimum and maximum to EEPROM when all six saw a range. Re-centre if needed, then
   **press and release again** to request line following.
4. Press during motion or an obstacle pause to stop locally. Release the
   button, then press and release again to make a new request. MSP S2 also
   requests STOP.

On later power-ups the Uno restores the saved readings and starts parked with
`CAL=1` and `LAST=CAL_RESTORED`. Put it on the line and tap once to drive.
To replace the readings for a new track or different lighting, send `C` to
the parked Uno using Serial Monitor at 9600 baud with newline. A successful
save prints `Line calibration saved.` An interrupted sweep leaves the previous
EEPROM record intact. A missing or invalid record makes the first tap request a sweep.

On a centred line, both tracks run at `FOLLOW_SPEED=90` (out of 400) to give
the camera more time to confirm a blue square. Steering uses `readLine(sensors)`
with centre **2500**, `kp=1` and `kd=0`. On sharp turns the outside track can
reach +250 and the inside track can reach −400. Sweep direction changes at the original step ranges.
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

The Uno plugs into the Zumo Shield, which carries the track driver and six
line sensors. The MSP430 samples the water probe on P6.0 and drives the pump
MOSFET gate on P1.6. The pump uses a separate four-AA supply.

## USB diagnostics

Use **9600 baud and newline**. Commands are case-insensitive.

| Command | Effect |
| --- | --- |
| `C` | Request a powered calibration from MSP |
| `F` | Request following; requires calibration and MSP grant |
| `S` / `STOP` | Stop locally |
| `ALARM OFF` / `ALARM ON` | Mute or enable the flip alarm and save the setting |
| `STATUS` | Request motion, last event and flip alarm status |

Periodic status identifies **`FW=OG9`**. `CAL` is calibration complete, `SWEEP`
is calibration active, `RUN` is following, and `REQ` is a pending local request.
`STEP=n/80` shows sweep progress. `UP` is seconds since reset. `LAST` retains
the last motion event across stopped MSP STOP/HELLO exchanges; `REASON` can
return to zero during resynchronisation.

| `LAST` | Meaning |
| --- | --- |
| `BOOT` | No accepted sweep/start since reset |
| `CAL_RESTORED` | Loaded the six saved line-sensor ranges at startup. Tracks are parked. |
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

These commands compile and run host tests. Upload Uno **OG9** and the matching
MSP430 supervisor to enable automatic resume. The Uno build uses Pololu
**ZumoShield 2.1.0**, AVR core **1.8.8**, Wire and SoftwareSerial. In Arduino IDE,
open the repository sketch `zumo_line_follow.ino`, select Arduino Uno, and keep
its bundled headers beside it.

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
