# Local robot dashboard

This is the first working **bench-monitoring** version of the local website.
It runs on the laptop and reads the existing robot MSP430 USB console.
It does not upload firmware or change the Arduino program.

## Open it

1. Double-click **Start Dashboard.cmd** in this folder. Keep its terminal open.
2. Open **http://127.0.0.1:8765** in Edge or Chrome if it does not open automatically.
3. Plug the robot MSP430 into the laptop by USB.
4. Close other serial terminals using **COM13**. Only one program can own the port.
5. Select **MSP Application UART1 / COM13** and connect in the dashboard.
6. Press **S2** on the MSP430. Its green LED toggles; the website should update
   LED2 and the button count within about two seconds.

The page lists compatible TI Application UART ports. It excludes the Uno,
Bluetooth ports and the TI debug interface (COM14). The port number may change
on another USB socket; select the Application UART by its description.

If the server is already running, the launcher opens its existing page.
Press Ctrl+C in the server terminal to stop it and release the serial port.
If another program needs COM13, use **Disconnect** first.

## Available now

- Live robot MSP430 identity, LED2 state, S2 press count and UART error counts.
- Local bench controls: ping, LED2 on/off and internal UART0 loopback.
- A bounded session event log, including board replies and connection errors.
- USB camera preview in the browser, camera selection, and local snapshots.
- A clearly labelled plan for the future pest-review-to-spraying workflow.

The firmware's `STATUS` reply is polled once per second. Without a valid reply
for four seconds, telemetry becomes stale and new bench commands are refused.
A port being open, or a displayed motor command, is not proof of physical motion.
Sensor measurements, pest recognition, job approval/dispatch, movement, spray
delivery and dock telemetry are **not integrated yet**. There are no motor or
pump commands in this web API. The existing motor supply repair/calibration
remains a separate, deferred task.

The event log is held in memory for this server session (latest 100 events),
not a permanent experiment database. No automatic reconnection is performed.

## Camera: connect it to the laptop

Use the **USB webcam already borrowed from the lab** first:

```text
USB webcam at test plant ----USB----> Laptop
                                      |-- Local website / live view
                                      |-- Future image processing + user review
                                      |
                                      USB now; wireless gateway later
                                      |
                               Robot MSP430 (main controller)
                                      |
                              Supporting robot controllers
                               Uno: wheels / line sensors
                               Pico W: wireless link tested separately;
                                       MSP bridge still pending

Second MSP430 + Booster Board: separate dock controller (integration pending)
```

1. Plug the webcam's USB cable into the laptop, not into a microcontroller.
2. Secure it on a small stand facing **one test plant or a pest trap** for the
   first experiment. Keep the view and diffuse lighting steady.
3. In the dashboard, start the camera and allow the browser's camera permission.
   Choose the external webcam in the camera list if the laptop camera appears.
4. Check focus using the actual target at its intended size and distance.
   A whole-plant view may show leaf damage while missing individual tiny insects.
5. Stop the camera when finished. The website requests video only, never audio.

The live stream stays in the browser; no video or snapshot is uploaded to a
server or cloud service. A snapshot is saved only when the user requests it.
This release has no automatic pest detector and makes no pest identification claim.
Preview is the first camera check; a labelled image set and evaluation are
needed before adding detection or connecting it to spray requests.

If the borrowed camera is too blurry, first adjust distance, focus and lighting.
For general leaf/plant viewing, a **USB UVC 1080p autofocus webcam**, such as the
[Logitech C920s](https://www.logitech.com/en-us/shop/p/c920s-pro-hd-webcam), is a
reasonable candidate. Logitech specifies 1080p/30 fps and autofocus. This is
not a guarantee that it can resolve very small pests; verify the closest-focus
distance with the intended target before buying. For tiny insects, evaluate a
USB camera with a suitable close-focus/macro lens rather than choosing only by
megapixels. A Raspberry Pi CSI camera is not a plug-in camera for the Pico W.

Assumption for this first version: the camera is fixed beside the test plot and
the laptop remains nearby. A camera travelling on the robot would need a
different power/data arrangement; that wireless video system is not built here.

## Intended later process

1. Camera/laptop analysis flags a potential pest observation with an image.
2. User reviews the evidence and requests a water-only demonstration treatment.
3. Robot MSP430 checks available sensor conditions and job state before accepting.
4. Arduino handles local line following and reports progress to the MSP430.
5. The assigned spray controller executes a bounded command from the MSP430.
6. Confirmed progress, completion or fault is returned to the website.
7. The dock MSP430 handles its local service sequence when docking is integrated.

These are planned stages, not simulated running statuses. A leaf-damage image
alone does not establish which pest caused it. The exact recognition target,
mounted sensor set, spray hardware ratings and verification method still need
to be defined. The MSP430 remains the main embedded job authority.

## Dependencies and starting on another computer

Python 3.10+ and pySerial 3.5; standard HTML/CSS/JavaScript, no Node build needed.
The launcher uses a local `.venv` first, then this computer's bundled Python.
On this computer it can reuse pySerial already installed in
`../tmp/pico-tools-python`. For a self-contained setup with Python installed:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py --open
```

The server binds **127.0.0.1 only**, not the local network. It validates local
Host/Origin headers and accepts only a small bench-command allowlist. Do not
expose it publicly; this is a local lab tool, not a multi-user service.

## Verification

Software tests (no serial port opened):

```powershell
python -m unittest discover -s tests -v
```

The implementation checks telemetry parsing/freshness, unknown command
rejection, port filtering, origin checks and static-file scope. The initial
verification passed 14 software tests and seven live MSP430 checks through the
website API. Browser checks include actual board connection/LED replies, event
export, stale data, empty port lists, camera errors and responsive layouts.
Camera preview/snapshot checks use synthetic video, not the physical webcam.
Results are recorded in `../output/verification/local-dashboard-2026-10-29.json`.

Browser camera access on localhost requires the user's permission:
[MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).
Serial setup follows the [pySerial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html).
