# Car electronics

The **MSP430 is the main robot controller**. The other boards provide camera,
wireless communication, line sensing and wheel control.

| Device folder | Current program | Responsibility |
| --- | --- | --- |
| [MSP430](MSP430/README.md) | `robot_supervisor/main.c`, ESP-UART build | Main supervisor; checks Uno state and controls movement authorisation/timeouts |
| [Arduino_Uno](Arduino_Uno/README.md) | `msp_line_follow/msp_line_follow.ino` | D2/D4 IR sensors and L298N wheel outputs under MSP430 supervision |
| [ESP32_Gateway](ESP32_Gateway/README.md) | `robot_wifi_gateway/robot_wifi_gateway.ino` | FireBeetle private Wi-Fi access point and UART bridge to MSP430 |
| [XIAO_ESP32S3_Camera](XIAO_ESP32S3_Camera/README.md) | `xiao_camera_wifi/xiao_camera_wifi.ino` | Wireless OV3660 live video; USB-C is power only during use |
| [Archive](Archive/README.md) | Earlier experiments | Historical Pico motor/I2C programs and local backup locations |

```text
Camera ---- private Wi-Fi ---- FireBeetle ESP32
                                      |
                              UART 9600, 3.3 V
                                      |
                               MAIN MSP430
                                      |
                           UART + Uno TX divider
                                      |
                              Arduino Uno
                              /         \
                        IR D2/D4      L298N → wheels
```

Camera video and robot status return through the **desk Pico** to the laptop.
See [exact connections](../Laptop/Tools/Communication/board-placement.md).
Automatic pest jobs, spraying and full track calibration remain unfinished.
Build commands run on the laptop; the firmware produced belongs to each board.
