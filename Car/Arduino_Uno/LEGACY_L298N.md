# Previous Uno / L298N base

Historical instructions. For the current Zumo, use [the Zumo guide](zumo_line_follow/README.md).

## Previous base — 12 November 2026

**Previously selected source:** [line_follow_car](line_follow_car/README.md), the
Arduino-only white-road follower. The user requested removing the ESP/MSP STOP
dependency after UART1 receive errors were identified. `f` starts locally;
`s` stops locally. MSP/ESP/ultrasonic cannot stop this standalone sketch.
The original [msp_line_follow](msp_line_follow/README.md) is retained separately.
12 November user-confirmed wiring: LEFT OUT -> D4, RIGHT OUT -> D2;
both sensor VCC -> Uno 5V and GND -> Uno GND. This supersedes the earlier
A0/A1 and 3.3V assumptions. The source now uses digitalRead on D4/D2.
The user explicitly requested an assistant upload. The standalone version was
uploaded and flash-verified on COM12; fresh w/b calibration is now required.

Latest track clarification: white road with black borders. Both white -> forward;
left black -> RIGHT; right black -> LEFT; both black -> STOP. The source now uses
white-road steering. Calibrate w on actual white and b on actual black at the SAME
mounted height. The code learns each sensor's digital 0/1 polarity independently;
equal or unstable captures reject calibration. There are no ADC thresholds in
the active digital setup.

The selected standalone sketch ignores D5/D6 UART and needs no MSP session or
heartbeat. D7-D10 L298N wiring, 3000ms corner limit and explicit restart remain.
Do not use lifting the car as a black calibration sample.
Physical sensor contrast, wheel directions and ultrasonic braking need testing.

## Earlier IR-only analogue calibration

[ir_analog_calibration](ir_analog_calibration/README.md) is an earlier
sensor-only sketch for A0/A1. It does not read the user's current D4/D2 wiring.
Use the selected standalone sketch above for this car. Uploading the
analogue test would replace the integrated programme and its MSP STOP receiver.

## Other DIGITAL tests

`line_follow_car` now matches the current white-road D4-left/D2-right setup.
`ir_line_test` retains its older sensor-test assumptions; it is not the current
driving programme.

## Sensor-only test history — 29 October 2026

**ir_line_test** is the dedicated two-sensor black-line test, retained separately
from the later combined line-following sketch. It is not a live inventory of
the program currently flashed on another user's Uno.
Sensor supply is VCC -> 3.3V, GND -> GND. The user requested changing the second
digital OUT from D3 to D4; the current source therefore reads D2/D4. Move that
OUT wire physically to D4 with power off. The updated build passed; the user
requested copy/paste code in chat and will upload this version manually.
See [IR test instructions](ir_line_test/README.md). It was compiled, uploaded
with flash verification, and live RAW reports from both pins were received.
Both were RAW=0 in the initial observation; physical black/white contrast is
still unverified. Calibrate with w over white and b over black before expecting OK.

The motor test source below is retained separately. Uploading the IR test
replaces whichever program is on the board; this IR test holds D7-D10 LOW.
The user reported the motor setup working before moving to the sensor test.

## Continuous motor test — verified 9 October 2026

Source: `uno_forward_test/uno_forward_test.ino`.

- Your Uno is connected by USB on COM12. You clarified that the four-AA
  battery holder powers only the L298N, not the Uno.
- The sketch now implements the requested continuous mode: `f` runs both
  motors until `s` is received. It starts stopped and has no time limit.
- The updated host tests passed C++ syntax checks. Host test execution remains
  unavailable because Windows Application Control blocked the previous test
  executable. No security settings were changed.
- Continuous mode compiled and linked for `arduino:avr:uno` with Arduino AVR
  core 1.8.8: 2,268 bytes of flash and 193 bytes of RAM. It was uploaded on COM12
  with flash verification.
- Live serial verification received the continuous-mode READY message and
  STOP acknowledgements for both `s` and `S`. The board was left stopped.
- No forward command has been sent by the assistant; physical movement and
  wheel direction have not been verified by the assistant.
- ENA/ENB jumper state and the L298N's regulated logic supply still need checking.

Four AA cells are typically 6 V nominal for alkaline or 4.8 V for NiMH.
The Uno is USB-powered in this setup, so its VIN/barrel-jack supply range does
not apply to the motor battery. Keep the common ground with the L298N.
A four-AA supply may not be enough for the L298N module's onboard regulator to
provide its required logic supply; this depends on the exact module.
Do not increase the motor battery voltage without checking the motors' ratings.

## Your wiring

| Arduino Uno | L298N |
| --- | --- |
| D7 | IN1 |
| D8 | IN2 |
| D9 | IN3 |
| D10 | IN4 |
| GND | GND |

Left motor: OUT1 / OUT2. Right motor: OUT3 / OUT4.
Battery positive: motor-supply terminal labelled +12V / VIN on the L298N;
battery negative: L298N GND. The +12V terminal label does not mean that your
motors require 12 V; use a supply appropriate for their actual ratings.

This sketch assumes the **ENA and ENB jumper caps are fitted**, enabling both
motor channels. They are separate from the **5V-EN regulator jumper**.
No Arduino wires are assigned to ENA/ENB in this version. Therefore it uses
full drive, not adjustable speed. Do not copy the earlier Pico enable-pin wiring.

## First test

1. Keep motor power disconnected while uploading. Support the chassis with
   both wheels off the table for the first direction check.
2. Power the Uno through its USB cable. Use a suitable motor supply through
   the L298N, with the common ground above. Check the battery voltage and motor
   ratings, and verify that the L298N logic has a valid regulated 5 V supply.
   A four-AA pack may be too low for a module's onboard 5 V regulator.
   Do not join the module's 5 V terminal to the Uno's 5 V pin without checking
   the module's regulator/jumper arrangement. Do not feed motor power through
   the Uno's pins.
3. Select **Arduino Uno** and the Uno's port in Arduino IDE. It was detected as
   **COM12** on 9 October 2026; the port may change after reconnecting.
4. Upload this sketch. Open Serial Monitor at **115200 baud**. If needed, press
   the Uno RESET button to see the READY message again. The sketch starts stopped.
5. With ENA/ENB enabled and motor power correctly connected, send the single
   letter **f**. Both motors are commanded forward continuously at full drive.
   Send **s** to stop. There is **no automatic timeout**. Keep the motor-battery
   switch/connector accessible. Any Serial Monitor line-ending setting is acceptable.
6. Check both wheels turn in the direction that would propel the car forward.
   If one is backwards, disconnect power and swap that motor's two OUT wires,
   or change its `*_FORWARD_*` constant in the sketch and upload again.

Uppercase F/S also work. The sketch does not automatically drive at startup.
Repeated f commands while moving do nothing. If f and s are already queued
together, s takes priority. After stopping, send a new f to start again.
Opening Serial Monitor may reset the Uno, which starts stopped.

The stop command runs in software. The Uno does not reliably detect loss of
Serial Monitor through `Serial`; closing it does not command a stop. Send s
and confirm STOPPED before closing it. Disconnect the motor battery if you
cannot send a stop command. Do not rely on unplugging USB: it removes the Uno's
power in this setup, but the still-powered driver's inputs may float.
Pins can float during reset or bootloader operation, before this sketch starts.
Keep motor power off during upload/reset, or use hardware input pull-downs and
a suitable hardware enable arrangement for later unattended operation.

## What this proves

This is a bench test of Uno -> L298N -> motors. It does not yet implement line
following, obstacle detection, encoders, spray control or the MSP430 link.
The printed FORWARD message confirms a command, not actual wheel movement.
Both motors receiving the same command does not guarantee straight travel.
In the final system the MSP430 remains the main controller; the Uno executes
its authorised movement commands.

## References

- [ST L298 datasheet](https://www.st.com/resource/en/datasheet/l298.pdf):
  enable inputs, separate logic supply and bridge input truth table.
- [Arduino power guidance](https://support.arduino.cc/hc/en-us/articles/360018922259-What-power-supply-can-I-use-with-my-Arduino-board):
  USB power and recommended VIN/barrel-jack supply range.
