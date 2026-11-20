# User button and onboard LEDs only

Used and program-verified on **18 November 2026**. The
[integrated pump supervisor](../robot_supervisor/PUMP_SETUP.md) replaced this
diagnostic on **20 November**. Installing this test temporarily replaces the supervisor. The pump output is disabled: **P1.6 is an input with a
pull-down and is never driven HIGH**. Keep pump and Zumo motor power off.

**Last tested diagnostic mode was automatic.** Red LED1 is requested ON
for one second and OFF for one second continuously; no button press is needed.
Green LED2 stays ON and P1.6 stays disabled. S2 and SW1/S1 builds remain available.

For either button build, use the following sequence.

1. Power the MSP430 through laptop USB and release the selected button.
2. **Green LED2 stays ON** when the program is ready.
3. Press the selected button once, **S2/P1.1** by default or **SW1/S1/P2.1** with
   `-Switch1`. **Red LED1/P1.0 flashes six times over about
   three seconds**, then stays OFF. Green remains ON.
4. Release the button before another press. Holding it does not repeat the test.

This program uses a simple polling loop and fixed delays. It does not depend on
the camera, pump, UART, interrupt-driven pulse controller or watchdog servicing.
The user confirmed two direct three-second pump runs on 20 November. The normal
pump-enabled supervisor is now installed. S2 is a temporary debugging control.

Build only, from the repository root:

```powershell
./Car/MSP430/build_s2_led_test.ps1 -Automatic
```

Output: ignored `build-auto/s2_led_test.out`. Use `-Switch1` for SW1/S1 in
`build-sw1/`, or omit both options for S2 in `Debug/`. Building does not upload an image. Software
tests execute the actual main with timed button inputs and check six flashes,
held-button suppression, automatic one-second transitions, the ready indicator
and P1.6 remaining disabled. All three configurations pass 3395 assertions.

The startup register check confirmed LED2's output latch HIGH and P1.6 disabled.
The user confirmed the green ready light and red illumination during the direct
30-second check, but did not see blinking from S2, SW1 or automatic mode.
Debugger checks recorded automatic red-output transitions. The difference
between these checks and visible operation remains unresolved. The official
[LaunchPad schematic](https://e2echina.ti.com/cfs-file/__key/communityserver-discussions-components-files/55/MSP_2D00_EXP430F5529LP_5F00_Schematic.pdf)
shows JP8 in the P1.0-to-LED1 connection. Its physical state has not been verified.

This diagnostic omits normal robot communications, ultrasonic STOP and target
jobs. Restore the integrated supervisor after using it.
