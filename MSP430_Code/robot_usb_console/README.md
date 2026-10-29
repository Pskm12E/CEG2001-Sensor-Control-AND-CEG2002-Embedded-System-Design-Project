# Robot MSP430 USB console

This is the current robot MSP430 bench project. It runs on the MSP-EXP430F5529LP
and can be used today with its USB cable alone. The robot MCU is the controller
that initiates requests; the future Arduino peer only answers them.

## Try it now

Open a serial terminal on **MSP Application UART1 / COM13**, **9600 baud**,
8 data bits, no parity, one stop bit, no flow control. Send each command with
Enter/newline. Use COM13 for this console; COM14 is the debugger interface.
Only one application can open COM13 at a time.

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
`output/verification/msp430-usb-console-2026-10-29.json` at the project root.
`MSP430_Code/tests/verify_usb_console.py --port COM13` repeats these hardware
checks with Python and pyserial. It briefly switches LED2 on/off and leaves it
off. Close any other COM13 terminal before running it.

## Later: Arduino connection

Obtain a **bidirectional 3.3V/5V logic-level converter** suitable for UART,
such as the common BSS138 module with LV/HV and matching numbered channels.
Inspect the actual module labels before connecting it.

Disconnect both USB supplies while assembling wires. Keep motor battery power
disconnected for this communication-only bench test.

| From | To |
| --- | --- |
| MSP430 `3V3` | Converter `LV` reference |
| Arduino `5V` | Converter `HV` reference |
| MSP430 `GND` | Converter common `GND` |
| Arduino `GND` | Same converter/common `GND` |
| MSP430 `P3.3` (UART0 TX) | Converter `LV1` |
| Converter `HV1` | Arduino `D5` (software RX) |
| Arduino `D6` (software TX) | Converter `HV2` |
| Converter `LV2` | MSP430 `P3.4` (UART0 RX) |

Power each board from USB for the bench test. The converter references come
from their respective boards; do not connect Arduino 5V directly to MSP GPIO
or its 3V3 rail. D2/D4 remain the IR pins, D7-D10 the motor-control pins, and
Uno D0/D1 remain available for USB logging/programming. D5/D6 gain their serial
roles only when the corresponding bench sketch is uploaded.

Upload `Arudino_Code/uart_link_bench/uart_link_bench.ino` to the Uno for this
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
