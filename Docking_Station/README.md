# Docking station

The station has its own MSP430F5529, Booster Board, reservoir sensor and
refill pump. Import the [station project](MSP430/README.md) in CCS.
The [pin map](Booster_Board/README.md) describes the station wiring.

## Standalone refill used in the station trial

Use the [standalone CCS project](MSP430/standalone) for the local Hall-sensor and reservoir demonstration. With the bay clear, five absent samples arm the station. Five present samples confirm arrival. The dock waits three seconds, then powers its refill driver for up to ten seconds while the magnet stays present and the comparator reports sufficient water. The LCD displays the status. USB can carry diagnostic output. This image does not exchange stop or departure permits with the car.

## Laptop-connected docking

Connect both the **station MSP430 USB** and the **desk Pico W USB** to the
laptop. The Pico communicates with the FireBeetle on the car over the existing
private Wi-Fi. The station has its own pump supply.

1. Install the coordinated station CCS project in this folder on the **station**
   MSP430. The **car** uses the [Zumo supervisor](../Car/MSP430/robot_supervisor)
   with ESP UART, Zumo, verified P1.6 pump and a three-second spray setting.
   Also install the matching Uno OG9, FireBeetle gateway and desk Pico builds.
2. Close the station's CCS serial monitor and open **Start Robot.cmd**. The
   launcher listens for the station on the MSP application UART ports. Use
   **Find station USB** if you plug it in later. You can also specify a known
   station port with `--dock-port COM3`. Use the station's application UART.
   On the project laptop COM3 was the station and COM13 was the car.
3. Look under **Docking station** for **Docked** or **Undocked**. A magnet
   already present at power-up is displayed, and the robot stays parked.
   Remove the magnet to arm the next returning visit. Record the empty and
   full car tank readings in the dashboard, then keep both USB boards connected.

## One visit

| Event | Action |
| --- | --- |
| Two car P6.0 samples below 500 during forward travel | The Zumo reverses. With docking enabled, the car also requires a recent clear-station message to continue reversing. |
| First active Hall sample on station P2.4 | The station reports arrival on its nominal 100 ms sensor tick. The laptop requests a stop over Wi-Fi. Actual stopping also takes radio, controller and braking time. |
| Magnet qualifies for five samples and the Uno acknowledges STOP for this visit | The laptop renews a station permit. The station waits three seconds with both tracks commanded off. |
| Magnet present, permit fresh and station reservoir sufficient | The dock drives its refill pump on P1.4 for up to ten seconds. Moving the magnet, low station water or loss of permits cuts the pump. |
| Fresh car tank reading strictly above 60% during an acknowledged visit | The laptop requests pump cutoff. When the station confirms completion, magnet present and pump off, a three-second departure pause starts. The dashboard shows the countdown. A reading at or below 60% resets it. At the end the car checks the visit, stopped Uno, water and obstacle interlocks before driving forward. |
| Ten-second pump cutoff reached while the tank is at or below 60% | The pump stays off and the Zumo waits for a fresh reading above 60% on the same visit. |
| Fault or interrupted visit | The station consumes this attempt. Check the robot and clear the magnet before rearming. A car already parked when the dashboard reconnects stays parked. |

The station's reservoir comparator is on P3.2. The car uses its own tank ADC
on P6.0. The threshold uses the unrounded car tank percentage. With empty 1836
and full 2281, raw 2103 is exactly 60% and 2104 qualifies. Completion reports the pump output
command. The hardware has no flow or wheel-speed feedback.

The station reports `HALL1 <0|1|?> PUMP=<0|1>` and `DOCK1 <visit> <phase>`
on changes and periodically at 9600 baud. The laptop sends `HOLD <visit>`
to renew the stopped-car permit and `FULL <visit>` to end the refill. The permit
expires after about 2.5 seconds without renewal. The car's clear-dock
permission expires after four seconds. Closing the USB link cannot deliver
an instant stop over a broken radio connection.

After installing, verify first with track and pump power off. Bring the
magnet to the station after the car reports reverse and check the dashboard
events for arrival, settling, fill and completion. Test the powered approach
with space to measure how far the tracks actually travel after detection.
