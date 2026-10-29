# Board placement

**During today's setup:** plug the ESP32 and Pico W into the laptop by USB.
The MSP430 can stay unplugged. No jumper wires between boards are needed for
the wireless LED test.

**On the finished prototype:** the ESP32 stays beside the laptop, the Pico W
rides on the robot, and the robot's MSP430 remains in charge.

```mermaid
flowchart TB
  subgraph desk[DESK / TEST PLANT]
    direction LR
    cam[USB webcam] -->|USB| pc[Laptop<br/>Website + image processing]
    pc -->|USB| esp[ESP32<br/>Wireless gateway]
  end
  subgraph robot[ROBOT CHASSIS]
    direction TB
    pico[Pico W<br/>Wireless messages]
    main[MSP430 #1<br/>MAIN CONTROLLER]
    uno[Arduino Uno<br/>Wheel + line control]
    ir[Left IR: D2<br/>Right IR: D4]
    driver[L298N motor driver]
    wheels[Left + right motors]
    spray[Water pump + suitable driver<br/>Control wiring still to confirm]
    pico -. future wired link; pins pending .-> main
    main -. future command/status link .-> uno
    ir --> uno
    uno --> driver --> wheels
    main -. future bounded spray control .-> spray
  end
  subgraph dock[DOCKING STATION]
    direction TB
    station[MSP430 #2 + Booster<br/>Dock controller]
    service[Dock sensors + refill pump driver<br/>Hardware and firmware pending]
    station -.-> service
  end
  esp <-->|Wi-Fi bench link| pico
  main -. dock communication path pending .-> station
  style main fill:#dff1e5,stroke:#1c6843,stroke-width:3px
  style pico fill:#e6efff,stroke:#325ca2
  style esp fill:#e6efff,stroke:#325ca2
```

Solid arrows describe physical connections or the wireless bench link. They do
not certify the entire robot has been tested. Dashed arrows are future integration.
The website-to-gateway connection still needs software integration; today's ESP32
USB commands use a serial console.

Mount the robot's electronics on a dry upper platform with spacers. Keep the
Pico's antenna end clear of the battery, motor driver and metal. Mount the two IR
sensors at the front facing down at matching height; mounting height/spacing and
the wide black strip must be calibrated together. Place the water tank low and
securely, with the pump and tubing separated from the boards. Final power
distribution and pump ratings must be checked before connecting them.

Charging remains manual. This diagram does not add wireless charging or a leak
sensor. The dock's exact sensing, Booster model and robot communication path are
still to be confirmed.
