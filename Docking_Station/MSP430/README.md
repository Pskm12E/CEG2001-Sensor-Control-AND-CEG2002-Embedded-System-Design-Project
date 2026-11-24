# Second MSP430 — dock controller

Import [waterlevel](waterlevel) into Code Composer Studio for the station's
MSP430F5529. The project includes the LCD driver, linker script and debugger
configuration from the supplied 24 November project. Its CCS settings select
TI MSP430 compiler 21.6.2.LTS. The project also builds with 21.6.3.LTS.

The station uses P2.4 for magnet detection, P3.2 for its own reservoir comparator
and P1.4 for the refill driver. Its USB backchannel uses 9600 baud, 8N1.
The [car supervisor](../../Car/MSP430/robot_supervisor) is a separate image.
