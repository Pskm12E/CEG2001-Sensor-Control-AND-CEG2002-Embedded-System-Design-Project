# Docking station

The station has its own MSP430F5529, Booster Board, reservoir sensor and
refill pump. Import the [station project](MSP430/README.md) in CCS.
The [pin map](Booster_Board/README.md) describes the station wiring.

## Laptop-connected docking

Connect both the **station MSP430 USB** and the **desk Pico W USB** to the
laptop. The Pico communicates with the FireBeetle on the car over the existing
private Wi-Fi. The station has its own pump supply.

1. Install the coordinated station CCS project in this folder on the **station**
   MSP430. The **car** uses the [Zumo supervisor](../Car/MSP430/robot_supervisor)
   with ESP UART, Zumo, verified P1.6 pump and a three-second spray setting.
   Also install the matching Uno OG9, FireBeetle gateway and desk Pico builds.
2. In Windows Device Manager, identify the station's **MSP Application UART**
   COM port by unplugging and reconnecting just the station. Close its CCS
   serial terminal. Leave the magnet away from the dock at startup.
3. Open PowerShell in the project root. For example, if **COM13** belongs to
   the station, run `& ".\Start Robot.cmd" --dock-port COM13`. Add
   `--no-camera` for a docking-only test. Wait for **Dock ready** before
   starting the car. Leave the dashboard server running and the laptop awake.

## One visit

| Event | Action |
| --- | --- |
| Two car P6.0 samples below 500 during forward travel | The Zumo reverses. With docking enabled, the car also requires a recent clear-station message to continue reversing. |
| First active Hall sample on station P2.4 | The station reports arrival on its nominal 100 ms sensor tick. The laptop requests a stop over Wi-Fi. Actual stopping also takes radio, controller and braking time. |
| Magnet qualifies for five samples and the Uno acknowledges STOP for this visit | The laptop renews a station permit. The station waits three seconds with both tracks commanded off. |
| Magnet present, permit fresh and station reservoir sufficient | The dock drives its refill pump on P1.4 for up to ten seconds. Moving the magnet, low station water or loss of permits cuts the pump. |
| Normal timed cutoff and two car readings above 500 | The station reports completion. The car authorizes forward line following after checking the visit ID, fresh water reading, stopped Uno and front obstacle interlock. |
| Fault or interrupted visit | The station consumes this attempt. Check the robot and clear the magnet before rearming. A car already parked when the dashboard reconnects stays parked. |

The station's reservoir comparator is on P3.2. The car uses its own tank ADC
on P6.0. A wet car sensor during filling keeps the robot parked until the
station reports the normal pump cutoff. Completion reports the pump output
command. The hardware has no flow or wheel-speed feedback.

The station reports `DOCK1 <visit> <phase>` on changes and periodically at
9600 baud. It accepts a matching `HOLD <visit>` followed by LF. The permit
expires after about 2.5 seconds without renewal. The car's clear-dock
permission expires after four seconds. Closing the USB link cannot deliver
an instant stop over a broken radio connection.

After installing, verify first with track and pump power off. Bring the
magnet to the station after the car reports reverse and check the dashboard
events for arrival, settling, fill and completion. Test the powered approach
with space to measure how far the tracks actually travel after detection.
