# System overview image — 4 November 2026

Method: built-in image_gen imagegen; no CLI fallback.

Output: robot-system-connections-2026-11-04.png

Checked: USB PC-to-FireBeetle, Wi-Fi FireBeetle-to-Pico, robot MSP authority, all listed I2C/UART/Uno pins, retained divider and pull-ups, unresolved I2C status, planned XIAO/dock/spray roles. Board drawings are illustrative, not physical pin-location guides. Sensor/motor arrows represent separate functional connections; do not join their signal wires.

## Final generation prompt

Create a polished, accurate educational infographic for a beginner's real embedded robot project. A single landscape poster, high resolution, roughly 3:2 aspect ratio, white background, navy text, generous spacing, clean flat illustrations of laptop and distinct microcontroller boards. Prioritise readable text and clear connections over decoration. This is a functional system diagram, NOT a physical pin-header placement guide.

TITLE: "ROBOT SYSTEM — BOARDS & CONNECTIONS"
Prominent short subtitle: "MSP430 is the main controller"
Prominent top callout: "Laptop ↔ ESP32 = USB     |     ESP32 ↔ Pico W = Wi-Fi"

MAIN DIAGRAM across the upper and middle area, with five clearly separated cards in a left-to-right communication chain. Group the first two under "BESIDE LAPTOP" with pale blue background. Group the last three under "ON THE CAR" with pale green background.
1. "LAPTOP" with a laptop illustration. Two lines: "Serial console now" and "Website integration pending".
2. "FIREBEETLE ESP32" with black board illustration. Role: "USB ↔ Wi-Fi gateway".
3. "PICO W" with green board illustration. Role: "Wireless message relay".
4. "ROBOT MSP430" with red LaunchPad illustration, largest/most emphasised card. Bold red label "MAIN CONTROLLER". Role: "Authorises actions • supervises Uno". Second smaller line: "Job / spray logic pending".
5. "ARDUINO UNO" with blue board illustration. Role: "Line sensing + wheel control".

Connect Laptop ↔ FireBeetle with a thick blue bidirectional arrow labelled "USB • 115200 baud".
Connect FireBeetle ↔ Pico with a purple bidirectional arrow and a Wi-Fi icon labelled "Private Wi-Fi".
Connect Pico ↔ MSP with an AMBER DASHED bidirectional arrow labelled "I²C • CHECK WIRING". This link is implemented in firmware but FAILED the physical test, so never depict it as verified.
Connect MSP ↔ Uno with a teal bidirectional arrow labelled "UART • 9600 baud".
No Wi-Fi arrow between laptop and ESP32. No direct Pico-to-Uno connection. No motor control from Pico. Arrowheads at both ends on communication links mean requests and replies.

Below the Pico/MSP link, a very legible wiring card with exact text:
"PICO ↔ MSP430"
"GP4 (pin 6) ↔ P3.0 • SDA"
"GP5 (pin 7) ↔ P3.1 • SCL"
"GND (pin 8) ↔ GND"
"SDA → 4.7 kΩ → Pico 3V3"
"SCL → 4.7 kΩ → Pico 3V3"
"Pico 3V3 OUT = pin 36"
Small note: "Two pull-ups; do not join board 3V3 outputs."

Below the MSP/Uno link, a separate very legible card with exact text:
"MSP430 ↔ UNO"
"P3.3 TX → D5 RX"
"P3.4 RX ← divider ← D6 TX"
"GND ↔ GND"
"Keep the existing Uno TX divider."
Small two-line note:
"D6 → 1 kΩ → RX junction"
"RX junction → (2.2 kΩ ∥ 2.2 kΩ) → GND"

Beneath the Uno, a compact readable sensor/motor branch:
"LEFT IR → D2" and "RIGHT IR → D4" feeding Uno.
"IR power: 3.3V + GND"
Uno arrow to a red motor driver block labelled "L298N", then arrow to a small two-wheel robot/chassis icon labelled "WHEEL MOTORS".
Exact compact pin mapping in this branch:
"D7→IN1   D8→IN2"
"D9→IN3   D10→IN4"
"OUT1/2 → left motor"
"OUT3/4 → right motor"
"Uno GND ↔ L298N GND"

One clear return-path strip across the width:
"STATUS BACK TO PC: Uno → MSP430 → Pico → Wi-Fi → ESP32 → USB → Laptop"
Below, small honest qualifier: "Full return path awaits the Pico–MSP wiring fix."

Bottom area: two or three subtle light-grey PLANNED cards, visually separate from tested links:
"XIAO ESP32S3 CAMERA — ON CAR"
"Images for pest monitoring"
"Camera link / processing pending"
Make explicit small text: "Separate board from FireBeetle"
"MSP430 #2 + BOOSTER — AT DOCK"
"Dock sensors + refill control"
"Communication / pins pending"
"SPRAY PUMP + DRIVER"
"MSP-authorised spraying"
"Hardware / pins pending"
Do not draw any assigned camera/dock Wi-Fi or GPIO link. Do not introduce charging, leak sensors or extra boards.

BOTTOM verification banner exact meaning with icons:
"✓ ESP32 ↔ Pico Wi-Fi tested    ✓ MSP430 ↔ Uno UART tested    ! Pico ↔ MSP430 still NOT_CONNECTED"
Small footer: "Based on tests: 3 Nov 2026 • Updated: 4 Nov 2026 • Signal diagram; USB power from a power bank carries no PC data."

Avoid dense paragraphs, decorative plants, tiny text, photoreal clutter, crossing wires, unlabeled connectors, invented pin assignments, extra Wi-Fi paths, false all-working claims. Keep exact board names and all pin labels spelled correctly. Make this easy to understand at a glance.
