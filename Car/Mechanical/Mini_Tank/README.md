# Mini water tank and glue-on holder — provisional

**Current Zumo layout, 17 November 2026:** the user now specifies a cut-bottle
tank approximately 60 mm diameter x 100 mm high, with 100 mL water. See the
[current enclosure design](../Zumo_Enclosure/README.md). The rectangular tank
and holder below are an earlier draft and are not the current bottle cradle.

Two separate printable parts for the robot. The tank lifts vertically out of a
holder whose flat rear face bonds to the side of the mount.

The user reported approximately **3 cm length × 7.5 cm height × 2 cm width**.
This draft conservatively interprets that as the complete assembly envelope:
30 mm along the mount, 75 mm vertically, and 20 mm outward. It remains unclear
whether the 20 mm is instead the mount's own thickness. These are design
dimensions, not measurements extracted from the photograph.

## Dimensions

All dimensions are millimetres. Order: width along mount × outward depth × height.

| Feature | Size |
| --- | --- |
| Tank outer body | 25 × 15 × 55 |
| Tank clear cavity | 21 × 11 × 52 |
| Tank walls / floor | 2 / 3 |
| Holder overall | 30 × 20 × 75 |
| Flat rear glue face | 30 × 75 |
| Holder pocket | 26 × 16 |
| Tank-to-holder clearance | 0.5 on each side |
| Holder walls / floor | 2 / 3 |
| Retaining walls | Top 28 above holder bottom; 25 above support floor |
| Drain opening in holder floor | 4 × 4 |
| Seated tank rim height | 58 above holder bottom |
| Empty tank capacity to rim | 12.012 ml |
| Illustrated working water depth | 35; leaves 17 headspace |
| Working water with example probe | Approximately 7 ml |

The holder's drain opening is **not** in the tank. The tank has an uninterrupted
floor and no plumbing holes. The 20 mm assembly depth excludes adhesive thickness.

## Sensor fit still needs confirmation

The user describes the sensor as **UNO Mega2560 rainwater level sensor for
Arduino**. That compatibility description suggests the narrow resistive probe
family, but does not uniquely identify its manufacturer or dimensions.
The reference shown in the mockup uses a **62 × 20 × 8 mm** module envelope, matching the dimensions
published for [HALJIA's water-level sensor](https://www.haljia.com/products/haljia-rain-water-level-sensor-module-depth-of-detection-liquid-surface-height-compatible-with-arduino).
This is an example, not an identification of the user's sensor.

Published variants differ: [Keyestudio](https://docs.keyestudio.com/projects/KS0522/en/latest/docs/lessons/lesson-23-water-level.html)
lists 65 × 20 × 8 mm, while [SunFounder UMSK](https://docs.sunfounder.com/projects/umsk/en/latest/01_components_basic/25-component_water_level.html)
lists a 60 × 22 mm PCB. **The 22 mm version cannot fit this draft's 21 mm cavity.**
A 65 mm long, 20 mm wide version fits the nominal illustrated envelope, reaching
73 mm above the holder bottom with its tip 2 mm above the internal floor.
Confirm with the actual product link, a close-up identification, or a width
measurement before finalizing. No geometry was changed solely from the generic
compatibility description.

For the illustration, the PCB thickness is assumed to be 1.6 mm and the lower
40 mm is the sensing region. The probe tip sits 2 mm above the cavity floor;
the board extends 12 mm above the tank rim. The connector is dry. Only the
sensing tracks should contact water; confirm the actual board's permitted wet
region. The 21 mm cavity provides only **0.5 mm per side** around a 20 mm board.
Printing tolerance and attached components can consume this clearance.

The sensor position is illustrative: **a sensor clip is not yet designed or
included**. Its shape and mounting location depend on the actual sensor.
Confirm sensor length, width, board thickness, connector envelope and available
mounting holes before a final fit revision. The reservoir can be filled through
the open top; a splash lid and pump outlet are not included in this two-part draft.
For use on a moving robot, a splash cover and positive tank retention still need
to be resolved; the current holder allows the tank to lift out.

## Files

- `dimensions-and-mockup.png`: dimensioned CAD views and sensor section.
- `tank-provisional.stl`: tank, upright and open top up.
- `holder-provisional.stl`: holder, upright with its bottom on the bed.
- `mini_tank.scad`: editable OpenSCAD; choose `part = "tank"`, `"holder"`, or `"assembly"`.
- `dimensions.json`: source dimensions used by the generator.
- `build_models.py`: generates the STL solids, OpenSCAD source and drawing.
- `validation.json`: mesh and dimensional checks from the generator.

Import STL files as **millimetres**, with **no scaling**. Each file is one solid
part. The open tank cavity does not make the material shell an open/non-manifold
mesh. The prototype package does not contain printer-specific G-code.

## Printing and checking

Use the upright orientations already in the STLs. Their walls rise directly
from the floor, so the nominal geometry does not require support. Start with a
0.4 mm nozzle, 0.2 mm layers, at least four perimeter paths and a solid tank
floor; inspect the slicer preview to ensure the full 2 mm walls and 3 mm floor
are filled without voids. Use a calibrated material profile and test a small
fit sample if your printer's clearance is unknown.

A closed CAD mesh does not guarantee that an FDM print holds water.
[Prusa's watertight-print guidance](https://help.prusa3d.com/article/watertight-prints_112324)
explains the effects of perimeter count, layer bonding and printer settings.
Leak-test the tank separately, on dry tissue, before bringing it near the
robot's electronics. Keep the electronics portion of the sensor above water.

Dry-fit the holder on the actual mount and check wheels, cables, ground clearance
and vertical removal space. Use adhesive suitable for the actual printed plastic
and mount material, following its surface preparation and cure instructions.
The glued joint and the 2 mm backplate have not been load-tested. Check the
cured mount with the filled tank before operating the robot.

## Verified and unverified

The generator checked each mesh is connected, has two faces at every edge,
consistent outward winding, positive volume, and the stated bounding dimensions.
It also checked the tank material volume and nominal sliding clearance.
The PNG was visually inspected. OpenSCAD source was provided but not rendered
in an installed OpenSCAD application.

Actual sensor fit, printed tolerances, watertightness, adhesive strength,
splash resistance and wheel clearance remain unverified.
