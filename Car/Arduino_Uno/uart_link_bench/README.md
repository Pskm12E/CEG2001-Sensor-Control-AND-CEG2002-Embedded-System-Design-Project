# Uno UART communication bench

Prepared and compiled on 29 October 2026: **3898 bytes flash / 444 bytes RAM**.
Uploaded to the physical Uno on COM12 on 3 November 2026 using Arduino CLI
with verification enabled. Earlier car sketches remain separate. This file
was used for the LED communication test. Later on 3 November it was replaced
on the physical Uno by [msp_line_follow](../msp_line_follow/README.md).

On 3 November, the connected MSP430/Uno bench passed **23 checks**, including
physical PING/PONG, MSP-commanded Uno LED ON/OFF, independent Uno USB state
readback and ten repeated wired round trips. Final MSP status reported
UART_ERRORS=0, RX_DROPS=0, UART0=IDLE; both LEDs were left OFF and Uno motor
outputs stayed disabled. Report:
`Laptop/Artifacts/verification/msp430-uno-divider-retest-2026-11-03-210252.json`.

The first wired request after reconnection was rejected with ERR INVALID LINE;
three subsequent pings and the complete retest passed without firmware changes.
The cause of that initial framing rejection is unconfirmed. Startup framing
and recovery need further work before motor integration. This short bench
test does not establish operation under motor noise or repeated power cycles.

Earlier USB silence recovered after external wires were removed from the MSP
middle RXD/TXD block, its two shorting caps restored and USB reconnected.
Keep those caps fitted for USB communication. The Uno link uses the separate
MSP side-header P3.3/P3.4 pins. The motor battery remained disconnected.

Both command sources accept `PING`, `STATUS`, `LED ON`, `LED OFF`, and `HELP`.
Commands can be upper/lowercase and end in LF, CR or CRLF. Replies go only to
the source that sent the command.

- USB Serial Monitor: 115200 baud (current Uno port COM12).
- Tested MSP430 connection: D5 RX / D6 TX at 9600 baud, 8N1. User's bench uses
  a resistor divider on D6 -> MSP P3.4; see the MSP project README for the
  reported wiring and the limits of this electrical check.
- `PING` replies `PONG UNO`; `LED ON` replies `ACK LED ON`; `LED OFF` replies
  `ACK LED OFF`. LED commands only affect the Uno's built-in LED (D13).
- `STATUS` reports LED state and `MOTORS=DISABLED` (the commanded output state,
  not a measurement of the physical motors).
- D7-D10 are set LOW outputs at startup and are never commanded HIGH.
- IR reading/calibration and navigation are not part of this test. Keep motor
  battery power disconnected during upload and the bench test.

SoftwareSerial cannot transmit and receive simultaneously: send one command,
wait for its reply, then send the next. This is a diagnostic text protocol;
do not treat it as the final movement/spraying control protocol.

Follow the wiring table in `Car/MSP430/robot_usb_console/README.md` at the
project root. Uploading this sketch replaces the running Uno sketch. When
navigation integration begins, merge the tested communication logic into a
new combined program with stop handling, watchdogs and calibration checks.
