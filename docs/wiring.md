# Version 1 wiring and board connections

Use these notes with the individual sketch README. They describe the known bench
pin assignments, not a completed power distribution or integrated robot schematic.

## Arduino Uno → L298N → wheels

| From | To |
| --- | --- |
| Uno D7 | L298N IN1 |
| Uno D8 | L298N IN2 |
| Uno D9 | L298N IN3 |
| Uno D10 | L298N IN4 |
| Uno GND | L298N GND |
| Left motor | OUT1 / OUT2 |
| Right motor | OUT3 / OUT4 |
| Suitable motor battery + | Driver motor-supply terminal, often labelled +12V / VIN |
| Motor battery − | Driver GND |

The Uno is USB powered in the current bench setup. The separate four-AA holder
was used for the driver. The terminal label `+12V` does not specify the motors'
required voltage. Motor ratings, battery performance and the module's logic
supply must be checked; four AAs may not provide enough headroom for its onboard
5 V regulator. Do not feed the motor supply through a board's GPIO/5 V pin.

The sketches assume **ENA and ENB enable jumpers** are fitted. These are separate
from the **5V-EN regulator jumper**. Do not connect the driver's 5 V terminal to
another supply without checking that regulator/jumper arrangement.

## Two digital IR sensors → Uno

| Sensor connection | Uno connection |
| --- | --- |
| Left OUT | D2 |
| Right OUT | D4 |
| Both VCC | 3.3 V, as used in this project's current test wiring |
| Both GND | GND |

Left/right are viewed from behind the car, facing forward. The code uses INPUT,
not a 5 V internal pull-up. Verify the actual modules support the chosen supply.
Calibrate each sensor over white and black at its mounted height. This line
follower expects **both sensors over black when centred on a wide strip**.

## Robot MSP430

Board: **MSP-EXP430F5529LP**, target **MSP430F5529**. The upper MSP430F5528 chip
belongs to the debugger; it is not the firmware target.

| Connection | Function in current robot_usb_console |
| --- | --- |
| USB through the LaunchPad debugger | Power/programming and Application UART console |
| P1.0 | Red LED1, double blink |
| P4.7 | Green LED2 |
| P1.1 / S2 | Button toggles LED2 |
| P4.4 TX / P4.5 RX | UART1 USB backchannel; used by current dashboard |
| P3.3 TX / P3.4 RX | UART0 reserved for proposed Uno diagnostic link |

### Proposed MSP430 ↔ Uno UART bench link

This link is **not yet physically verified**. Use a suitable 3.3 V ↔ 5 V logic-level
converter; inspect its actual pin labels first. The proposal uses 9600 baud:

| From | Through converter | To |
| --- | --- | --- |
| MSP430 P3.3 TX | LV1 ↔ HV1 | Uno D5 RX |
| MSP430 P3.4 RX | LV2 ↔ HV2 | Uno D6 TX |
| MSP430 3V3 | LV reference | — |
| Uno 5V | HV reference | — |
| Both board grounds | Common GND | — |

Power each board by USB for the bench test. Do not join their positive supply
rails. Upload `uart_link_bench` to the Uno only for this test: the line-following
sketch does not yet implement this serial protocol. Motor supply stays disconnected.

## ESP32 and Pico W

For Version 1, each uses its own USB data cable. **No header pins between them
are needed**: the link is Wi-Fi. The Pico only drives its onboard LED during
the wireless test. Its robot mounting is a future physical step.

**Pico-to-MSP430 pins are still unassigned.** Do not connect another transmitter
to P3.3/P3.4 while those pins are allocated to the Uno. P4.4/P4.5 are also occupied
by the current USB console. Select the bus and pin allocation before integration.

## Still to confirm

- Dock MSP430 and Booster exact models, sensor pin map and communication path.
- Pump voltage/current, driver, nozzle control, dosing feedback and tank sensing.
- Ultrasonic model and final pin allocation; D11/D12 were only a proposal.
- Regulated battery rails and current budget for the finished robot.
- Stop-marker detection and reliable track calibration.

Automatic charging and leak detection are not implemented in Version 1.
