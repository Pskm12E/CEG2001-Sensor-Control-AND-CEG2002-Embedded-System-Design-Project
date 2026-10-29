# Robot MSP430 initial LED test

This folder contains the original **v1.0 single-blink source** for the
MSP-EXP430F5529LP / MSP430F5529. It is retained as a standalone bring-up example.
The board's current, more capable project is
[robot_usb_console](../robot_usb_console/README.md).

## What this source does

- Red LED1 / P1.0: approximately 0.5 seconds ON, 0.5 seconds OFF.
- Green LED2 / P4.7: held off.
- Timer_A0 uses the REFO-derived ACLK; the CPU sleeps in LPM3 between interrupts.
- No button handling, USB serial commands, robot links or actuator control.

S2 therefore does not change this standalone v1.0 program. For the requested
double blink, S2/LED2 toggle and USB commands, use **robot_usb_console**.

## Build and upload

1. Connect the bare LaunchPad through its debugger USB port. Keep the normal
   debug/power jumpers in place.
2. Import this folder as an existing project into TI Code Composer Studio.
3. Select target **MSP430F5529**. The upper MSP430F5528 chip is part of the
   debugger, not the target device.
4. Build, then load/debug and resume the application. Uploading replaces the
   currently flashed program; compiling alone does not.
5. Observe LED1. It connects to P1.0 through JP8. No serial output is expected.

On the original Windows setup, `MSP430_Code/build_led_test.ps1` builds only,
using CCS21.0.1 and TI MSP430 compiler21.6.3.LTS under `D:/Apps/ccs`.
The CommonJS launcher helper is in `../tools/ccs-cli.cjs`.

## Earlier test history

Double-blink and S2 versions were successfully uploaded and user-observed during
development on 29 October. Before the USB-console milestone, this folder's
source was found reverted to the original v1.0. Those earlier results do not
describe the single-blink source published here. The double-blink/button features
are retained in the **current robot_usb_console** project instead.

[TI LaunchPad user's guide](https://www.ti.com/lit/ug/slau533d/slau533d.pdf)
