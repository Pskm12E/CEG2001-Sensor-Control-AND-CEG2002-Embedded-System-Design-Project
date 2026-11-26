# Car ultrasonic sensor

The HC-SR04 measures the distance in front of the Zumo. Trigger uses P3.2 and the divided echo signal uses P2.7. Connect the sensor ground to the MSP430 ground. The 5 V echo goes through a 2.2 kΩ upper resistor to the MSP input and a 3.3 kΩ lower resistor from that input to ground.

Timer_A2 times the trigger and echo, and Port 2 records the rising and falling edges. The foreground converts pulse duration to distance in centimetres. A valid reading of 5 cm or closer pauses an eligible forward run. Two consecutive valid readings of at least 7 cm release that obstacle pause. Missing echoes alone cannot resume it.

See the [timing implementation](ultrasonic_hcsr04.h), [decision thresholds](obstacle_guard.h) and [Zumo wiring guide](../../Arduino_Uno/zumo_line_follow/README.md#connections). The sonar faces forward during a low-tank reverse.
