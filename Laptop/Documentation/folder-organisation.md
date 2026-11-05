# Folder organisation and migration

Updated 5 November 2026. The three primary groups are **Car**, **Laptop** and
**Docking_Station**. Each device has a README identifying its current program.
Older independent experiments are labelled as archive/bench software. The dock
directories document planned work; they do not contain invented firmware.

## What moving folders affects

Already-flashed firmware, board wiring, pin assignments and the saved private
Wi-Fi network do not change. Folder moves do affect source-relative includes,
Python tool/dependency lookup, PowerShell builders, CMake inputs, launch commands,
IDE workspace entries and documentation links. These references were updated.

- Use `Laptop/Dashboard/Start Dashboard.cmd` for the local app.
- Reopen/import Arduino, Pico and CCS projects from their new source folders.
  Arduino sketch directory and `.ino` filenames were kept matched.
- Rebuild when changing firmware. Old CMake/build caches contain absolute paths;
  they were preserved locally under ignored `tmp/reorganization-build-cache`
  rather than reused or included in Git. New builds regenerate current outputs.
- Private radio settings moved to
  `Laptop/Tools/Communication/local-network.json`. Hash checks confirmed their
  contents were preserved. Settings, generated headers and firmware stay ignored.
- Local temporary tools and session notes remain in ignored `tmp/` and `work/`.
  They are not extra published source groups.

## Old-to-new locations

| Earlier path | Current path |
| --- | --- |
| `Arudino_Code/` | [Car/Arduino_Uno](../../Car/Arduino_Uno/README.md) |
| `MSP430_Code/` | [Car/MSP430](../../Car/MSP430/README.md) |
| `ESP32_Code/robot_wifi_gateway/` | [Car/ESP32_Gateway](../../Car/ESP32_Gateway/README.md) |
| `ESP32_Code/xiao_camera_wifi/` | [Car/XIAO_ESP32S3_Camera](../../Car/XIAO_ESP32S3_Camera/README.md) |
| `Pico_Codes/laptop_wifi_bridge/` | [Laptop/Pico_W](../Pico_W/README.md) |
| `Local_Website/` | [Laptop/Dashboard](../Dashboard/README.md) |
| `Local_Website/models/` | [Laptop/YOLO_Model](../YOLO_Model/README.md) |
| `Wireless_Link/` | [Laptop/Tools/Communication](../Tools/Communication/README.md) |
| `docs/` | [Laptop/Documentation](diagrams/README.md) |
| `output/` | [Laptop/Artifacts](../Artifacts/README.md) |
| `deploy/` | [Laptop/Deployment](../Deployment/README.md) |

The model directory is a documented future location. **No trained YOLO weights
exist yet.** The current blue-square detector is Python/OpenCV in Dashboard.
Historical PDFs, generated diagram text and dated measurement JSON preserve
their original context; old paths inside an unchanged test report are provenance,
not current launch instructions. Tag `v1.0.0` preserves the original repository.

## Hosting boundary

This change is prepared on **codex/organize-device-folders**, separate from the
automatically deployed **codex/pest-hosting** branch. No deployment settings were
changed. Promoting this layout later requires changing the hosted build root
from `Local_Website` to `Laptop/Dashboard` and verifying its read-only endpoints.

## Validation

The moved dashboard passed 42 software tests, including detection, wireless-frame
handling, HTTP restrictions and hosted-preview isolation. Six host C++ suites
passed 5,070 assertions across Uno/MSP control, UART framing and radio/video
parsing. Node syntax and Python import/compilation checks passed.

Current firmware was rebuilt from the new source paths without upload. Detailed
build and file-preservation results are recorded with the reorganisation report
in `Laptop/Artifacts/verification`. Boards were packed away, so these checks do
not constitute another physical sensor, motor, camera or radio test.
