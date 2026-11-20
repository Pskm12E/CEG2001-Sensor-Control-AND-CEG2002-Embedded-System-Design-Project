# Target stop, water spray and continuation

The `V2_Working` profile runs the ESP-UART/Zumo supervisor with the pump enabled.
The MSP430 drives the 2N7000 gate on **P1.6** and limits each pulse to **three
seconds**. The operator confirmed the pump worked after replacing a resistor.
Two earlier bench runs also confirmed that the pump stopped at the end of a
pulse. [Bench and installation record](../../../Laptop/Artifacts/verification/pump-integration-2026-11-20.json)

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
Outside a spray job, the MSP430 and Uno OG6 pause active line following
at **5 cm or closer** and resume after two consecutive valid readings at least
**7 cm**. A spray job canceled by an obstacle requires a new local start.

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
| MSP430 P1.6, or P1.4 with `-PumpGateP14` | MOSFET gate; add a series gate resistor, e.g. 100 Ω |
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

## Confirmed bench operation

With Zumo track power off and the separate pump supply connected, the MSP430
issued timer-bounded three-second P1.6 pulses. The user confirmed that the pump
ran and stopped in two observed tests. Each readback recorded one start, one
stop, zero remaining ticks and P1.6 LOW after cutoff. This short-run result is
the basis for enabling the installed three-second profile.

The normal supervisor uses Timer_A0 for an independent duration cutoff and a
reset watchdog serviced by the main loop. Startup leaves the pump off. The
standalone [P1.6 voltage-test program](../pump_voltage_test/README.md) remains
available for future measurements. It replaces the supervisor when installed.

P6.0 is sampled as a raw 12-bit ADC value once per second (`WATER=0..4095`).
The dashboard displays probe wetness using the measured dry and wet references.
Saving empty and full readings with the probe mounted in the tank enables a
tank-level estimate. With the OG7-compatible supervisor, two raw readings at
15 or lower cancel an active spray job. During ordinary line following they
request one second of straight reverse followed by a stop. Two readings at 30
or higher clear the empty state so the operator can start another run.

## Sources and builds

| Board | Required version / source |
| --- | --- |
| Uno | OG6 for line following, obstacle pause/resume and the flip alarm. [Zumo sketch](../../Arduino_Uno/zumo_line_follow/README.md) |
| MSP430 | ESP-UART/Zumo build, [spray_job.h](spray_job.h) and [main.c](main.c) |
| ESP32 | DIRECT_WIFI_V2, `robot_wifi_gateway` |
| Desk Pico | DESK_BRIDGE_V3, `laptop_wifi_bridge` |
| Laptop | Updated local dashboard; restart its server after installation |

Old Pico/ESP images still provide monitoring but cannot perform the new cycle.
There is no direct remote motor START, manual pump-on or calibration API. The
hosted preview remains read-only. Queued target/continuation requests expire;
uncertain actions are never replayed after timeout/reconnection. The MSP rejects
duplicate job IDs and continuation outside the matching completed spray.

From the repo root, compile the current pump-enabled deployment profile.

```powershell
./Car/Arduino_Uno/build_zumo.ps1
./Laptop/Tools/Communication/build_direct.ps1 -Zumo -PumpDriverVerified
./Laptop/Tools/Communication/build_desk_pico.ps1
```

To build only the MSP430 image, use the following command.

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo -PumpDriverVerified -SpraySeconds 3
```

That command compiles only to ignored `Debug_wifi_zumo_pump/`. It does not
upload firmware. Omitting `-PumpDriverVerified` builds the separate
`Debug_wifi_zumo/` profile with `READY=0`. Target detection then stops the Zumo
and reports `DRIVER_DISABLED`. The installed image uses `READY=1` and the
three-second pump cutoff.

If the gate wire is on P1.4, add `-PumpGateP14` to the supervisor or direct-link
build command. The MSP430 output is in `Debug_wifi_zumo_pump_p14/`. The selected
pin starts low and uses the same stopped-robot checks and timer cutoff.

Software checks include the actual sketch/supervisor/sonar path, the bounded job,
Pico command/HTTP dispatch and the detection-to-job callback. They do not measure
physical braking, flow rate, motor torque, transistor temperature or track behavior.
