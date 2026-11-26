# Desk Pico W setup

The desk Pico W runs `DESK_BRIDGE_V3`. Its USB port connects to the laptop. Its radio joins the FireBeetle on the car. It carries JPEG video from the XIAO camera and status and bounded requests to the FireBeetle. The car MSP430 decides whether motion or a spray job is allowed.

## Start the monitor

1. Power the FireBeetle, car controllers and XIAO camera. Connect the desk Pico to the laptop with a USB data cable.
2. Open [Start Robot.cmd](../../../Start%20Robot.cmd). The launcher checks the Pico identity and starts the camera subscription. The dashboard shows each link separately.
3. For coordinated docking, connect the **station** MSP430 to a second USB port. The station and Pico have different serial identities.
4. Use **Start detection** for the blue marker. If video stays at 0 fps while car telemetry is current, check the XIAO camera power and its private Wi-Fi connection. If the camera is live while the car status is stale, check car MSP430 power and the FireBeetle-to-MSP UART.

## Build and identify the board

Run `python Laptop/Tools/Communication/configure.py` before building the Wi-Fi boards. Use `./Laptop/Tools/Communication/build_desk_pico.ps1` to compile the firmware. The Pico W image is `Laptop/Pico_W/laptop_wifi_bridge/build/laptop_wifi_bridge.uf2`.

The optional USB installer takes the actual Pico COM port, for example `./Laptop/Tools/Communication/upload_pico.ps1 -Port COM11 -Role Desk`. Compile first and close any dashboard or serial monitor using the port. Closing the dashboard also releases its video subscription. Use [the dashboard guide](../../Dashboard/README.md) for the normal operator controls.

The [Pico source](../../Pico_W/laptop_wifi_bridge/main.cpp) handles status freshness, JPEG delivery and visit or job identifiers. The [communications guide](README.md) lists the other boards that must use matching Wi-Fi settings.
