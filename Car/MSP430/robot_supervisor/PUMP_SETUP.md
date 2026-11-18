# Target stop, water spray and continuation

**Temporary bench mode, 18 November:** the MSP currently runs the separate
[P1.6 voltage test](../pump_voltage_test/README.md). The integrated supervisor
described below must be restored before robot operation. Motors remain off and
the pump disconnected for the voltage test.

Source update: **18 November 2026**. The software sequence is implemented and
tested with simulated hardware. **MSP pump-disabled firmware and Pico V3 are
installed and verified. Uno OG4 is user-confirmed, and FireBeetle V2 is now
flashed/hash-verified and USB-identified. The MSP UART idle-restart fix is
installed, and all live links are verified while stopped with the pump disabled.**
The pump is **disabled in the default build** while the driver rating is unresolved.

## Requested sequence

1. The laptop confirms the blue target across three distinct fresh camera frames.
2. Pico V3 and ESP32 V2 forward one bounded `TARGET` request to the MSP430.
3. MSP accepts only while the calibrated Zumo is following, with no obstacle
   inhibit or manual STOP. It sends STOP and waits for the Uno acknowledgement.
4. After a stopped session is established, wait about 300 ms, then run the pump
   for **3 seconds**. Both tracks remain stopped throughout.
5. Turn the pump off. A fresh camera-based continuation, carrying the same job
   ID, lets the MSP resume line following once. No continuation within about
   3 seconds leaves the robot stopped and cancels the cycle.

Manual STOP, an ultrasonic near obstacle, UART/link faults, refusal or lost
calibration cancel the cycle with the pump off. They do not resume automatically.
The current sonar trigger is **5 cm**, with two readings at least **7 cm**
clearing a recent near inhibit. Missing echoes retain the requested no-STOP policy.

One continuously visible target triggers one cycle. The laptop requires about
one second of fresh frames without a target before rearming. This is blue-shape
recognition, not insect identification, range finding or nozzle alignment.
Closing/losing monitoring cannot grant continuation; physical STOP still depends
on the wired MSP/Uno link, local stop controls and their power supplies.

## Supplied wiring

| Connection | Destination |
| --- | --- |
| Separate 4×AA pack + | Pump + |
| Pump − | 2N7000 drain |
| 2N7000 source | Common GND |
| MSP430 P1.6 | MOSFET gate; add a series gate resistor, e.g. 100 Ω |
| MOSFET gate | Add 100 kΩ to source/common GND to hold it off during reset |
| Pack − | Common GND |
| 1N4001 striped/cathode end | Pump + |
| 1N4001 unstriped/anode end | Pump − |
| Water sensor V/+ | MSP430 3.3 V |
| Water sensor G/− | Common GND |
| Water sensor S | MSP430 P6.0 / ADC A0 |

Put the diode directly across the pump terminals. MSP, Uno, ESP32, sonar, water
sensor, driver source and pump-battery negative share GND. The pump battery does
not connect to an MSP GPIO. Confirm the actual manufacturer's transistor package
pinout; TO-92 lead order must not be inferred from a generic drawing.

## Driver qualification still needed

To check the GPIO control voltage without powering the pump, use the separate
[button-driven P1.6 voltage test](../pump_voltage_test/README.md). It produces
a bounded 3-second pulse with the pump disconnected; it does not detect or
qualify the pump. Building it leaves the installed supervisor unchanged.

The user reports the pump is approximately **5 V**; its current/model and the
exact 2N7000 manufacturer remain unknown. A separate battery supplies motor power
but does not establish that the transistor can switch it. The
[Vishay 2N7000 datasheet](https://www.vishay.com/docs/70226/70226.pdf) lists a
200 mA continuous-current absolute maximum at 25 °C and specifies on-resistance
at gate voltages above 3.3 V. Threshold voltage is not a full-on drive rating.
Those limits cannot qualify an unidentified pump at a 3.3 V gate signal.

Verify pump running/startup current, supply voltage range and a driver whose
on-resistance is specified for the actual gate drive. A four-AA supply may exceed
5 V depending on cell chemistry/state. The existing 2N7000 wiring has therefore
**not** been approved for a powered pump test. Hardware qualification is required
before using P1.6 to switch a powered pump. The disconnected-load GPIO voltage
test above is separate. The gate pull-down is required even with firmware protection.

P6.0 is sampled as a raw 12-bit ADC value once per second (`WATER=0..4095`).
Wet/dry calibration is pending; no tank level or empty-tank protection is claimed.

## Sources and builds

| Board | Required version / source |
| --- | --- |
| Uno | OG4, [Zumo sketch](../../Arduino_Uno/zumo_line_follow/README.md) |
| MSP430 | ESP-UART/Zumo build, [spray_job.h](spray_job.h) and [main.c](main.c) |
| ESP32 | DIRECT_WIFI_V2, `robot_wifi_gateway` |
| Desk Pico | DESK_BRIDGE_V3, `laptop_wifi_bridge` |
| Laptop | Updated local dashboard; restart its server after installation |

Old Pico/ESP images still provide monitoring but cannot perform the new cycle.
There is no direct remote motor START, manual pump-on or calibration API. The
hosted preview remains read-only. Queued target/continuation requests expire;
uncertain actions are never replayed after timeout/reconnection. The MSP rejects
duplicate job IDs and continuation outside the matching completed spray.

From the repo root, compile the pump-disabled deployment candidate:

```powershell
./Car/Arduino_Uno/build_zumo.ps1
./Laptop/Tools/Communication/build_direct.ps1 -Zumo
./Laptop/Tools/Communication/build_desk_pico.ps1
```

After hardware qualification, the explicitly enabled MSP build is separate:

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo -PumpDriverVerified -SpraySeconds 3
```

That command compiles only to ignored `Debug_wifi_zumo_pump/`. It does not
qualify the driver or upload firmware. The default `Debug_wifi_zumo/` image uses
`READY=0`: target detection stops the Zumo, reports `DRIVER_DISABLED`, and holds
it stopped without spraying or automatically continuing. A timer interrupt cuts
off the pump at the duration limit; the enabled build also uses a watchdog.

Software checks include the actual sketch/supervisor/sonar path, the bounded job,
Pico command/HTTP dispatch and the detection-to-job callback. They do not measure
physical braking, flow rate, motor torque, transistor temperature or track behavior.
