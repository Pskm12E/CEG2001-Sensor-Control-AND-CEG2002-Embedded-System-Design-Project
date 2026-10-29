# Changelog

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
