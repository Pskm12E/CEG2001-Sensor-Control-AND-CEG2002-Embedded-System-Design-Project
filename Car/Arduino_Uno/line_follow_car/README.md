# Arduino-only white-road follower

**Previous L298N base only.** The 17 November Zumo setup uses
[zumo_line_follow](../zumo_line_follow/README.md) with MSP430 ultrasonic stopping.
Do not upload this standalone L298N sketch to a Zumo Shield.

Selected by the user on 12 November 2026 to run the Uno independently of the
faulty ESP/MSP serial connection. Open `line_follow_car.ino`. The startup message
is `UNO WHITE-ROAD STANDALONE`. Uploaded to COM12 with all 6,816 flash bytes
verified. Its live help response and stopped/uncalibrated reports were checked.

The preceding integrated firmware received MSP STOP after UART1 ESP receive
errors. This sketch has no MSP/ESP serial receiver, approval or heartbeat lease.
One local `f` keeps following until a local stop condition occurs. MSP S2,
Wi-Fi STOP and the MSP ultrasonic sensor do not control this standalone sketch.

## Existing wiring

| Connection | Uno / driver |
| --- | --- |
| Left IR OUT | D4 |
| Right IR OUT | D2 |
| Both IR VCC / GND | Uno 5V / GND |
| L298N IN1 / IN2 / IN3 / IN4 | D7 / D8 / D9 / D10 |
| Left motor / right motor | OUT1-2 / OUT3-4 |

Keep common ground and the existing ENA/ENB jumpers. Left/right are viewed from
behind the car, facing forward. No pin changes are required. D5/D6 UART traffic
is ignored; the sketch does not initialise those pins or any SoftwareSerial.

## White road with black borders

| Left head | Right head | Requested motion |
| --- | --- | --- |
| White | White | Forward |
| Black | White | Right: left wheel forward, right stopped |
| White | Black | Left: left wheel stopped, right forward |
| Black | Black | Latched stop |

This supersedes the earlier black-line-between-heads version. Both heads belong
inside the black borders when centred. White outside a missed border cannot be
distinguished from white inside the road by these two sensors.

## Upload, calibration and driving

Use Arduino Uno / COM12 and Serial Monitor at **115200 baud**.

1. Keep motor battery disconnected while uploading and calibrating.
2. Put both heads over actual white at their mounted height; send `w`.
3. Put both over actual black at the same height; send `b`.
4. Return both to white inside the road. The report should say
   `L4=WHITE R2=WHITE MODE=STOP`.
5. For the powered trial, `f` starts locally and `s` stops locally.

Each head learns its own digital polarity from 40 readings; at least 38 must
agree. Identical white/black values refuse start. Calibration is RAM-only and
must be repeated after upload/reset/power-off. `c` clears it; `?` prints help.
Use single-letter commands. Calibration and help stop motion; `s` has priority.
There is no automatic start or restart.

Input changes settle for 8ms; outputs pause during unsettled readings and latch
SIGNAL_FAULT after 150ms of instability. A continuous turn latches TURN_TIMEOUT
at 3000ms. BOTH_BLACK also latches stopped. After correcting the condition,
recenter on white and send a fresh `f`. These stops remain local to the Uno.

## Verification

- Actual-sketch fake-GPIO/serial checks: **1,244 passed**, including one start
  sustaining 12 simulated seconds without MSP packets while D5/D6 change, white
  road steering, independent polarity, manual stop and local fault stops.
- Actual helper compile-time checks: **29 passed**. The updated steering test
  failed against the previous black-line sketch before the correction.
- Real Uno build passed: **6,816 bytes flash / 371 bytes RAM**.
- Upload/flash verification passed on COM12. Live `?` response confirmed the
  standalone firmware; it was left at `L4=NC R2=NC MODE=STOP` for fresh w/b.

Physical continuous driving and steering still require a powered trial.
The integrated supervisor version remains in [msp_line_follow](../msp_line_follow/README.md).
