# Changelog

## One Hit Wounder · 24 November 2026

- The Zumo follows a centred line at 90/400 and saves all six line-sensor ranges in EEPROM. After the first successful calibration, one tap starts a run on the same track. The operator completed a full track run at this speed.
- The car supervisor supports continuous reverse after two water readings below 500 and a return to forward travel after two readings above 500. The laptop can coordinate a stop at the dock magnet and a timed refill with the matching station firmware. The docking sequence passed simulation and still needs a full physical refill trial.
- The laptop launcher can share a view-only link to the camera and robot readings. The XIAO camera delivered live video at about 14 fps over the desk Pico during the camera check.

## V2_Working · 20 November 2026

- The operator confirmed that replacing a resistor in the pump circuit restored
  pump operation. The release uses MSP430 P1.6 and the three-second cutoff.
- Uno OG6 adds a persistent flip-alarm setting. Hold the parked Zumo button
  for two seconds to toggle it. Short taps still calibrate and start following.
- Camera jobs wait for a stop acknowledgement, settle, spray, and resume on
  a matching continuation. An ultrasonic pause during line following resumes
  after two clear readings of at least 7 cm. The stop threshold is 5 cm.
- Clarified the alarm thresholds, button handling and interrupt-driven pump
  cutoff in the source. The rebuilt OG6 flash image and MSP430 loadable
  segments match the previously verified firmware. The dashboard reports P6.0
  probe wetness or estimated water level after empty/full calibration.

## Ultrasonic pause and resume — 2026-11-20

- The updated MSP430 and Uno OG5 pause active line following at 5 cm or closer
  and resume after two consecutive valid readings at 7 cm or farther.
- Missing echoes leave a paused run waiting for clearance. Manual stop, link
  failure, interrupted calibration and an aborted spray require a new request.
- The pause keeps the Uno session active. A refused or timed-out pause falls
  back to STOP. The regression tests exercise this behavior through the Uno
  sketch and MSP430 scheduler.

## Integrated three-second pump profile — 2026-11-20

- User confirmed the P1.6-driven pump running and automatically stopping in two
  observed bench tests. Installed/program-verified the normal ESP-UART/Zumo
  supervisor with the existing bounded pump profile enabled.
- The target cycle waits for Zumo STOP acknowledgement and settling, runs the
  pump for three seconds, turns it off, then accepts matching fresh-camera
  continuation. Ultrasonic settings remain 5 cm STOP / 7 cm clearance.
- The shared direct-link build helper now forwards `-PumpDriverVerified` to
  the MSP build. Default pump-disabled builds remain available.
- Passed 1424 Zumo/MSP/sonar assertions, 119 spray-job assertions, 3140 sonar
  assertions, 4614 UART interrupt assertions and nine dashboard target-job tests.
  Four live read-only updates report the pump profile enabled, stopped motion,
  pump off, Uno ready and zero communication errors.
- The full physical target-to-spray-to-resume trial remains pending.

## Button and automatic LED diagnostics — 2026-11-18

- User confirmed red illumination during the repeated direct LED test, but
  still did not see blinking after S2. Selected SW1/S1 (P2.1) for comparison.
- Added `-Switch1` and `-Automatic` build options alongside the default S2 build.
  Automatic mode requests red LED1 ON/OFF every second and keeps green LED2 ON.
  The three configurations pass 3395 real-main assertions. P1.6 stays disabled.
- Flashed and program-verified automatic mode after the SW1 comparison. Debugger
  checks recorded red-output transitions, but the user saw no blinking in S2,
  SW1 or automatic mode. The cause remains unresolved. The direct red LED test
  was visible, so the halted P1IN read alone cannot establish GPIO failure.
- S2 is a temporary debug control. The normal robot source meets the coursework
  minimums independently with Timer_A0, Timer_A2, five interrupt handlers,
  ADC12/A0 and LPM0. The installed LED diagnostic uses fixed delays.
- A direct three-second pump test is pending wiring readiness. No automated
  pump pulse has been issued and the robot supervisor remains to be restored.

## Isolated S2 LED test — 2026-11-18

- At the user's request, isolated the button and LEDs before further pump work.
  Green LED2 indicates ready; one S2 press gives six red LED1 flashes, then OFF.
  The simple polling program holds P1.6 as an input with pull-down, never HIGH.
- Compiled and passed 1664 assertions against the actual firmware main with
  timed button inputs. Flashed/program-verified and checked green-output HIGH,
  red GPIO configuration and the disabled pump pin. Visible LEDs await the
  user's observation; an output latch alone is not a visual verification.
- The agreed next step is S2 starting both pump and blinking for three seconds,
  after the LED-only check works. No pump was activated during this LED test.

## Press-to-start blinking voltage test — 2026-11-18

- Changed the standalone bench test to start on a debounced S2 press, blink red
  LED1 at about 2 Hz, and keep P1.6 steadily HIGH for three seconds. Another
  press cancels early; a held button does not repeat the test.
- Added runtime progress/start/stop counters and passed 11335 pulse/LED/gate
  assertions. Flashed/program-verified the update and checked sustained timer
  and main-loop progress. Recorded 32 physical test starts and stops in RAM.
- User reports varying 1.9–3.0 V readings and no visible red blink. Unloaded pin
  voltage and visible LED operation remain under investigation; these are not
  qualified powered-pump results. Motor power stays off and the pump disconnected.

## Standalone pump control-voltage test — 2026-11-18

- Prepared separate MSP430F5529 firmware for a disconnected-load voltage check:
  MSP S2 press/release produces a bounded three-second P1.6 pulse and LED1 signal.
  Another press cancels early; held buttons do not repeat or activate at startup.
- Added timer cutoff, reset watchdog, build-only helper, meter instructions and
  5788 passing pulse-state assertions. This does not detect or qualify a pump.
- After a replacement USB cable resolved enumeration, flashed/program-verified
  the standalone test and checked P1.6 starts as a GPIO output LOW. Left it running
  for the user's voltage measurement; no pulse was synthesised by the agent.
  The robot supervisor is temporarily replaced and must be restored before driving.

## Stable target video relay — 2026-11-18

- Fixed the desk Pico discarding a completed JPEG when the next partial frame
  arrived in the same TCP poll. Two bounded buffers now publish complete frames
  with matching metadata, retaining newest-frame behavior without a queue.
- Installed the Pico update. Two live checks improved receive rate from
  4.4–6.6 to 12.9–13.3 fps; longest gaps fell from 969–1282 to 281–328 ms.
  The unchanged detector stayed confirmed after its initial three frames.
- Passed 12083 real-decoder assertions and all 70 dashboard tests. Camera, MSP,
  Uno and FireBeetle firmware were unchanged. No actuator commands were sent.
- Clarified the dashboard's pump-disabled STOP test mode and current target-job
  status. The user’s target trial reached DRIVER_DISABLED, so spraying and
  automatic continuation remain unavailable until the driver is qualified.
- Left monitoring in a visible launcher terminal with Ctrl+C shutdown.

## MSP UART reply recovery — 2026-11-18

- Fixed the nonblocking UART1 transmit queue stalling after it became idle.
  Reading the USCI interrupt vector had cleared TXIFG; later enqueues enabled
  TXIE without restarting transmission. Enqueue and idle restart are now atomic.
- Reproduced the stall with actual enqueue/ISR code and a USCI flag model, then
  passed 4614 regression assertions plus existing supervisor/sonar/Zumo checks.
- Flashed/program-verified the corrected pump-disabled MSP image. Distinct fresh
  dashboard records confirm Pico/Wi-Fi/ESP/MSP UP, Uno READY, RUN=0, PUMP=0,
  READY=0 and zero UART errors. Calibration is needed; no drive/spray was requested.

## Target stop and bounded spray source — 2026-11-18

- Added confirmed blue-target requests through Pico V3 / ESP32 V2 to an MSP-owned
  stop, settle, three-second pump pulse and token-matched continuation sequence.
- Added duplicate-target suppression, action IDs, priority/cancellation, bounded
  timeouts and no replay. Stale/missing camera data cannot grant continuation.
- Changed source ultrasonic STOP/clear thresholds to 5/7 cm, retaining the user's
  no-echo-ignore policy. Increased the Zumo outer-track turn limit to 250; straight
  speed remains 150 and the calibration sweep remains unchanged. Uno source is OG4.
- Added P1.6 pump control and P6.0 raw ADC reporting. Default pump driver is
  disabled while pump current/2N7000 suitability are unknown. Added independent
  timer cutoff and a watchdog to the explicitly enabled build.
- Installed/program-verified the MSP pump-disabled image and verified Pico V3.
  The user subsequently confirmed Uno OG4, then connected FireBeetle on COM20.
  Flashed/hash-verified DIRECT_WIFI_V2 and checked USB identity, AP/Pico/video
  recovery; fixed the two stale USB V1 labels and added an explicit Direct uploader
  option. Reconnect/power MSP for a full robot-link check. Pump remains disabled;
  no drive, calibration or spray commands were sent.

## Zumo driving milestone — 2026-11-17

- Replaced the L298N/two-IR base with Uno + Zumo Shield six-sensor black-line
  following. Preserved the user's original 80-step calibration, PD settings
  and upper-only speed clamps; added interruptible MSP-authorised motion.
- MSP HC-SR04 stopping currently uses **2 cm STOP / 4 cm clearance**. Missing,
  invalid and stale echoes do not stop or block motion; near data expires after
  about 300 ms without a fresh valid reading. Manual/communication STOP and
  the Uno one-second lease remain; no automatic restart.
- Flashed/verified the MSP update; user-installed Uno OG3 was confirmed by serial
  output. The user subsequently reported the driving setup working. The physical
  braking distance and full track are not independently measured.
- Consolidated current guides and separated previous-base instructions. Named
  Uno timing/pin/calibration constants, clarified sonar policy, and removed
  unreachable MSP transmit branches. Cleanup does not reflash the boards.
- Restored the local Uno sketch from the saved complete OG3 source package
  after finding it overwritten with a four-character note; refreshed that package.
- Included the desktop launcher, Zumo dashboard status parsing, regression checks,
  dated evidence and track/enclosure design sources. Pump/ADC/YOLO/dock integration
  remain pending; the separate Pico Wi-Fi issue has not been reverified as fixed.

## Folder organisation — 2026-11-05

- Organised current sources into Car, Laptop and Docking_Station, with device
  guides, labelled archived experiments and an old-to-new path map.
- Preserved the main car MSP430, Uno wheel control, car ESP32 access point,
  wireless XIAO camera and desk Pico architecture.
- Included continuous wireless video and the laptop OpenCV blue-square test.
  Trained YOLO, detection-triggered stopping/spraying and dock firmware remain planned.
- Updated builders, imports, relative includes, launch paths and documentation.
  Regenerated build output; kept private settings and binaries out of Git.
- Kept the Version 1 tag and deployed hosting branch unchanged.

## Version 1 — v1.0.0 — 2026-10-29

First source release of the CEG2001/CEG2002 pest-monitoring and spot-spraying
robot prototype. This is the tested bench-development milestone.

### Included

- Robot MSP430F5529 USB console, LED/button bring-up and internal UART diagnostics.
- ESP32 FireBeetle laptop gateway and Pico W robot wireless-link firmware.
- Private-network configuration generator, shared bounded message parser,
  request/reply IDs, heartbeat/timeouts and reconnect handling.
- Separate Uno motor, IR calibration, line-following and serial-peer sketches.
- Local MSP430 dashboard with camera preview and event log.
- Board-placement and workflow diagrams, wiring notes, historical concept art,
  earlier PDF setup guide, screenshots and verification reports.

### Verified milestone

- 19 MSP430 USB checks passed.
- 19 wireless checks passed, including 30 sustained request/reply exchanges,
  remote LED control and recovery after resetting the ESP32.
- Dashboard software, hardware and browser checks recorded; camera validation
  used a synthetic video source.
- Uno sketches compiled; navigation helper assertions passed. Track behaviour
  and the previously reported motor-power connection still require physical checks.

### Not included yet

MSP430-to-Pico integration, the physical MSP430-to-Uno link, website-to-gateway
commands, pest detection, complete sensor fusion/job scheduling, water spraying,
automated docking/refill and a validated final power system. Charging is manual;
older pictures showing wireless charging are concepts only.

### Build and privacy notes

Generate wireless credentials locally and build both radio boards from the same
configuration. Compiled binaries and board backups are intentionally not released.
Some Windows build helpers target the original laptop's toolchain paths.
The ESP32's default compressed flash transfer failed on that USB connection;
ROM-loader upload with uncompressed smaller blocks passed hash verification.
