# Pump control-voltage test

**Installed, program-verified and left running on 18 November 2026.** The initial
USB descriptor fault was resolved by changing the USB cable. The idle check
confirmed P1.6 is a GPIO output with its latch LOW. The normal supervisor is
temporarily replaced; keep motor power off until it is restored. See the
[build and installation record](../../../Laptop/Artifacts/verification/pump-voltage-test-2026-11-18.json).

Standalone firmware for **MSP-EXP430F5529LP**, using the existing **P1.6** gate
output. It generates a test signal; it cannot detect whether a pump is connected,
measure pump current or confirm that water flows.

## Measure the control signal

1. Switch Zumo motor power off. **Disconnect the pump and its battery pack.**
   Leave the MSP430 powered by laptop USB. Turn dashboard detection off.
2. Use a multimeter in **DC voltage mode**, leads in **COM** and **V** sockets:
   black probe to MSP GND, red probe to **P1.6** (or gate, with source at GND).
   Do not use the current/amps socket for this voltage measurement.
3. After this test firmware is installed, P1.6 starts **LOW, about 0 V**.
4. **Press and release MSP430 S2**, the board's P1.1 button, once. P1.6 goes
   **HIGH, about 3.3 V, for 3 seconds**, then returns to 0 V. LED1 lights during
   the pulse. Press S2 again during the pulse to turn it off early.
5. Press and release again for another pulse. Holding a button does not repeat
   pulses; a button held during startup cannot activate the output by itself.

The timer bounds each pulse and a reset-mode watchdog guards a stalled program.
A GPIO voltage reading does **not** qualify the 2N7000 to drive the pump. Keep
the pump disconnected until its current and driver suitability are checked.

## Build without installing

From the repository root:

```powershell
./Car/MSP430/build_pump_voltage_test.ps1
```

Output: ignored `Debug/pump_voltage_test.out`. The build does not upload it.
**Flashing this test replaces the robot supervisor**, so robot communications,
ultrasonic stopping and automatic target jobs are unavailable during the test.
Restore the normal pump-disabled supervisor afterwards:

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo
```

That command also only builds; the resulting supervisor image must be flashed
to restore robot operation. Building this test does not upload it automatically;
the installed bench image described above was flashed separately.
