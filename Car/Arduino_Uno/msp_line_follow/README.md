# MSP430-controlled Uno white-road follower

**Previous L298N base only.** The 17 November Zumo setup uses
[zumo_line_follow](../zumo_line_follow/README.md), black-line sensing and
D6 RX/D13 TX. Do not upload this old motor sketch to a Zumo Shield.
The shared `robot_link.h` in this folder is still included by the MSP supervisor.

**Latest user choice, 12 November:** use the Arduino-only
[line_follow_car](../line_follow_car/README.md) to remove the ESP/MSP STOP
dependency during driving. This folder retains the integrated supervisor version;
uploading it restores MSP approval, STOP reception and the heartbeat lease.

Updated 12 November 2026: the user describes a **white road with black borders**.
The source now selects `WHITE_LANE`: steer away from a detected black border.
This supersedes the earlier black-tape-between-heads layout.

**Latest wiring correction:** LEFT sensor OUT -> D4, RIGHT OUT -> D2, both
powered from Uno 5V. The previous sketch read A0/A1, which did not match these
connections. The corrected sketch uses `digitalRead()` on D4/D2 and learns each
sensor's white/black 0/1 polarity. No sensor wires need moving.

Photos show blue sensitivity trimmers and indicator changes between the pale
surface and black tape. The exact module model remains unidentified; its LED
state alone does not establish which output value means black. Earlier A0/A1,
3.3V and no-adjustment-screw instructions are superseded for this setup.

**Upload:** remains user-controlled. Recalibrate after uploading; calibration
is stored only in RAM and is cleared by reset or power-off.

## Wiring

| Connection | Uno |
| --- | --- |
| LEFT sensor OUT | D4 |
| RIGHT sensor OUT | D2 |
| Both sensor VCC | Uno 5V, user-confirmed wiring |
| Both sensor GND | Uno GND, common with the motor driver |

D4/D2 are INPUT without internal pull-ups. Check the sensors' own GND connections
to the Uno. The user also found a loose motor-driver ground; restore the common
ground with power disconnected before powered motor testing.

Retain all motor/UART wires: D7/D8 -> L298N IN1/IN2 -> OUT1/2 (stated LEFT
wheel); D9/D10 -> IN3/IN4 -> OUT3/4 (RIGHT). ENA/ENB jumpers give full on/off
drive. `REVERSE_TURN_OUTPUTS=false` and both known forward polarities remain.
MSP P3.3 TX -> Uno D5 RX; D6 TX -> existing divider -> MSP P3.4 RX; common GND.
The MSP430 remains the main controller; this change needs no MSP protocol update.

## Calibrate at the mounted height

Use Uno Serial Monitor **115200 baud, New Line**. Motor batteries remain OFF
for these checks. The MSP must be powered/linked to approve w/b requests.

1. Both heads over actual white floor -> send `w`; wait for sampling to finish.
2. Both heads directly over actual black tape -> send `b`; use a separate patch
   under each head if needed. Keep the SAME gap/height and lighting as step 1.
3. Send `IR`, then allow the three report lines to cycle. Both sensors need
   `OK` and overall `CAL=1`. Do not use lifting the chassis as the black sample.
4. Place both heads over the white road, inside its black borders. Each head
   should classify white. Move only the left head over the left black border,
   then only the right over the right border, and check the named readings.

Example only (not an actual measured calibration):

```text
IR LEFT D4 RAW=0 W=0 B=1 OK
IR RIGHT D2 RAW=1 W=1 B=0 OK
```

RAW is the current digital level, 0 or 1. W/B are the saved levels measured over
white/black; -1 means no valid capture. Each head must produce a different value
for white and black. Either polarity works independently per head. OK means
distinct saved levels; SAME means both captures matched; MISSING means a missing
or unstable capture. REQ=0 alone is not proof of successful calibration.

Before calibrating, slide the actual black border under each head at the same
height and verify its RAW value changes from its white reading. The sensor
trimmers adjust the hardware switching point; software calibration only labels
the two output states. Keep the actual colours assigned to w and b.

## Digital calibration and filtering

- Each capture takes 40 readings, at least 5ms apart (about 200ms). At least
  38 must agree; otherwise that capture is invalid.
- Identical saved white/black levels refuse start.
- A changed input must settle for 8ms. During unsettled input the motors stop;
  150ms of instability latches a stop.

The analogue thresholds in the shared controller are inactive in this digital
configuration. The older A0/A1 sensor-only sketch and its `sense` command are
not the calibration programme for this wiring. Repeat w/b after reset, upload,
power-off or a mounting/trimmer change.

## Track layout and MSP authority

Mount both heads facing down near the front, inside the black borders when the
car is centred. Left/right are viewed from behind the car facing forward.

| Left head | Right head | Action |
| --- | --- | --- |
| White | White | Forward |
| Black | White | Right: left wheel forward, right wheel stopped |
| White | Black | Left: left wheel stopped, right wheel forward |
| Black | Black | Latched stop; reposition and explicitly restart |

A turn ends when both return to white, or latches TURN_TIMEOUT after 3000ms
continuously correcting. Border width, sensor spacing, speed and turning radius
must allow a correction before the car crosses the border. White outside the
track is indistinguishable from white inside it once a border is missed. Two
sensors do not determine a route through intersections or a corner with both
heads on black; this implementation stops in the latter case.

`f` is a request for MSP approval, never an automatic local start. Missing/invalid
calibration, unstable readings, an absent MSP session, or the ultrasonic veto
blocks start. `s` stops locally; MSP STOP and the 1000ms lease remain active.
No automatic restart. `IR` and STATUS only read state. Reports fit the 63-byte
usable TX space and skip while the buffer is full; they never wait during steering.
The old MSP text aliases L2/R4 still mean logical left/right; actual physical
inputs are LEFT D4 / RIGHT D2. Dashboard labels reflect the physical pins.

Use [the ultrasonic guide](../../MSP430/robot_supervisor/ULTRASONIC_SETUP.md).
The older standalone sketches replace this programme if uploaded; they are not
the integrated MSP-controlled white-road driving sketch.

## Verification

The earlier A0/A1 build's passing software tests did not prove the physical
wiring matched. The digital revision tests supply signals on D4/D2 independently
of the sketch's pin constants to catch that mismatch. Verification passed:
290 digital sensor-to-motor/calibration checks, 15 USB-report checks, 163 portable
controller/protocol checks, and 68 supervisor checks including digital WHITE_LANE
calibration, approval and obstacle STOP. Arduino Uno compilation passed: 10,230
bytes flash / 618 bytes RAM. No upload or motor command was performed.
Live digital contrast/calibration, physical steering, HC-SR04 near-distance
ranging and braking still need hardware checks.
