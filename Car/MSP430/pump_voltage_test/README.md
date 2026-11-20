# Pump control-voltage test

**Bench test completed, 20 November 2026.** Two user-observed pump runs confirmed
P1.6-controlled operation and automatic cutoff after about three seconds. The
[integrated pump supervisor](../robot_supervisor/PUMP_SETUP.md) is now installed.
The earlier missing visible LED behavior remains unresolved.

This standalone test remains available for voltage checks. Installing it replaces
the normal robot supervisor. The original USB descriptor fault was resolved by
changing the USB cable.

## Measure the control signal

1. Switch power off. **Disconnect the pump, its battery pack, and the P1.6 wire
   to the MOSFET circuit.** Power only the MSP430 by laptop USB for this initial
   unloaded GPIO check. Leave Zumo motor power off and dashboard detection off.
2. Use a multimeter in **DC voltage mode**, leads in **COM** and **V** sockets:
   black probe to MSP GND, red probe directly to **P1.6**.
   Do not use the current/amps socket for this voltage measurement.
3. After this test firmware is installed, P1.6 starts **LOW, about 0 V**.
4. **Press MSP430 S2**, the board's P1.1 button, once. After about 30 ms of
   debounce, P1.6 goes **HIGH, about 3.3 V, for 3 seconds**, then returns to 0 V.
   **Red LED1 blinks about twice per second** during this interval, then stays
   off. P1.6 remains steadily HIGH through the LED's dark intervals for the meter.
5. Release S2 after pressing and leave it alone for five seconds. Another press
   during the test turns it off early, which can give unsettled meter readings.
   After it ends, a fresh press starts another test. Holding a button does not repeat
   pulses; a button held during startup cannot activate the output by itself.

The timer bounds each pulse and a reset-mode watchdog guards a stalled program.
The measurement steps above use a disconnected load. The later connected-pump
bench runs and current deployment are recorded in the integrated cycle guide.

The timer is configured for approximately 3.003 seconds of normal execution.
Debugger halt/resume sampling can stretch that interval in wall time; measure
the normal pulse after the debugger disconnects. Runtime diagnostic counters
record timer/main-loop progress and observed starts/stops. Physical HIGH voltage
and visible LED operation require the user's bench measurement; an idle latch
check alone does not establish them.

## Build without installing

From the repository root:

```powershell
./Car/MSP430/build_pump_voltage_test.ps1
```

Output: ignored `Debug/pump_voltage_test.out`. The build does not upload it.
**Flashing this test replaces the robot supervisor**, so robot communications,
ultrasonic stopping and automatic target jobs are unavailable during the test.
Restore the integrated supervisor afterwards.

```powershell
./Car/MSP430/build_robot_supervisor.ps1 -EspUart -Zumo -PumpDriverVerified -SpraySeconds 3
```

That command also only builds; the resulting supervisor image must be flashed
to restore robot operation. Building this test does not upload it automatically;
the installed bench image described above was flashed separately.
