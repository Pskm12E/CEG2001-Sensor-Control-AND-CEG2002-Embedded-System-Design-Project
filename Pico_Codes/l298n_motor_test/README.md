# Forward-only L298N test for Pico W

**Archived experiment.** The project now uses the **Arduino Uno** for wheels
and the Pico W for the [wireless link](../../Wireless_Link/README.md).
Do not use this pin map for the current Uno wiring.

The L298N has no user-programmable firmware. The Pico program controls four
direction inputs and two enable inputs. The MSP430 will remain the main controller
in the final robot; this separate project is a manual bench test only.

## Status

This firmware starts with the motor outputs off. After upload, sending `f` or `F`
through the USB serial monitor commands BOTH wheels in the configured forward
direction for one second at 40% PWM, then disables the outputs. Sending `s` or `S`
stops early. There are no reverse or turn commands, and it does not start driving
automatically at power-up.

The previous compile-time motor lock has been removed: this firmware WILL drive
the motor pins when it receives `f`. It was not uploaded during that experiment
because the battery, module jumpers and wiring were unverified. The Pico now
runs the separate wireless bench firmware; uploading this replaces it.

## Proposed signal connections

Pin numbers below are for the original Raspberry Pi Pico W. GP numbers are not
the same as physical header pin numbers.

| Pico signal | Physical pin | L298N module label | Function |
|---|---:|---|---|
| GP6 | 9 | IN1 | Left motor direction input 1 |
| GP7 | 10 | IN2 | Left motor direction input 2 |
| GP8 | 11 | ENA | Left motor PWM enable |
| GP9 | 12 | IN3 | Right motor direction input 1 |
| GP10 | 14 | IN4 | Right motor direction input 2 |
| GP11 | 15 | ENB | Right motor PWM enable |
| GND | 13 | GND | Common signal ground |

Left motor connects to OUT1/OUT2; right motor connects to OUT3/OUT4. The actual
wheel direction depends on motor lead orientation and mounting. Check each wheel
with the chassis raised before attempting travel.

For a standard module with ENA/ENB jumpers that tie the enable inputs to 5 V,
remove BOTH enable jumpers before attaching Pico PWM outputs. Add a 10 kOhm
pull-down from each enable input to common ground so the bridges stay disabled
while the Pico is resetting or unplugged. Confirm the module's actual labels and
circuit before doing this. The separate 5V-EN regulator jumper has a different
purpose; do not confuse it with ENA/ENB.

The L298 chip accepts a logic high from 2.3 V, so Pico 3.3 V control outputs meet
its input specification. Its logic power supply is a separate requirement: do not
power L298 logic from Pico 3V3. A module's regulator and 5 V terminal configuration
must be checked from its specific documentation or circuit.

## Power information still needed

Before giving a battery-terminal wiring plan, confirm:

- A photo of the actual module, including the power terminals and all jumpers.
- Wheel motor rated voltage and stall current, or its identifiable model.
- The battery/supply voltage and current capability.

For initial testing, power the Pico by USB and the driver/motors from an appropriate
motor supply, with a common ground. Route motor return current directly to the
driver/supply rather than through the Pico or its breadboard leads. Leave the
module's 5 V terminal disconnected from the Pico while USB powers the Pico.
Never connect a motor output or battery positive to a Pico GPIO.

The L298 has a significant, current-dependent voltage loss and heats up under
load. A label such as "2 A" is not proof that the module can continuously run the
actual motors. PWM limits average motor drive; it does not make an unsuitable
battery voltage safe or measure motor current.

## Run the test after the hardware checks

1. Raise the wheels clear of the table and arrange a reachable motor-power switch.
2. Compile this project and upload `build/l298n_motor_test.uf2`. Disconnect motor
   power while wiring or uploading; apply it only after the outputs are confirmed
   idle and the wheels are raised.
3. Open its USB serial monitor at 115200 baud.
4. Wait for `FORWARD TEST READY`. Send `f` using the monitor's message field.
   Both wheels are commanded for ONE second at 40% PWM, then the monitor reports
   `STOPPED`. Further `f` characters during that pulse do not extend it.
5. Send `s` to disable the outputs early. USB disconnect also cancels motion, and
   reconnecting does not resume it. The timeout is checked by the firmware loop;
   keep the physical motor-power switch reachable as well.
6. Check that BOTH wheels turn in the car's forward direction. With motor power
   off, swap the two motor leads for any wheel turning backwards, or change that
   wheel's `LEFT_FORWARD_IN1_HIGH` / `RIGHT_FORWARD_IN3_HIGH` setting and rebuild.
7. Only after the raised-wheel test works, try one pulse on a clear floor with
   enough USB cable slack. Without feedback, equal PWM cannot guarantee a straight
   path or a particular travel distance.

At 40% duty some motors will not start. Do not assume that means the Pico failed,
or repeatedly leave a stalled motor energized. Check wiring and supply first.
EN low makes the motors coast; it does not actively brake the wheels. This test
has no obstacle sensing, motion feedback or MSP430 command interface yet.

## Code checks

On 9 October 2026, the Pico W firmware build succeeded and the host-side controller
tests passed. The generated UF2 is `build/l298n_motor_test.uf2` (62,464 bytes).

`tests/forward_test_test.cpp` checks that the controller stays idle at startup,
limits each command to one second, ignores repeated forward commands during a
pulse, stops on request or USB loss, and ignores turn/reverse commands. These
software checks do not verify the physical wiring, motor direction or wheel speed.

## Reference

[ST L298 datasheet](https://www.st.com/resource/en/datasheet/l298.pdf): logic and
enable thresholds, input functions, truth table, and output voltage drop.
