# Zumo enclosure: actual printable prototype

This package contains real STL solids, editable source, a CAD assembly and a
mesh-derived preview. The Uno stays attached to the Zumo. Its back-soldered
wires stay in place; this design makes no electrical or pin changes.

**Print the small fit templates and mounting feet first.** The user's actual
mount spacing, fitted-board height, USB socket coordinates and motor variant
are unknown. The complete enclosure is a fit-check prototype, not a verified
final fit or a rated water-carrying assembly.

## Files

- `exports/*.stl`: 22 separate models, already oriented for printing in mm.
  Quantities are in `PRINT_MANIFEST.md`; electronics and the bottle are not STLs.
- `parameters.json` and `build_enclosure.py`: editable dimensional source.
- `zumo_enclosure.scad`: generated CSG source. Open in OpenSCAD for an assembly;
  set `mode="print"` and `part_name` to a manifest name for an individual part.
  Edit JSON and regenerate for dimensional changes; SCAD is a generated snapshot.
- `assembly-reference.glb`: inspection model with clearly named reference
  electronics, tracks, blade, bottle and water. The GLB converts mm to metres
  as required by glTF; it is a viewing reference, not a manufacturing exchange file.
- `cad-preview.png`: assembled and exploded views of these actual meshes.
- `validation.json`: mesh checks, bounds, assumptions and collision results.

## What mounts where

Four separate feet use the existing chassis/shield fixing positions. Offset
posts carry the common deck around the fitted Uno. Do not drive an M3 screw
into an original Zumo chassis hole. The original fixing thread is #2-56 in the
[Pololu assembly instructions](https://www.pololu.com/docs/0J57/2.b).
The feet have a separate M3 captive-nut interface for the deck.

The nominal mounting pattern is 55 mm across the front, 50 mm across the rear
and 63 mm between rows. It comes from the
[Pololu Shield v1.2 dimension drawing](https://www.pololu.com/file/0J1344/zumo-shield-v1.2-dimensions.pdf)
and [drill DXF](https://www.pololu.com/file/0J914/zum01c01-drill.dxf), not a
measurement of this robot. Short slots accommodate small differences only.
The rear-left foot follows an L-shaped path around the USB-B pocket.

The bottle sits on the left. The bank lies flat on the right, on four 4 mm
printed pads plus 1 mm soft pads. Two purchased 15 mm straps thread through
raised eyes and run under the bank inside the case. They do not run between
the case and carrier. The bank's plugged-in port faces the rear plug bay.
Check the integral cable roots and folded cables against the real bank.

A removable slotted tray holds the MSP430 and FireBeetle above the bank using
movable edge clips. Use only component-free PCB edges; no board holes are
invented and no PCB drilling is required. A small accessory tray hangs beneath
the lid at the rear. Its 56.8 x 40.8 x 10.4 mm interior is an allowance, not a
measured fit for the user's breadboard.

The camera and nozzle share a fixed right-facing plate. The lens opening is
above the nozzle slot; both axes point in the same direction. Their actual
mounts are unmeasured, so the plate uses universal strap slots. There is no
servo. Aim with the robot and calibrate the camera-to-spray offset. A removable
front sensor frame also uses universal slots rather than a claimed sensor
hole pattern. Keep the existing blade and underside line sensors clear.

## Hidden USB route and original switch

One continuous cable runs from the bank's USB output, through the internal
plug bay and rear chute, across a covered rear duct, then into the USB-B socket
of the Uno already on the chassis. Signal wires can share the remaining duct
space if their insulation and cable bends fit. Do not pull the solder joints.

The bank bay reserves **70 W x 50 D x 30 H mm** from its assumed rear port face.
The Uno pod has **30 mm clear width, 30 mm clear height** and approximately
**56.8 mm usable depth behind the assumed socket mouth**. These are design
allowances, not measured connector envelopes or USB cable bend specifications.
Check the actual fully inserted plugs, adapters and relaxed cable curves.

The original rear slide switch remains on the Zumo. A **26 mm wide x 18 mm high
rear tunnel** under a raised cable crossing provides tool access at the assumed
switch location. The crossing above it has 8 mm nominal cable height. Check
the complete reach to the real switch; no case-mounted replacement switch is
included. Cable diameter and switch coordinates remain unmeasured.

The deck underside defaults to **32 mm above the fixing surface**: assumed
12 mm to the highest solder surface, 18 mm wire space and 2 mm margin. Those
numbers were not supplied as measurements. The reference PCB keep-out does
not model every component underneath the Uno. Change the parameters if any
wire, connector, pin, component, blade or track touches a foot or cover.

## First print and assembly

1. Print the three `00_fit_*` bars. Hold them above the visible fixing centres
   without pushing on the board or soldered wires. They check the two row
   spacings and the right-hand 63 mm row pitch; they are not load-bearing
   adapters or an exact hole gauge. The row-pitch bar includes the 2.5 mm
   front/rear lateral offset on that side.
2. Print the four `01_mount_*` feet and four `02_*` washers. Try each foot at
   its labelled position while leaving the Uno attached. Confirm the 63 mm row
   spacing, underside component clearance and original blade fixing stack.
   If an original screw is too short, use the same #2-56 thread with the correct
   additional engagement. Select length from the actual stack; never force it
   or bottom it in the chassis. Do not dismantle the Uno to make a wrong foot fit.
3. Fit the feet and carrier only. Check rear-switch operation, track rotation,
   front blade, line sensor view and clearance above every rear-soldered wire.
4. Fit the empty lower case and bottle cradle with captive nuts. Fit the real
   bank, pads, straps and cable; try the rear duct and removable duct cover.
   Check both plugged-in connector ends and the switch tunnel before loading.
5. Fit the controller tray, edge clips and actual boards. Check jumper/USB
   heights and screw tips, then fit the upper sleeve, accessory tray and lid.
   Fit the fixed optics/nozzle plate and optional front frame using actual
   component fasteners or soft straps.
6. Test dry and unloaded, then add 100 g of secured ballast low in the bottle
   position. Check straight motion, tight turns, stopping and dock return at
   low speed. Use water only after the bottle/hose/leak test passes separately.

## Hardware shopping/check list

Sizes below suit the nominal model; verify actual head, nut and screw lengths.
Steel hardware mass is additional to the plastic estimate.

| Joint | Suggested nominal hardware | Quantity |
| --- | --- | ---: |
| Original chassis to feet | Existing #2-56 thread; length selected from actual stack | 4 |
| Carrier to feet | M3 x 10 pan head, M3 nuts in side-loading foot pockets | 4 |
| Lower case to carrier | M3 x 8 countersunk, M3 nuts under carrier | 4 |
| Bottle cradle to carrier | M3 x 8 countersunk, M3 nuts under carrier | 2 |
| Sleeve and lid to lower-case ears | M3 x 50 pan head, M3 nuts in lower-case ears | 4 |
| Duct-cover mounting tabs to carrier | M3 x 8 pan head, M3 nuts in cover tabs | 2 |
| Duct cover to duct | M2 x 6 into 1.7 mm printed pilot holes | 4 |
| Camera/nozzle plate to lower-case bosses | M3 x 8 pan head and M3 nuts | 4 |
| Front sensor frame to carrier | M3 x 8 pan head and M3 nuts | 2 |
| PCB edge clips to tray | M3 x 8, head height at most 2 mm, nuts beneath tray | 8 |
| Accessory tray under lid | M3 x 8 pan head and M3 nuts | 4 |

Also use two 15 mm soft straps for the bottle, two for the bank, four 1 mm soft
bank pads and suitable component fasteners/soft ties. Do not put metal screw
heads against PCB components. The nominal 8 mm clip screws clear the bank by
about 1 mm at their tips; recheck this with real hardware and no excess length.

## Printing

Use **mm, 100% scale**. Import each STL without automatic resizing. PETG is a
prototype material suggestion; 0.2 mm layers and a 0.4 mm nozzle are starting
settings. The case walls are 1.2 mm, so inspect three continuous wall lines in
the slicer. Inspect every screw pocket and thin section before printing.
Filament, cooling, orientation and layer adhesion determine real strength.

Files are already rotated and placed at Z=0. The carrier prints with its roof
on the bed and the guard walls upward; the lid and bottle cap print upside
down. The camera plate prints with its flat front on the bed. Use local support
under the rear duct's switch tunnel/raised cable bridge if the printer cannot
bridge that span. Inspect supports for nut pockets and small overhangs; keep
support material out of cable space and remove it before assembly.

The supplied bottle cap is a loose splash cover with three small pilot holes.
It is not a seal or a pressure cap. Size actual hose/probe openings after the
real fittings are known. The enclosure is not waterproof; it does not isolate
a leaking bottle from the electronics. Remove the bank for charging and
inspection rather than charging a hot enclosed pack beside water.

## Weight and limits

Read the current full-solid plastic estimate in `PRINT_MANIFEST.md` (about
270 g for this revision). Actual sliced and printed mass will differ. Add the
complete Zumo, bank, boards, bottle, 100 g water, fasteners, cables, pump, tubing
and sensors to obtain total moving mass. This is a substantial payload for a
small Zumo, so **this design does not establish that it can carry the water**.
It is a physical fit prototype to weigh and test, with no load or strength
rating. Pololu's [load discussion](https://forum.pololu.com/t/max-load-acceptable-by-a-zumo-robot/23183)
does not provide a universal allowable payload for every motor configuration.

Pump, driver, actual camera/sensor/nozzle bodies and hose dimensions have not
been supplied and are not fitted CAD components. The universal brackets and
accessory space must be adapted once those parts are checked. Exact fit/load
cannot be inferred from photographs or a watertight STL check.

## Rebuild and digital validation

From this folder in PowerShell, using Python 3.14 or a compatible Python:

```powershell
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.txt
& .venv/Scripts/python.exe build_enclosure.py
```

The builder checks each exported STL after reopening it: closed manifold,
consistent winding, positive volume and one connected shell. It checks actual
default printed-part intersections, the mounted Uno PCB, reference components
and reserved USB/header envelopes. The preview uses a software depth buffer
and these meshes. The generated SCAD shares the same primitive construction;
OpenSCAD itself was not used to render or validate this package.

The JSON parameters are editable dimensions and assumptions. Offset-foot
routes, universal clips and some fastener coordinates also live in the Python
source; this is not an automatically fitting enclosure for arbitrary boards.
After edits, rebuild and inspect `validation.json`, the preview and sliced
parts before printing. Physical interference, heat, leakage, tipping, traction,
motor current and dock/track performance require checks on the real robot.
