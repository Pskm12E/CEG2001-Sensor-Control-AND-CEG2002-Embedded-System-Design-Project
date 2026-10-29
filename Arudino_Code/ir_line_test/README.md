# Two-sensor IR black-line test

For the Arduino Uno, using the user's requested updated wiring:

| Sensor | VCC | GND | Digital OUT / DO |
| --- | --- | --- | --- |
| Sensor 1 | Uno 3.3V | Uno GND | Uno D2 |
| Sensor 2 | Uno 3.3V | Uno GND | Uno D4 |

The second input was changed from D3 to D4 at the user's request on
29 October 2026. With USB and motor power disconnected, move only that sensor's
OUT/DO wire from D3 to D4. Software cannot move the physical connection.

Read the labels printed on each module rather than guessing the pin order.
This sketch is for digital-output comparator modules, not analogue-only or
QTR RC-timing sensors. The exact sensor model is unconfirmed. The confirmed
3.3V wiring is retained; whether the module performs well at that voltage must
be checked with the physical black/white test. INPUT mode avoids enabling an
Uno 5V pull-up on the 3.3V sensor outputs.

## Use

1. Stop the car and disconnect the motor battery before uploading or rewiring.
   Leave the Uno on computer USB for power and Serial Monitor.
2. Upload `ir_line_test.ino`, select Arduino Uno / its current port (COM12 was
   detected on 29 October 2026), and open Serial Monitor at **115200 baud**.
3. Point both IR emitter/receiver pairs downwards at the track. Start a few mm
   above it and hold the same height while moving between black and white.
4. With **both sensors over white**, send **w** and wait for the capture results.
5. With **both sensors over black**, send **b**. Use a broad black patch or a
   separate patch under each sensor so both see black for this calibration.
6. Move them between the white background and black line. Each sensor shows
   `OK - BLACK` when its calibrated black reading is stable, and `WHITE` for the
   other reading. The Uno's built-in LED turns on when either sensor sees black.

Example after successful calibration (RAW polarity can be the opposite):

```text
D2 RAW=1 OK - BLACK | D4 RAW=0 WHITE
```

`RAW=0/1` is the digital signal, not a distance or moisture measurement.
The code discovers black polarity independently for each sensor rather than
assuming LOW means black. It requires different stable readings on black and
white before reporting OK; each sensor must remain stable for 50 ms before
classification. A raw signal changing does not by itself prove line detection.

Commands: **w** captures white, **b** captures black, **c** clears calibration,
**?** repeats help. Uppercase W/B/C also work. Calibration uses RAM and must be
repeated after reset, power-off, or reopening Serial Monitor if that resets the Uno.

## If both surfaces give the same reading

- Confirm OUT/DO reaches D2 or D4, the sensor is powered and grounds are common.
- Confirm the emitters face the floor and maintain a short, fixed gap.
- If the module has a sensitivity screw, adjust gradually until it switches
  between your actual white surface and black tape. Repeat **both w and b**
  after adjustment, changing height, or changing the supply voltage.
- Keep sunlight and reflective nearby objects out of the test area.
- `NO CONTRAST` is a failed contrast check, not a software declaration that the
  sensor is broken. Some obstacle-style IR modules cannot reliably distinguish
  a floor line at the chosen height; the exact module may need identifying.
- A disconnected input can float and produce misleading RAW values. This
  sketch cannot electrically verify that a sensor is connected.

## Motor behaviour

This sketch holds the existing L298N direction pins D7/D8/D9/D10 LOW and has
no driving commands. Uploading replaces the program currently on the Uno.
The separate `../uno_forward_test/uno_forward_test.ino` motor source is retained;
upload it again to restore the continuous f/s motor test. No line following or
MSP430 control is implemented by this sensor-only test.

## Verification

- D2/D4 update compiled successfully for Arduino Uno (4,334 bytes flash,
  218 bytes RAM). User requested code in chat to copy/paste and upload manually;
  assistant has not uploaded this version. Physical test remains pending.
- The results below describe the previously verified D2/D3 version.
- Compiled and linked for `arduino:avr:uno` with Arduino AVR core 1.8.8 on
  29 October 2026: 4,334 bytes flash, 218 bytes RAM. The only compiler warnings
  were unused parameters in the installed Arduino core's `new.cpp`.
- Uploaded to the identified Uno on COM12 with flash verification.
- Live serial check received the IR startup banner, four D2/D3 report lines
  and the `c` clear-calibration acknowledgement at 115200 baud.
- Both inputs reported RAW=0 during that observation. This does not establish
  which surface they faced or prove that either sensor distinguishes black.
- No surface calibration was sent by the assistant. Physical white/black
  calibration and confirmation of OK output remain for the user.
- After a temporary USB disconnection the Uno returned on COM12. Selected
  Arduino Uno / COM12 in the new sketch window and verified compilation in the
  IDE, resolving its Missing FQBN error. Serial Monitor is now open at 115200 baud
  and receiving live uncalibrated readings. Physical contrast calibration remains.

Reference: [Pololu reflectance application note](https://www.pololu.com/docs/0J13/all)
explains how surface reflection, height and lighting affect line sensing.
It is background reading, not identification or wiring documentation for the
user's unconfirmed module.
