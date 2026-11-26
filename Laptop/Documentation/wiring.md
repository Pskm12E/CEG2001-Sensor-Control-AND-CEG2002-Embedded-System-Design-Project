# Final robot wiring

The [board-by-board connection table](../Tools/Communication/board-placement.md#exact-signal-connections) shows the FireBeetle, car MSP430, desk Pico and Uno links. For the station use the [Booster Board pin map](../../Docking_Station/Booster_Board/README.md).

| Signal | Pin or connection |
| --- | --- |
| Car sonar | MSP430 P3.2 trigger, P2.7 echo through its divider |
| Car tank probe | MSP430 P6.0, ADC channel A0 |
| Car spray pump command | MSP430 P1.6 to MOSFET gate, with gate-to-source pull-down |
| Uno serial input | MSP430 P3.3 TX to Uno D6 RX |
| MSP430 serial input | Uno D13 TX through the divider to MSP430 P3.4 RX |
| FireBeetle to MSP430 | GPIO17 TX to MSP P4.2 RX and MSP P4.1 TX to GPIO16 RX |
| Dock arrival and reservoir | Station P2.4 Hall input and P3.2 comparator output |
| Dock refill pump and LCD | Station P1.4 pump command and P6.0–P6.6 LCD connections |

The [Zumo wiring guide](../../Car/Arduino_Uno/zumo_line_follow/README.md#connections) covers the six reflectance inputs. Each motor uses its own driver and power supply. The logic circuits share the applicable ground reference.
