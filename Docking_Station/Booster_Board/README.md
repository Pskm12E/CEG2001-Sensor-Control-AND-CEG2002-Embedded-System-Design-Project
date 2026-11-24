# CEG2002 Booster Board — dock peripherals

The [station firmware](../MSP430/waterlevel/main.c) uses these station GPIOs.

| Function | Dock MSP430 pin | Signal |
| --- | --- | --- |
| Hall sensor | P2.4 | Low when the magnet is present, 3.3 V compatible |
| Station reservoir comparator | P3.2 | High when water is sufficient, external 3.3 V pull-up |
| Refill pump driver | P1.4 | High commands the driver on |
| Dock indicator | P1.0 | High after confirmed arrival |
| Low-water LEDs | P1.2, P1.3, P8.1, P8.2 | Four-LED chase |
| LCD | P6.0–P6.6 | D4–D7, RS, RW, EN |
