# The system

Every Stakee part follows one geometry contract, defined in `stakee/core.py`, so any part stacks on any crate with the same footprint.

Source: [`stakee/core.py`](../stakee/core.py). All values below are read from it.

## Coordinates

- X is width, Y is depth, Z is up.
- The front face is -Y. The label recess is on the front.
- Every part is centered on the XY origin, with its lowest point at z = 0.

## Grid and height units

| Unit | Size | Used for |
| --- | --- | --- |
| Grid unit | 42 mm | Footprint, `NX` along X and `NY` along Y |
| Height unit | 7 mm | Crate height `H` and the stack pitch |

A crate is named `NXxNYxH`, for example `2x2x6`: 84 × 84 mm of grid, 6 × 7 = 42 mm stack pitch.

## Outer size and cavity

| Dimension | Formula | 2x2x6 |
| --- | --- | --- |
| Outer width | `42 × NX − 0.5` | 83.5 mm |
| Outer depth | `42 × NY − 0.5` | 83.5 mm |
| Outer height (lip top) | `7 × H + 4` | 46 mm |
| Stack pitch | `7 × H` | 42 mm |
| Cavity width | `42 × NX − 4.5` | 79.5 mm |
| Cavity depth | `42 × NY − 4.5` | 79.5 mm |
| Cavity height | `7 × H − 5.5` | 36.5 mm |

- The outline is 0.25 mm (`GAP`) inside the grid on every side, so neighbouring crates do not touch.
- The outer corners have a 3.75 mm radius. Walls are 2 mm thick.
- The floor top is at z = 5.5 mm. The cavity height is measured from there to the stacking seat, 4 mm below the lip top. Anything inside a crate must stay below the seat, or the crate above will not seat.

Computed with `uv run stakee list` and `BoxSize` in `core.py`:

| Size | Outer (W × D × H, mm) | Pitch (mm) | Cavity (W × D × H, mm) | Label recess width (mm) |
| --- | --- | --- | --- | --- |
| 1x1x2 | 41.5 × 41.5 × 18 | 14 | 37.5 × 37.5 × 8.5 | none (H < 3) |
| 1x1x3 | 41.5 × 41.5 × 25 | 21 | 37.5 × 37.5 × 15.5 | 25.5 |
| 2x1x3 | 83.5 × 41.5 × 25 | 21 | 79.5 × 37.5 × 15.5 | 60 |
| 2x2x3 | 83.5 × 83.5 × 25 | 21 | 79.5 × 79.5 × 15.5 | 60 |
| 2x2x6 | 83.5 × 83.5 × 46 | 42 | 79.5 × 79.5 × 36.5 | 60 |
| 3x2x6 | 125.5 × 83.5 × 46 | 42 | 121.5 × 79.5 × 36.5 | 60 |
| 4x2x6 | 167.5 × 83.5 × 46 | 42 | 163.5 × 79.5 × 36.5 | 60 |

## Stacking

Every crate is the lid of the crate below.

### Feet

Each grid cell has its own foot, 41.5 × 41.5 mm at the top. The foot uses the Gridfinity profile, given as (height, inset from the cell outline):

| z (mm) | Inset (mm) | Section |
| --- | --- | --- |
| 0 | 2.95 | Bottom |
| 0.8 | 2.15 | 45° chamfer |
| 2.6 | 2.15 | Vertical face |
| 4.75 | 0 | 45° chamfer up to the full outline |

The feet are 4.75 mm tall (`FOOT_HEIGHT`). Because they use the Gridfinity profile, crates also sit on Gridfinity baseplates.

### Lip

The top of every crate is a stacking lip, 4 mm above the nominal height `7 × H` (`LIP_ABOVE_NOMINAL`). The lip is cut with the shape of the feet, grown by the lip clearance:

- The cut is the foot envelope, lifted by the clearance and widened by it on every side.
- On the 45° chamfers these two offsets cancel. The feet of an upper crate seat on the chamfers 4 mm below the lip top (`SEAT_DEPTH`), which is exactly `7 × H`.
- The clearance only changes the play on the vertical faces of the feet.
- The body of the upper crate starts at 4.75 mm, so there is a 0.75 mm shadow gap between the two bodies.

The result: a crate of height `H` puts the next part at exactly `7 × H` mm, whatever the clearance. The `verify()` of the [Crates](../models/crates/README.md) family checks this with the real solids. It places a box and a cap at `7 × H` (zero overlap) and 0.05 mm lower (they collide), so the parts seat and do not hover.

### Lip clearance

| | Value |
| --- | --- |
| Default (`LIP_CLEARANCE`) | 0.25 mm |
| Allowed by the geometry | 0.15 mm up to, but not including, 1.0 mm |

Below 0.15 mm the cavity wall, not the lip, sets the play: the vertical foot face sits 2.15 mm in from the outline and the wall is 2.0 mm thick. Set the clearance for your printer with the [calibration coupons](printing.md#calibration) and `stakee box --lip-clearance` ([CLI](cli.md#--lip-clearance-mm)).

### Caps

A cap (`make_cap`) is one foot the size of the whole footprint, hollowed out from below with a 1.6 mm shell, under a 2.4 mm top plate. It is 7.15 mm tall and seats in the lip of any crate with the same footprint. Its top is flat, so it ends a stack. The label recess is on top.

## Magnets

| Property | Value |
| --- | --- |
| Pocket | 6.5 mm diameter, 2.4 mm deep, open at the bottom of the feet |
| Position | ±13 mm from each cell center on both axes |
| Count | 4 per grid cell (16 on a 2x2 crate) |
| Magnet | 6 × 2 mm disc, glued in |

`stakee box --no-magnets` omits the pockets.

## Divider slots

| Property | Value |
| --- | --- |
| Slot | 1.6 mm wide, 0.8 mm deep into the wall |
| Pitch | 21 mm (half a grid unit), on all four inner walls |
| Positions | `k × 21 − n × 21` mm for `k = 1 … 2n − 1`, along a side `n` units long |
| Height | From the floor (z = 5.5 mm) up through the lip, so a plate drops straight in |
| Plate | 1.2 mm thick (`DIVIDER_THICKNESS`) |

A 2-unit side has slots at −21, 0 and 21 mm; a 3-unit side at −42, −21, 0, 21 and 42 mm. A side with `2n − 1` slots holds up to `2n` compartments. The [Dividers](../models/dividers/README.md) family and `stakee box --dividers` use these slots.

## Label recess

| Property | Value |
| --- | --- |
| Face | Front (-Y) of crates; top of caps |
| Size | `min(width − 16, 60)` mm wide, 12 mm tall, 0.6 mm deep |
| Height on a crate | Top edge 1.5 mm below the stacking seat, so the center is at `7 × H − 7.5` mm |
| Minimum crate height | 3 units (`LABEL_MIN_HEIGHT_UNITS`); 2-unit crates have no recess |

`stakee box --label` and `stakee cap --label` export a press-fit tile for it ([CLI](cli.md#--label-text)).

## Clip sockets

Crates have eight L-shaped bayonet sockets on the side (+X and -X) faces, for the stack clip in the [Carry kit](../models/kit/README.md).

| Property | Value |
| --- | --- |
| Window | 7.4 mm long along the face, 1.6 mm tall, 1.4 mm deep |
| Hidden leg | 5.0 mm long, behind a 0.6 mm skin; the clip's hook sits in it |
| Footprint along Y | 12.4 mm |
| Position along Y | Centered 12 mm in from the front and back faces |
| Heights | Centered 2 mm below the lip top, and 6.5 mm above the bottom |

A clip nub enters the window, then the clip slides along Y so its hook is behind the skin and cannot be pulled straight off. On the +X face the leg runs toward +Y; on the -X face toward -Y.

The lip sockets of a lower crate sit 2 mm above the seam (`7 × H`), the base sockets of the upper crate 6.5 mm above it. This holds for every height, so one clip fits every seam. `stakee box --no-sockets` omits the sockets.

## Constants

| Constant | Value | Meaning |
| --- | --- | --- |
| `GRID` | 42.0 mm | Footprint unit |
| `HEIGHT_UNIT` | 7.0 mm | Height unit and stack pitch |
| `GAP` | 0.25 mm | Clearance per side between neighbouring cells |
| `OUTER_RADIUS` | 3.75 mm | Outer corner radius |
| `WALL` | 2.0 mm | Wall thickness |
| `FLOOR_Z` | 5.5 mm | Top of the solid floor |
| `FOOT_HEIGHT` | 4.75 mm | Height of the feet |
| `FOOT_STATIONS` | (0, 2.95), (0.8, 2.15), (2.6, 2.15), (4.75, 0) | Foot profile as (z, inset) in mm |
| `LIP_CLEARANCE` | 0.25 mm | Default foot/lip clearance |
| `LIP_ABOVE_NOMINAL` | 4.0 mm | Lip top above `7 × H` |
| `SEAT_DEPTH` | 4.0 mm | How far feet sink below the lip top |
| `MAGNET_DIAMETER` | 6.5 mm | Magnet pocket diameter |
| `MAGNET_DEPTH` | 2.4 mm | Magnet pocket depth |
| `MAGNET_OFFSET` | 13.0 mm | Pocket offset from the cell center, both axes |
| `DIVIDER_SLOT_WIDTH` | 1.6 mm | Slot width |
| `DIVIDER_SLOT_DEPTH` | 0.8 mm | Slot depth into the wall |
| `DIVIDER_THICKNESS` | 1.2 mm | Divider plate thickness |
| `CLIP_SOCKET_OPENING` | 7.4 mm | Socket window length |
| `CLIP_SOCKET_LEG` | 5.0 mm | Hidden leg length |
| `CLIP_SOCKET_HEIGHT` | 1.6 mm | Socket height |
| `CLIP_SOCKET_DEPTH` | 1.4 mm | Socket depth into the wall |
| `CLIP_SOCKET_SKIN` | 0.6 mm | Wall in front of the leg |
| `CLIP_SOCKET_INSET` | 12.0 mm | Socket center from the front/back face |
| `CLIP_SOCKET_LIP_Z` | 2.0 mm | Lip socket center below the lip top |
| `CLIP_SOCKET_BASE_Z` | 6.5 mm | Base socket center above the bottom |
| `LABEL_HEIGHT` | 12.0 mm | Label recess height |
| `LABEL_DEPTH` | 0.6 mm | Label recess depth |
| `LABEL_MAX_WIDTH` | 60.0 mm | Label recess maximum width |
| `LABEL_MIN_HEIGHT_UNITS` | 3 | Lowest crate with a label recess |
| `LABEL_TOP_OFFSET` | 1.5 mm | Label recess top below the stacking seat |
| `CAP_PLATE` | 2.4 mm | Cap top plate thickness |
| `CAP_SHELL` | 1.6 mm | Cap foot shell thickness |

## Building on the contract

Families build their parts from these functions in `core.py`:

| Function | Returns |
| --- | --- |
| `BoxSize(nx, ny, h)` | Size with `width`, `depth`, `lip_top` and `cavity` |
| `make_box(size, magnets, dividers, clip_sockets, label, lip_clearance)` | A complete crate |
| `make_cap(nx, ny, label)` | A cap |
| `feet(nx, ny, magnets)` | The feet alone |
| `lip_pocket(size, clearance)` | The cut that forms a stacking lip |
| `divider_slot_positions(n)` | Slot centers along a side `n` units long |
| `clip_socket_positions(size)`, `clip_socket_cuts(size, lip, base)` | Socket centers and cuts |
| `label_width(width)`, `label_z(size)`, `label_recess(width, front_y, z_center)` | Label recess size, height and cut |

See [Adding a family](adding-a-family.md).
