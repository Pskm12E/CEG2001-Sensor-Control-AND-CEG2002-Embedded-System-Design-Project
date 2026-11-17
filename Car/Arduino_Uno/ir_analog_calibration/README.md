# Standalone analogue IR calibration

**Historical A0/A1 test:** the user has now confirmed LEFT OUT -> D4, RIGHT OUT
-> D2 and sensor VCC -> Uno 5V. Use [msp_line_follow](../msp_line_follow/README.md)
for that current wiring. The analogue instructions below describe the earlier
setup and do not apply to these replacement sensors.

Sensor-only bench sketch requested on 12 November 2026. **LEFT S -> A0,
RIGHT S -> A1, VCC ->3.3V, common GND.** The latest user confirms no pins changed.
The latest photos show blue adjustment trimmers, superseding the earlier
no-adjustment-screw description. The exact replacement model/output is not
independently identified. This sketch measures voltage using the ADC, including
switched high/low levels, and learns each head's white/black polarity. Do not use
the older D2/D4 test for the retained A0/A1 wiring.

Open `ir_analog_calibration.ino` in Arduino IDE and select Arduino Uno/current
USB port. The assistant builds this source but leaves upload to the user.
Keep the motor battery OFF during upload and calibration.

1. Open Serial Monitor at **115200 baud**, **New Line**.
2. Hold both heads at the actual mounted driving height over white; send `w`.
3. Without changing height, put actual black tape beneath BOTH heads (two
   patches if necessary); send `b`. Do not use lifting the car as a black sample.
4. Both heads need `OK` and the summary must say `CAL=1`. Move each across
   black/white at that same height and check the named head changes colour.

The updated parser accepts whole commands: `w`/`white`, `b`/`black`,
`c`/`clear`, and `status` (case insensitive, Enter to send). The earlier
character-by-character parser interpreted the `c` inside `black` as clear;
that reproducible bug is fixed. The user's actual command text is unknown, so
this does not prove it caused their physical calibration failure.

Every capture now prints MEAN, MIN, MAX, SPREAD and SAVED/REJECTED_NOISE.
`NEED_w`/`NEED_b` means that colour has not been captured; WHITE_NOISY or
BLACK_NOISY means the corresponding capture exceeded the variation limit.
LOW_CONTRAST prints the measured GAP and required minimum. Send the two
CAPTURE lines if calibration still fails. Keep the car on the floor at normal
sensor height; use separate black patches under the heads during b capture,
then place both heads over the white road, inside its black borders, for the
later driving test. This supersedes the earlier line-between-heads layout.

RAW is an average of four ADC reads. W and B are independent 40-sample surface
means; T is the adjustable decision threshold. Either electrical polarity works. A capture
with more than30 ADC counts of variation is invalid, and a white/black gap
below40 counts is insufficient. An8-count hysteresis margin reduces flicker.
These are initial bench settings, not measured tuning for this module.

## Adjustable software sensitivity (V3)

The V3 startup banner identifies this build. Its default sensitivity is **70**,
which places the threshold 30% of the measured way from white towards black.
The previous fixed threshold was the midpoint (equivalent to sensitivity 50).
At 70, a smaller change towards black can trigger detection. This is a bench
setting, not a demonstrated fix for the user's sensor or mounting.

Send one command, then Enter, with Serial Monitor set to New Line:

| Command | Effect |
| --- | --- |
| `sense 50` | Use the midpoint of each head's white/black samples. |
| `sense 70` | Detect black earlier, closer to each head's white reading. |
| `+` | Increase sensitivity by 5, up to 75. |
| `-` | Decrease sensitivity by 5, down to 25. |
| `status` | Show sensitivity and both sensor readings. |

Every adjustment prints `SENSITIVITY=...` immediately. Valid samples also show
`T=... SENS=...` beside BLACK/WHITE. Adjustment preserves W/B, but resets the
classification so the next reading uses the new threshold. The limits leave
room for hysteresis at the minimum accepted contrast. All settings are RAM-only.

This changes the Uno's classification and its built-in LED, not the RAW signal,
sensor-module LEDs or physical detection range. Missing W/B, noisy captures and
insufficient contrast still reject calibration; sensitivity does not bypass them.
This setting is only in the sensor-only test; it has not been transferred to
the MSP-supervised driving sketch or uploaded to any board.

## Height and surface check

The user reports a response with non-reflective paper very close to the head;
the exact module model and rated supply remain unknown. That observation points
to height/material as variables to measure, not proof of valid line contrast.
An S label or absence of an adjustment screw does not identify the output type.
This sketch uses analogue input based on the user's stated output type.

With motors off, compare white floor and actual black tape at exactly the same
measured gap from the optical face. A 3, 5 and 10 mm comparison is an exploratory
test, not the unknown module's specification; do not let the head scrape the
floor. Keep both surfaces flat, lighting steady, and record each head's RAW/W/B
and capture spread. Select a usable mounting height that gives repeatable,
separated readings, then recalibrate there. Test the matte paper the same way
to distinguish a distance effect from a material effect. Do not alter the 3.3 V
supply without identifying the module's voltage rating.

Manufacturer references checked on 12 November 2026 (comparison devices, not
identification of this kit's modules):

- [Pololu reflectance application note](https://www.pololu.com/docs/0J13/all):
  measured white/black contrast falls as the head is raised.
- [Pololu QTR-8 guide](https://www.pololu.com/docs/0J12/all): about 3 mm mounting
  for fast readings, with reduced separation farther away.
- [DFRobot SEN0017](https://wiki.dfrobot.com/sen0017/): a different digital
  line sensor specifies 10-20 mm and its V5 has no adjustment resistor.

The Uno built-in LED indicates either calibrated head classified black; it is
separate from any LED on a sensor. Calibration is in RAM and is lost on reset.
If black/white signals still overlap at the same height, inspect mounting,
material and module requirements; software cannot manufacture missing contrast.

The sketch holds motor direction outputs D7-D10 LOW and has no driving command
or MSP UART receiver. Uploading it replaces the integrated Uno firmware. After
sensor testing, restore [msp_line_follow](../msp_line_follow/README.md) and repeat
its w/b calibration before a main-MSP-controlled driving test. The same ADC
threshold principles are implemented there; calibration values do not transfer
automatically between sketch uploads.

This test does not establish ultrasonic ranging, physical braking or navigation.

V3 verification: 66 checks on the actual sketch pass, covering whole commands,
CRLF, both polarities, threshold changes on identical RAW readings, sensitivity
limits, calibration preservation, noise/contrast rejection and stopped motor
pins. Uno compilation passed: 6,018 bytes flash and 282 bytes RAM.
Upload remains user-controlled; physical calibration is unverified.
