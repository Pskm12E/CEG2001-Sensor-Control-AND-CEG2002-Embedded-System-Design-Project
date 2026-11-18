# S2 and onboard LEDs only

Installed and program-verified on **18 November 2026**. This temporarily replaces
the robot supervisor. The pump output is disabled: **P1.6 is an input with a
pull-down and is never driven HIGH**. Keep pump and Zumo motor power off.

1. Power the MSP430 through laptop USB and release S2.
2. **Green LED2 stays ON** when the program is ready.
3. Press **MSP S2 / P1.1** once. **Red LED1 / P1.0 flashes six times over about
   three seconds**, then stays OFF. Green remains ON.
4. Release the button before another press. Holding it does not repeat the test.

This program uses a simple polling loop and fixed delays. It does not depend on
the camera, pump, UART, interrupt-driven pulse controller or watchdog servicing.
The pump-and-blinking test is the next step after the physical LEDs work.

Build only, from the repository root:

```powershell
./Car/MSP430/build_s2_led_test.ps1
```

Output: ignored `Debug/s2_led_test.out`. Building does not upload it. Software
tests execute the actual main with timed button inputs and check six flashes,
held-button suppression, the ready indicator and P1.6 remaining disabled.

The startup register check confirmed LED2's output latch HIGH and P1.6 disabled.
The user confirmed the green ready light, but has not seen the red S2 blink.
If green lights but red does
not, inspect the red LED1 path rather than repeatedly reflashing. The official
[LaunchPad schematic](https://e2echina.ti.com/cfs-file/__key/communityserver-discussions-components-files/55/MSP_2D00_EXP430F5529LP_5F00_Schematic.pdf)
shows JP8 in the P1.0-to-LED1 connection. A missing connection is a possibility,
not a confirmed diagnosis; identify the board/jumper before moving anything.

Normal robot communications, ultrasonic STOP and automatic spray jobs remain
unavailable until the normal pump-disabled supervisor is restored.
