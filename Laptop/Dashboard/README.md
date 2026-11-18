# Local robot dashboard

Open **http://127.0.0.1:8765** on the laptop. The robot MSP430 is the main
embedded controller. The app runs locally; the laptop keeps its normal Wi-Fi.

18 November source update: confirmed blue targets request a bounded MSP-owned
stop → **3-second spray** → continuation cycle. It requires Uno OG4, MSP job
firmware, ESP32 DIRECT_WIFI_V2 and Pico DESK_BRIDGE_V3. The default MSP build
keeps the unverified pump driver disabled and holds the robot stopped instead.
See [pump wiring, ratings and cycle behavior](../../Car/MSP430/robot_supervisor/PUMP_SETUP.md).
MSP and Pico updates are installed; Uno OG4 is user-confirmed and FireBeetle V2
is flashed/hash-verified and identified. Reconnect/power the MSP to verify the
complete robot link. The pump remains disabled pending driver qualification.
Reload the page after restarting the updated dashboard. Leave detection off until
the remaining firmware/driver checks are complete.

## Start the system

1. Power the car's FireBeetle ESP32, robot MSP430, Uno and XIAO camera.
   The camera can use **USB-C power from the power bank**.
2. Connect only the **desk Pico W** to laptop USB for dashboard data
   (currently COM11). Keep the existing ESP32/MSP430/Uno UART wiring.
3. Double-click **[Start Robot.cmd](../../Start%20Robot.cmd)** at the project root
   (or the existing **Start Dashboard.cmd** in this folder).
4. The launcher starts/reuses the local server, opens the browser, finds the desk
   Pico, verifies its firmware and starts the wireless camera. The page picks up
   this stream automatically. Keep the terminal open if it started the server;
   **Ctrl+C** closes that server. A reused server keeps running independently.
5. For the blue-square practice target, select **Start detection**.

The launcher waits up to 30 seconds for hardware. Missing/busy USB ports or an
offline camera produce **SETUP INCOMPLETE** rather than a false ready message.
The dashboard stays available: fix power/cabling and rerun the launcher, or use
**Connect** and **Start camera** manually. It never uploads firmware or calibrates sensors. Starting detection explicitly
enables target jobs with the compatible firmware. Closing monitoring does not command
the car to stop; use the robot's stop control if a separate test is driving it.

### Launcher options

From CMD in the project root:

```bat
"Start Robot.cmd"
"Start Robot.cmd" --detect
"Start Robot.cmd" --pico-port COM11
"Start Robot.cmd" --dashboard-only
"Start Robot.cmd" --no-camera --no-browser
```

`--detect` enables only the OpenCV blue-square test after live frames arrive.
`--pico-port` is needed when more than one supported Pico is attached; Uno and
MSP430 ports are excluded. `--dashboard-only` leaves hardware disconnected.
`--no-camera` connects only Pico telemetry; `--no-browser` skips opening a tab.
Use `--wait 60` for slower board startup, or `--http-port 8766` if another app
occupies port 8765. Closing another app's serial console can free a busy Pico.

The launcher uses the dashboard's virtual environment first, then this laptop's
bundled Python, then `py -3` or `python`. On a different laptop, install the
dependencies described below first. It does not download/install anything.

```text
CAR                                    DESK
XIAO ESP32-S3 Sense camera ---- Wi-Fi ----+
  USB-C: power bank only                 |
                                        +-- FireBeetle private AP -- Wi-Fi -- Pico W -- USB -- Laptop
Main MSP430 <--- UART ---> FireBeetle ----+
  |
  UART + existing Uno TX divider
  |
Arduino Uno -- Zumo Shield tracks / six-sensor array

Second MSP430 + Booster: separate future dock controller
```

The XIAO and desk Pico join the **existing** FireBeetle private 2.4 GHz network.
No camera signal wires to the MSP430, ESP32 or Pico are needed. The camera is
192.168.4.10:4243 and the gateway is 192.168.4.1. The FireBeetle AP supports the
two clients: Pico and camera. Do not connect additional devices to that private
AP. Credentials remain in ignored local configuration; never commit them.

## Live video

The camera continuously sends compressed frames over Wi-Fi to the Pico. The
Pico forwards bounded binary frames and separate robot-status replies over the
same USB connection. The server checks JPEG framing and CRC32, keeps the newest
frame and relays one persistent **MJPEG video stream** to the browser. There is
no timed snapshot/capture loop and no camera USB video connection.

Current tested setting: **320 x 240**, approximately **15 fps**. The page shows
the measured receive rate. Lighting, radio interference and distance can affect
performance; this prototype does not promise HD or 30 fps. The USB camera bench
sketches under `Car/XIAO_ESP32S3_Camera/Archive/xiao_camera_usb` are superseded and are not the car
camera firmware. Current sources:

- [Wireless camera](../../Car/XIAO_ESP32S3_Camera/xiao_camera_wifi/xiao_camera_wifi.ino): CAMERA_WIFI_V1.
- [Desk Pico](../Pico_W/laptop_wifi_bridge/main.cpp): DESK_BRIDGE_V3.
- [Robot ESP32](../../Car/ESP32_Gateway/robot_wifi_gateway/robot_wifi_gateway.ino): DIRECT_WIFI_V2.
- [Main MSP430](../../Car/MSP430/robot_supervisor/main.c): SUPERVISOR_V2 / ESP_UART_V1.

**Pause updates** closes the browser's video response; resuming requests the
latest live feed. **Stop camera** stops the Pico camera subscription. **Save
image** explicitly downloads one current video frame; it is not how the preview
runs. A normal laptop / USB webcam remains an optional separate source.

## Blue-square detection — laptop only

The **Blue-square test** runs Python/OpenCV on the laptop. Select **Start
detection**, hold the blue square face-on to the XIAO camera, and look for an
amber checking box followed by **Blue target detected** and a green box after
three distinct nearby camera frames. Centre coordinates are image pixels, not
distance or nozzle aim. **Stop detection** returns to the original live feed.
**Stop camera** also stops detection.

The detector filters HSV blue pixels, rejects small/non-square contours, and
confirms a spatially consistent target. It supports rotation in the image plane;
strong perspective, occlusion, blur or dim light can prevent detection. Other
similar blue shapes can match. Show a clearly visible target at least roughly
10 pixels wide; the filter rejects regions covering more than 65% of the frame.
These are practice settings, not measured insect-recognition performance.

One independent worker processes the newest frame and supplies a continuous
annotated MJPEG response. It does not queue an inference job for every image,
block USB reading, poll snapshots, or open another serial connection. Duplicate
camera sequence numbers do not count as new confirmation frames. Results older
than 750 ms are marked unavailable and lose their detected flag. Freshness is
measured from laptop processing/receipt, not a measured camera-exposure timestamp.

This is **colour/shape detection, not YOLO or insect recognition**. Confirmed fresh detections can request the bounded MSP target job; no direct
pump-on or unrestricted START command is exposed. One continuously visible target
gets one cycle, with one second of fresh absence required to rearm. Missing
camera data prevents post-spray continuation. Stop detection cancels an active
cycle. The future YOLO checkpoint belongs on the laptop
under [YOLO_Model/](../YOLO_Model/README.md); no trained weights are present. Physical pump/driver qualification and nozzle alignment remain pending.

Sources: [OpenCV HSV thresholding](https://docs.opencv.org/4.x/da/d97/tutorial_threshold_inRange.html),
[contour features](https://docs.opencv.org/4.x/dd/d49/tutorial_py_contour_features.html).

## Robot status

The dashboard reads MSP run state, calibration, left/right IR readings, UART
errors and the Pico / Wi-Fi / ESP32 / MSP430 / Uno links. It allows only PING and
STATUS checks. Movement, STOP, calibration, spraying and job dispatch are not
available through the app. The MSP430 retains embedded robot authority.

IR calibration is deferred, so **Needed / Not calibrated** is expected. A
reported stopped state is supervisor status, not wheel-encoder feedback. Pest
detection, ADC sensor integration, spraying and the dock are still future work.

Stale status is blanked until a fresh reply arrives. A temporary unavailable
MSP430 response must not close the independent camera relay. This was fixed and
has a regression test. USB cable loss still requires an explicit reconnect.

## Privacy and stopping

The server binds 127.0.0.1 only. No camera images are uploaded to a cloud service
or automatically recorded. Only the newest JPEG is held in memory; test evidence
contains frame counts and CRCs. Private bench images, firmware backups and
credentials are ignored by Git. The event log holds the latest 100 events.

Use **Stop camera** and **Disconnect** before opening the Pico in another serial
monitor. Ctrl+C in the server terminal shuts down the app. Closing a browser tab
ends its HTTP video connection; use Stop camera to stop the radio subscription.
The camera can stay powered by the power bank. The camera's laptop USB connection
is needed only for a future firmware upload/debug session, not normal operation.

## Dependencies and tests

Python 3.10+, pySerial 3.5, OpenCV headless 4.14, standard HTML/CSS/JavaScript. No Node build needed.
The launcher uses a local `.venv` or the laptop's bundled Python and can reuse
pySerial from `../../tmp/pico-tools-python` and OpenCV from `../../tmp/vision-python`.
On another computer:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py --open
```

Software-only tests:

```powershell
python -m unittest discover -s tests -v
```

With the Pico connected and wireless video already running:

```powershell
python tests/verify_camera_stream.py
```

This checks a continuous 200-frame MJPEG response, CRCs, increasing sequence,
frame rate and the wireless transport identity. It saves no images and sends no
actuator commands. Pico native decoder tests are in `../Laptop/Tools/Communication/tests`.

5 November evidence: 32 software tests, 4,021 native video decoder assertions,
531 existing HTTP/status decoder assertions. Initial wireless relay test passed
200 frames at 15.02 fps, with zero corrupt frames and fresh robot status:
`../Laptop/Artifacts/verification/camera-live-stream-2026-11-05-210148.json`.
The power-bank transition and camera USB absence are recorded separately in
`../Laptop/Artifacts/verification/camera-powerbank-wireless.json`. Final sustained test
with the camera on power-bank power passed 200 frames at 14.91 fps, zero corrupt
frames and fresh robot status:
`../Laptop/Artifacts/verification/camera-live-stream-2026-11-05-211019.json`.

## Hosted preview

The existing [hosted preview](https://pest.4bytedigi.com) was not redeployed.
Hosted mode cannot access this laptop's Pico or wireless camera relay, and all
hardware POST routes/video routes are blocked. Normal webcam preview there stays
in the visitor's browser. See [deployment notes](../Deployment/README.md).

## Blue detector verification — 5 November 2026

42 software tests passed. The supplied blue-square photo was located correctly;
this is a photo check, not a live camera recognition result. An actual continuous
annotated stream test passed 150 frames at 15.14 fps, with five distinct fresh
robot-status updates during the run and no actuator commands. The scene was the
ceiling, so positive live-target confirmation still needs the square in view.
Evidence: `../Laptop/Artifacts/verification/blue-detection-stream-2026-11-05-215150.json`.

Run the live video check only after starting the camera and detection:

```powershell
python tests/verify_detection_stream.py
```
