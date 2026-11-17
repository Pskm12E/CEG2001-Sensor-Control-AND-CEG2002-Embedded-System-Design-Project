# Zumo load and fit assessment — 17 November 2026

**Current CAD prototype:** actual STL/source files are now in [cad/](cad/README.md).
The printed geometry has a full-solid PETG estimate of **269.35 g**, separate
from water, bank, hardware and electronics. Its default printed envelope is
164.5 x 184.5 x 142.2 mm. Digital collision checks passed against the explicit
reference/allowance geometry; no physical fit, load or driving result is claimed.
This supersedes the earlier unassigned CAD mass and main-carrier-only footprint.

**Current packaging update:** v5 added power-bank connector space; v6 also
reserves the complete cable and a separate Uno USB-B plug/bend pocket. The
main carrier target remains 155 x 135 mm, but the complete outer case may need
a local USB-cover extension; see [the enclosure guide](README.md) and
[v6 dimension study](component-dimensions-v6.json). This does not verify load
capacity or change the hypothetical status of the mass example below.

## What can be concluded

The intended 100 mL water quantity is approximately **100 g**, creating about
**0.98 N** of static gravitational force. That is the water alone. It does not
include the empty bottle, cradle, lid, pump, tubing or any electronics.

The complete build's ability to carry and manoeuvre with that water is
**unverified**. Dimensions alone do not provide component mass, motor torque,
track friction, battery performance, centre-of-mass height, fastener strength
or printed-part strength.

Pololu's [manufacturer support response](https://forum.pololu.com/t/max-load-acceptable-by-a-zumo-robot/23183)
does not give a specific Zumo weight limit and cites roughly 275 g for a Zumo
with four AA NiMH cells. That is context, not a weighing of this user's
Uno-equipped variant. The [product motor tables](https://www.pololu.com/product/1418)
use a 500 g total chassis test condition. It is not a 500 g payload specification
or a universal pass/fail threshold.

## Illustrative mass example, not measured

| Term | Example mass |
| --- | ---: |
| Reference Zumo with batteries | 275 g |
| Hypothetical power-bank mass | 200 g |
| Intended water | 100 g |
| Example subtotal | **575 g** |

The bank's 200 g is an explicit example, not a published or measured PB-Y91
weight. This subtotal excludes the other boards, bottle, pump, printed parts,
camera, sensors, breadboard, extra wires and fasteners. It therefore cannot be
reported as the actual loaded mass or as proof that the robot can/cannot drive.

Use this actual mass sum, avoiding double-counting the Uno and normal batteries:

ready-to-drive Zumo + bank + added MSP430/ESP32/camera/sensors/breadboard +
pump/driver + empty bottle/lid/holder + water + printed carrier/case +
extra cables/tubing/fasteners.

## Placement study

The current proposed carrier is **155 wide x 135 long mm**, surrounding an approximately
98 x 98 mm user reference base outline. The bank is low on the right and the
bottle low on the left; the lighter boards are above the bank.

At proposed x locations -42.5 mm for the water and +36.5 mm for the bank, an
illustrative 275 g centred base and 200 g bank give a three-item horizontal
centroid of about **5.3 mm right with 100 g water**, or **15.4 mm right without
the water**. These calculations exclude all other masses and all z coordinates,
and use an assumed centred base. They are not a measured stability margin.

The actual ground-contact polygon and complete centre of mass must be measured.
The 98 x 98 outline is not the track contact patch. Water slosh, braking,
skid turns and cable/pump forces can change behaviour; a static projection alone
does not establish stability.

For an ideal straight cylinder with **60 mm internal diameter**, 100 mL would
make a water column about **35 mm** high, with its centroid about **18 mm**
above the inner bottom. The supplied 60 mm is an approximate external diameter
and a cut bottle may taper, so this calculation explains why a low cradle helps;
it is not a fill-line calibration. Put a measured 100 mL into the actual bottle.

## What the packaging calculation actually checks

The current saved JSON checks that:
- the bank's bare body rectangle lies inside the proposed dry-bay outline;
- the supplied MSP430 and FireBeetle PCB rectangles fit on the upper layer;
- those two PCB rectangles do not overlap, with a 4 mm proposed gap.
- the v5 empty USB-bay rectangle lies inside the revised dry-bay outline and
  starts at the power bank's proposed rear port plane, with 50 mm clear depth.

The bank is on a different layer from the boards. These checks do not include
the actual connector coordinates, plug bodies, cable bends, header heights,
standoffs, breadboard, pump, shield switch/USB openings or mounting-hole positions.
The breadboard's previous 47 x 35 allowance remains an allowance only.
No assembled-height or complete-assembly fit claim follows from the checks.

## Next physical checks

1. **Weigh and identify:** record the ready-to-drive base with its normal
   batteries, bank, extra components and prototype parts separately. Identify
   the motor gear ratio/variant and available motor/driver current specifications.
2. **Check retention and structure:** assemble the measured frame without water,
   ensure load bypasses electronic components and all tracks/switches/ports stay
   clear. Use supported equivalent ballast for the bottle load first; inspect
   the cup, ribs, joints and chassis fixings for slip or excessive deflection.
   No working-load rating is assigned by this suggestion.
3. **Test the actual flat track in stages:** check empty bottle first, then
   measured 50 mL and 100 mL, at low speed through straight travel, stopping and
   the route's S-turns. Check track clearance, steering consistency, resets,
   current/temperature within component ratings, cup movement and water containment.
   Stop if the carrier shifts or the drive struggles. Record the results.
4. **Review the fit:** carrier protrusions must clear both plants and the dock.
   Keep direct access to the original rear switch even with the bottle installed.

No actuator commands, hardware assembly, loaded drive or water test were
performed during this analysis. If the actual complete build is too heavy for
reliable turns, the remaining choices are reducing carried water/other mass
or using a larger base; a stronger-looking cover alone cannot resolve motor load.
