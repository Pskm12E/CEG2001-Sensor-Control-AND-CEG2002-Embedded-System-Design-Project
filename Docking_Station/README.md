# Docking station — planned

The intended dock uses a **second MSP430 plus the CEG2002 Booster Board**.
It is separate from the main MSP430 on the car.

| Folder | Status |
| --- | --- |
| [MSP430](MSP430/README.md) | Dock controller firmware has not been implemented |
| [Booster_Board](Booster_Board/README.md) | Component selection, sensor pins and interfaces remain to be assigned |

The intended role is local dock sensing and refill control. Robot-to-dock
communication, service interlocks and refill actuation are not integrated.
Charging remains manual; this directory does not add wireless charging or leak
detection requirements. There is no dock program to upload yet.
