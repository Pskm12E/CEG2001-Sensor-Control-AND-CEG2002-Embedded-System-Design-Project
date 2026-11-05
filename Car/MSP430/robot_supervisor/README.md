# Robot MSP430 supervisor + Uno line follower

## Current ESP UART build — 5 November 2026

Use [the direct Wi-Fi guide](../../../Laptop/Tools/Communication/direct-wifi-wiring.md) for the
accepted ESP32 -> MSP430 -> Uno route. Build with
`Car/MSP430/build_robot_supervisor.ps1 -EspUart`; this maps UART1 to **P4.1 TX /
P4.2 RX**, disables the unused I2C endpoint, and accepts correlated identity,
status and stop commands from the ESP. The USB backchannel instructions below
apply only to the older default build. Uno wiring is retained.

The base supervised line-following firmware was uploaded to both boards on
**3 November 2026**. The source now also includes an I2C status/stop-request
endpoint, **uploaded, flash-verified and USB-tested on the robot MSP430 on
3 November**. Physical I2C wiring has not yet been tested. The Uno program is unchanged. See the
[Pico bridge wiring and tests](../../../Laptop/Tools/Communication/msp-bridge-wiring.md).
Pest detection, spraying, dock control and ADC sensing remain unimplemented.

The **robot MSP430 is the main controller**. It sends start/stop/calibration
requests and keepalive messages. The Uno reads the two IR sensors, steers the
L298N and enforces local stop limits. Neither board starts the car at boot.

## Start here

IR calibration is deferred for the current communication-integration work.
The following steps are for the later physical line-following test.

Keep the motor battery disconnected while calibrating and checking the readings.
Use the MSP430's **Application UART, COM13 on this laptop, 9600 baud, newline**.
Close the old website/other serial terminals if they hold that port.

1. Wait for `LINK READY; STOPPED`.
2. Put **both** IR sensors over white at their mounted height. Send `W` and
   Enter. Hold them still for at least half a second.
3. Put **both** over black. Send `B` and Enter, then hold still again.
4. Send `STATUS`. You need `CAL=READY`; centred on the wide black strip,
   `L2=BLACK R4=BLACK`. `NC` means calibration is incomplete or has no contrast.
5. For the physical test, check motor wiring and common ground, secure the car
   for an initial wheels-raised test, and connect the motor battery. Send `F`
   to start; send `S` to stop. The two forward-polarity constants retain the
   earlier sketch's settings and must match the actual motor wiring.

Calibration is in RAM and must be repeated after an Uno reset/power cycle.
The existing ENA/ENB jumpers give **full drive**, not PWM speed control.
Both sensors must see black when centred; this is a wide-strip arrangement.

| MSP430 USB command | Behaviour |
| --- | --- |
| `PING` | Identify supervisor V2 |
| `STATUS` | Link, run authorisation, calibration and last received sensor state |
| `W` / `B` | Sample both sensors over white / black, motors stopped |
| `C` | Stop and clear calibration |
| `F` | Request following; rejected unless calibrated, stable and both black |
| `S` | Stop; waits for acknowledgement then establishes a stopped session |
| `H` or `LINK` | Establish a new stopped session |
| `HELP` | Command summary |

MSP **S2** requests stop. MSP LED1 double-blinks; LED2 shows acknowledged
following authorisation. Uno D13 shows its following state. Uno USB uses
**115200 baud**: `S` is a local stop and `STATUS` reports diagnostics;
typing `F` on the Uno USB port cannot authorise movement.

The Version 1 website expects the old bench telemetry/LED commands. It is not
yet integrated with this supervisor; use the MSP serial console for this stage.
Do not run the old bench upload/tests against this new firmware.

## Wiring retained

| From | To |
| --- | --- |
| MSP P3.3 TX | Uno D5 RX |
| Uno D6 TX, green wire | 1 kOhm resistor -> divider junction |
| Divider junction, yellow wire | MSP P3.4 RX |
| Divider junction | Two 2.2 kOhm resistors in parallel -> common GND |
| Uno GND / MSP GND / divider bottom | Common ground |
| Left IR OUT / right IR OUT | Uno D2 / D4 |
| IR VCC / GND | 3.3V / GND |
| Uno D7 / D8 / D9 / D10 | L298N IN1 / IN2 / IN3 / IN4 |

The resistor layout is user-reported; its voltage and worst-case logic margins
have not been measured. The nominal output is 2.62V for a 5V input. A dedicated
ground jumper has not been independently checked; do not rely on laptop USB
ground when changing to battery supplies. Never connect Uno D6 directly to
MSP GPIO. Disconnect power before rewiring.

Leave one jumper cap across the **RXD pair** and one across the **TXD pair** in
the MSP middle isolation block. They serve USB UART1. The external Uno link
uses the separate **side-header P3.3/P3.4 UART0**. Do not bridge RXD to TXD.

## Stop behaviour and protocol

- The MSP sends keepalives about every 200ms while following. It waits for each
  reply before sending another request; SoftwareSerial is not full duplex.
- The Uno stops and invalidates the session if no fresh valid keepalive arrives
  for 1000ms. Duplicate sequence numbers do not refresh that deadline. A frame
  error, local stop, prolonged unstable sensor or line-loss limit also stops it.
- The MSP drops run authorisation on a missing acknowledgement after about
  500ms, sends STOP and re-establishes a stopped session. Recovery never restarts
  movement automatically: another explicit `F` is required.
- The Uno has a one-second hardware watchdog, cleared only by its main loop.
- Sensor filtering is 8ms. Unstable input stops outputs while settling and
  latches a stop after 150ms. A correction has a 750ms limit. If both sensors
  lose black, only a recent turn direction may be searched, for at most 250ms;
  otherwise the robot stops. These timings need track tuning.

The shared definition is
`Car/Arduino_Uno/msp_line_follow/robot_link.h`, included by both compilers. Frames
contain `A5 5A`, type, 16-bit session, 16-bit sequence, argument, detail and
CRC16-CCITT-FALSE. Multi-byte fields use little-endian encoding. A reply echoes
session/sequence and sets bit 7 of the type. HELLO establishes a stopped session;
START requires calibration, KEEP alone cannot start, and STOP is always accepted
as a valid framed stop. Session IDs correlate requests; this is not an
authenticated or adversarial replay-resistant protocol.

## Build and upload

Uno: open `Car/Arduino_Uno/msp_line_follow/msp_line_follow.ino` in Arduino IDE,
select Uno and its port (COM12 here), then upload. AVR core 1.8.8 and its bundled
SoftwareSerial library were used; no extra Arduino library installation.

MSP: import this folder as a CCS project for **MSP430F5529**. The shared header
is outside the project folder, so retain the repository layout. On the original
machine, `Car/MSP430/build_robot_supervisor.ps1` builds with TI compiler
21.6.3.LTS. Its installation paths are machine-specific.

TI DSLite must receive **both** `--flash --verify` to program and verify;
`--verify` alone compares against the existing firmware. Use this project's
`targetConfigs/MSP430F5529.ccxml` and `Debug/robot_supervisor.out`, with `--run`.
Upload while motor power is disconnected. Earlier bench programs remain in
`robot_usb_console` and `Car/Arduino_Uno/uart_link_bench` for rollback.

## Verification on 3 November

The figures below refer to the **base firmware before the I2C extension**.
The extension separately passes 299 host bridge assertions and the unchanged
22 supervisor logic assertions; peripheral timing/wiring still need live testing.
The extension uses **5980 bytes flash / 932 bytes RAM** and was programmed with
DSLite flash+verify+run. A later USB test passed 12 checks, observed an Uno STOP
acknowledgement and five consecutive `LINK=READY RUN=0` states. One UART error
was counted during the initial recovery; it stayed at one throughout the test,
with zero RX drops/bad frames. Evidence:
`Laptop/Artifacts/verification/msp-bridge-usb-2026-11-03-222841.json`.

- Uno compiled: **8268 bytes flash / 559 bytes global RAM**; uploaded with verify.
- MSP compiled, flashed, verified and started: **5078 bytes flash / 856 bytes
  RAM**, including the 512-byte stack allocation.
- **133 host assertions** on actual Uno control/protocol code cover corruption,
  calibration, steering, duplicate/invalid sequences, stop and timer wrap/expiry.
- **22 host assertions** on the supervisor's actual command/response/scheduling
  functions cover acknowledgement matching, STOP priority and timeout recovery.
- **22 live hardware checks** passed: linked boot while stopped, uncalibrated
  START refusal, confirmed STOP, local Uno stop, resynchronisation, three Uno
  resets and ongoing status. The reset test produced one UART error per reset
  (three total), with zero receive drops and zero bad-CRC frames; each recovered
  without starting movement.

Evidence: `Laptop/Artifacts/verification/supervised-link-2026-11-03-211939.json`.
Physical track following, motor-noise behaviour and physical stopping while
moving have **not** been tested. Lease/steering behaviour passed host tests;
live hardware remained uncalibrated with motor power disconnected.

From the repository root:

```powershell
python Car/Arduino_Uno/tests/check_supervised_control.py
python Car/MSP430/tests/check_supervisor_logic.py
python Car/MSP430/tests/verify_supervised_hardware.py --msp COM13 --uno COM12
```

Host checks use the installed MinGW g++; live checks require pyserial and
reset the Uno, which clears calibration. Keep the motor battery disconnected.
