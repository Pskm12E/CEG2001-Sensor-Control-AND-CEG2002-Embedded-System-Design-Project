# Car electronics

The Arduino Uno runs OG9 on the Zumo Shield. The MSP430 grants motion and
controls the pump. The robot pauses at a measured **5 cm** obstacle and resumes
line following after two valid readings of **7 cm or farther**. On an accepted
camera job it stops, drives the pump on **P1.6 for three seconds**, and waits
for a matching continuation. The operator confirmed the pump works after a
resistor replacement. [Spray sequence and wiring](MSP430/robot_supervisor/PUMP_SETUP.md)

| Device | Program / responsibility |
| --- | --- |
| [MSP430](MSP430/README.md) | `robot_supervisor` with the ESP-UART, Zumo and verified-driver options |
| [Arduino_Uno](Arduino_Uno/README.md) | Saved line calibration, line following, reverse and flip alarm |
| [ESP32_Gateway](ESP32_Gateway/README.md) | FireBeetle private Wi-Fi access point and MSP UART bridge |
| [XIAO_ESP32S3_Camera](XIAO_ESP32S3_Camera/README.md) | Wireless camera; USB-C supplies power during use |

Use [the Zumo wiring/button guide](Arduino_Uno/zumo_line_follow/README.md),
[agreed two-plant track](Track/README.md) and
[removable enclosure CAD](Mechanical/Zumo_Enclosure/README.md).
