# FireBeetle ESP32 to car MSP430

The FireBeetle is the access point on the robot. The XIAO camera and desk Pico join its network. Robot requests travel from the desk Pico to the FireBeetle and then to the car MSP430 over a 3.3 V UART at 9600 baud, 8N1.

| From | To |
| --- | --- |
| FireBeetle GPIO17 TX | Car MSP430 P4.2 RX |
| Car MSP430 P4.1 TX | FireBeetle GPIO16 RX |
| FireBeetle GND | Car MSP430 GND |

The `-EspUart` supervisor build remaps USCI_A1 to P4.1/P4.2. The MSP430's USB connector still supplies power and debug access. Its normal USB serial pins P4.4/P4.5 carry no application console in this build.

The Uno has a separate UART on MSP P3.3/P3.4. Its 5 V TX signal needs the documented divider. See the [complete board wiring](board-placement.md#exact-signal-connections).

## Matching programs

- [FireBeetle gateway](../../../Car/ESP32_Gateway/robot_wifi_gateway/robot_wifi_gateway.ino) publishes status and translates bounded requests.
- [Car MSP430 supervisor](../../../Car/MSP430/robot_supervisor/main.c) checks the link, motion, obstacle, tank and pump conditions.
- [Desk Pico W](../../Pico_W/laptop_wifi_bridge/main.cpp) connects the laptop USB stream to the private network.
- [Uno OG9](../../../Car/Arduino_Uno/zumo_line_follow/zumo_line_follow.ino) executes permitted track motion and acknowledges a stop.

Build the gateway and matching car supervisor with `./Laptop/Tools/Communication/build_direct.ps1 -Zumo -PumpDriverVerified`. See the [main README](../../../README.md#build-the-firmware) for all board builds. A live camera image confirms the video path. Fresh car telemetry additionally requires a response from the car MSP430.
