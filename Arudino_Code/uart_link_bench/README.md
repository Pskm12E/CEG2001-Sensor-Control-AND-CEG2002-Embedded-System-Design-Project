# Uno UART communication bench

Prepared and compiled on 29 October 2026: **3898 bytes flash / 444 bytes RAM**.
Not uploaded or tested on the physical Uno yet. Earlier car sketches remain
separate. This file is for an LED communication test, not line following.

Both command sources accept `PING`, `STATUS`, `LED ON`, `LED OFF`, and `HELP`.
Commands can be upper/lowercase and end in LF, CR or CRLF. Replies go only to
the source that sent the command.

- USB Serial Monitor: 115200 baud (current Uno port COM12).
- Future MSP430 connection: D5 RX / D6 TX at 9600 baud, 8N1, through a
  suitable 3.3V/5V logic-level converter and shared GND.
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

Follow the wiring table in `MSP430_Code/robot_usb_console/README.md` at the
project root. Uploading this sketch replaces the running Uno sketch. When
navigation integration begins, merge the tested communication logic into a
new combined program with stop handling, watchdogs and calibration checks.
