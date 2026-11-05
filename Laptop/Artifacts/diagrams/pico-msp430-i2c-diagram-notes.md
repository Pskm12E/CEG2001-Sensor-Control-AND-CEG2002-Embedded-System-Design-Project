# Pico/MSP wiring diagram creation notes

Created 3 November 2026 using the built-in image-generation tool (not the CLI).
Assets: `pico-msp430-i2c-simple.png` and `pico-msp430-i2c-breadboard.png`.
Visually checked the final labelled pins, coloured connections, resistor
endpoints and five-hole row grouping against `Laptop/Tools/Communication/msp-bridge-wiring.md`.
This verifies the illustration, not the user's assembled circuit.

The breadboard generation specification used a 170-point mini breadboard with
17 rows and A-E / F-J groups. A4 receives Pico GP4, E4 connects MSP P3.0;
A8 receives Pico3V3; R1 is D4-D8, R2 is C8-C12; A12 receives Pico GP5,
E12 connects MSP P3.1; A16 receives PicoGND, E16 connects MSPGND. Right bank
unused. Pin blocks are logical, not physical pin layouts. Existing Uno divider
must remain connected separately.

Final edit prompt, applied to the generated breadboard image:

> Edit this wiring infographic with ONE SMALL correction only. Preserve every word, every hole, every wire, every endpoint, all colors of wires/highlighted rows, all junctions, board blocks, layout, size and labels EXACTLY. Replace the colorful horizontal stripes on the bodies of BOTH resistors with plain solid pale beige bodies, with NO color bands at all. Retain the adjacent text labels 'R1 4.7 kΩ' and 'R2 4.7 kΩ'. Both resistors remain at the same holes: R1 from D4 to D8; R2 from C8 to C12. Do not move or redraw any wire endpoints. This change avoids teaching an incorrect color code from an illustration. Everything else must be unchanged.
