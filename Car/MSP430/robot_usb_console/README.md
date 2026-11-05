# Robot MSP430 USB console

This is the earlier robot MSP430 bench project. The physical board now runs
[robot_supervisor](../robot_supervisor/README.md), uploaded on 3 November 2026.
This preserved bench program runs on the MSP-EXP430F5529LP
and can be used today with its USB cable alone. The robot MCU is the controller
that initiates requests; the future Arduino peer only answers them.

## Try it now

Open a serial terminal on **MSP Application UART1 / COM13**, **9600 baud**,
8 data bits, no parity, one stop bit, no flow control. Send each command with
Enter/newline. Use COM13 for this console; COM14 is the debugger interface.
Only one application can open COM13 at a time.

Keep one shorting cap across the two pins for **RXD** and one across the two
pins for **TXD** on the middle isolation block. Each cap bridges the USB/debugger
side to the target side of its own signal; do not connect RXD to TXD. These
connections serve USB UART1. The Uno link uses the separate side-header
**P3.3 TX / P3.4 RX (UART0)**. Disconnect power before changing wires or caps.

| Command | Expected result |
| --- | --- |
| `help` | Lists commands |
| `ping` | `PONG MSP430` |
| `status` | Board identity, LED2 state, S2 press count, UART state and error counts |
| `on` | Green LED2 on; `OK LED2 ON` |
| `off` | Green LED2 off; `OK LED2 OFF` |
| `loopback` | `LOOPBACK PASS: 12 bytes, internal UART0 only` |

Red LED1 continues its double blink. Pressing S2 toggles green LED2 and prints
a `BUTTON S2` message; `status` reports the accepted press count. An S2 press
does not send an Arduino command. S1 is unused.

`loopback` uses the MCU's internal UART0 test connection. It checks all 12 test
bytes, including 0x00/0xFF, and restores normal UART0 mode afterwards. This
does **not** test header wiring, the converter, or the Arduino. Run this
standalone test before attaching another board.

No start, drive or spray commands exist in this bench firmware. The program
does not implement pest detection, job scheduling or the final robot state
machine. Local S2 and console LED commands are diagnostic controls.

## Confirmed on 29 October 2026

- Compiled with CCS 21.0.1 / TI MSP430 compiler 21.6.3.LTS: 0 errors/warnings.
- Uploaded, flash-verified and started using TI DSLite: 3186 bytes flash,
  895 bytes RAM, including a 512-byte stack reservation.
- 19 live USB checks passed. They cover command/reply, status, local LED control,
  unsupported/overlong/invalid commands, lowercase/CRLF, fragmented input,
  five internal UART0 loopbacks, and a missing-peer timeout/recovery.
- Final serial status reported UART_ERRORS=0, RX_DROPS=0, UART0=IDLE, LED2=OFF.
- Physical inter-board UART, motion, pump control and sensor calibration have
  not been tested by this project. The new firmware's S2 event text/count is
  ready for a manual button check; automated testing did not physically press it.

The verification report is in
`Laptop/Artifacts/verification/msp430-usb-console-2026-10-29.json` at the project root.
`Car/MSP430/tests/verify_usb_console.py --port COM13` repeats these hardware
checks with Python and pyserial. It briefly switches LED2 on/off and leaves it
off. Close any other COM13 terminal before running it.

## USB recovery checked on 3 November 2026

After external wires were removed from the middle RXD/TXD block, the two
shorting caps were restored and USB reconnected, 26 USB checks passed. They
covered PING/status, local LED2 on/off/readback and 20 repeated pings. Final
status: LED2=OFF, UART0=IDLE, UART_ERRORS=0, RX_DROPS=0.

Evidence: `Laptop/Artifacts/verification/msp430-usb-restored-2026-11-03-192626.json`.
No firmware replacement was needed for this recovery. The physical Uno link
was disconnected during this USB-only test, then reconnected and checked below.

## Arduino link checked on 3 November 2026

The real wired link passed **23 checks**: USB identities, MSP LED control,
physical PING/PONG, MSP-commanded Uno LED ON/OFF with independent Uno USB
readback, ten repeated wired round trips and final status. Both LEDs finished
OFF; MSP UART_ERRORS=0, RX_DROPS=0, UART0=IDLE. Uno reported MOTORS=DISABLED.
Report: `Laptop/Artifacts/verification/msp430-uno-divider-retest-2026-11-03-210252.json`.

The first request after reconnecting received ERR INVALID LINE and timed out.
Three follow-up pings and the full retest passed without firmware changes.
Its exact cause remains unconfirmed; startup framing/recovery needs further
testing before movement integration. USB recovery and a short successful
bench test do not establish reliability during motor operation or power cycling.

### Current bench wiring

The user reported this resistor-divider wiring; communication was verified,
but resistor values, divider voltage and logic-level margins were not measured.

Disconnect both USB supplies while assembling wires. Keep motor battery power
disconnected for this communication-only bench test.

| From | To |
| --- | --- |
| MSP430 `P3.3` (UART0 TX) | Arduino `D5` (software RX) |
| Arduino `D6` (software TX), green wire | 1 kOhm resistor -> divider junction |
| Divider junction, yellow wire | MSP430 `P3.4` (UART0 RX) |
| Divider junction | Two 2.2 kOhm resistors in parallel -> common GND |
| Arduino GND, MSP430 GND, divider bottom | Shared ground |

The nominal divider output is 2.62 V for a 5 V input. This is calculated, not a
measurement. A dedicated ground jumper has not been independently confirmed;
the tested setup shared a ground through the laptop USB supplies. Provide a
common ground when wiring the boards, including when using separate supplies.

Power each board from USB for the bench test. Keep the RXD/TXD isolation caps
in place. Do not connect Uno D6 directly to MSP GPIO, or connect Arduino 5V
to the MSP 3V3 rail. D2/D4 remain the IR pins, D7-D10 the motor-control pins, and
Uno D0/D1 remain available for USB logging/programming. D5/D6 gain their serial
roles only when the corresponding bench sketch is uploaded.

Upload `Car/Arduino_Uno/uart_link_bench/uart_link_bench.ino` to the Uno for this
test; the existing line follower does not understand this new link yet.
The inter-board link uses **9600 baud, 8N1**, and one request followed by one
reply because SoftwareSerial cannot receive while transmitting.

Then enter these commands in the MSP430's COM13 console:

| MSP430 console command | Expected reply after a working physical connection |
| --- | --- |
| `link ping` | `LINK PASS: PONG UNO` |
| `link on` | `LINK PASS: ACK LED ON`; Uno built-in LED on |
| `link off` | `LINK PASS: ACK LED OFF`; Uno built-in LED off |

Without a connected, correctly programmed Uno, `link ping` should report
`LINK TIMEOUT`, not success. A timeout never enables movement.

This is a human-operated LED diagnostic protocol. It has no message IDs,
checksum, leases or motion watchdog and must be extended before controlling
movement or dosing. Identical late replies are not distinguishable from fresh
replies in this simple bench protocol.

## Implementation

- UART1: USB bridge on P4.4/P4.5; UART0: future peer on P3.3/P3.4.
- REFO/FLL gives nominal 1,048,576 Hz SMCLK; BR=109 and BRS=2 for 9600 baud.
- Timer_A0: ~100 ms heartbeat and timeout tick; Timer_A1: ~20 ms S2 debounce.
- Five ISRs: two UART RX, two timers, and the button port interrupt.
- Fixed-size receive rings and command buffers; invalid lines are rejected.
- CPU uses LPM0 between events, keeping SMCLK available for UART. TX is polled
  with a bounded wait for short bench messages; this is not a fully optimized
  low-power design. No power consumption measurements have been taken.
- `build_usb_console.ps1` builds this project without uploading it.

References: [TI board guide](https://www.ti.com/lit/ug/slau533d/slau533d.pdf),
[TI MCU datasheet](https://www.ti.com/lit/gpn/MSP430F5529),
[SparkFun UART level-converter wiring](https://learn.sparkfun.com/tutorials/bi-directional-logic-level-converter-hookup-guide/all?print=1).
