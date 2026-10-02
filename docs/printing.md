# Printing

Which filament to use for each family, how to calibrate the fit for your printer, and how to fit magnets and ground ESD crates.

Every part in [`models/`](../models/README.md) carries its own material and print notes in `models/<family>/manifest.json`; the family pages show them. This page collects them.

## Materials

| Family | Parts | Material | Notes |
| --- | --- | --- | --- |
| [Crates](../models/crates/README.md) | Crates | PLA or PETG | Upright, no supports, 3 walls, 15% infill. |
| | Caps | PETG | Upside down (plate on the bed), no supports. |
| [Dividers](../models/dividers/README.md) | Rails | PLA | Flat, thick-end side up, no supports, 100% infill. |
| | Hook plates, bridges | PETG | The hooks flex better in PETG. Same orientation as the rails. |
| [Inserts](../models/inserts/README.md) | Dev-board dock, parts grid | PLA or PETG | |
| | Solder station | PETG or ASA | It lives next to the iron. Never rest the hot tip on any print. |
| [Bag Library](../models/baglib/README.md) | Crates | PETG | PETG-ESD if you also keep unbagged ICs in it. |
| | Caps, followers | PETG | |
| | Index cards | PLA or PETG | Colour change at 1.2 mm for the text, 100% infill. |
| [Drawer cabinet](../models/drawers/README.md) | Sleeves | PLA or PETG | The lintel bridges 79.5 mm: print a bridge test first, 100% part cooling for bridges. |
| | Drawers | PETG or PLA | PETG for the flexing detent tongues. 4 walls. |
| | Rails | PLA | Flat, 100% infill. |
| [Pocket box](../models/pocket/README.md) | Base | PETG | The latch tab flexes; PLA tabs crack. 4 walls. |
| | Lid | PETG | Hinge pin: 82.5 mm of 1.75 mm filament. |
| | Divider | PLA or PETG | |
| [Carry kit](../models/kit/README.md) | Stack clip | PETG | PLA is too brittle for the hooks. On its side, 100% infill, thin walls / Arachne on. |
| | Tote handle caps | PETG | On the front face (-Y on the bed). |
| | NFC label cap | PETG or PLA | Takes an NTAG215 sticker under the label tile. |
| | NFC label tile | PLA or PETG, two colours | Filament swap at z = 1.6 mm. |
| | Tool rack cap | PETG, or TPU 95A | TPU for a softer, rattle-free rack. |
| [Magnetic tray](../models/magtray/README.md) | Trays | PLA or PETG | Plus 10 × 2 mm N52 disc magnets, inserted at a print pause. |
| [ESD crates](../models/esd/README.md) | Crates | Static-dissipative filament | See [ESD](#esd). Hardened nozzle, 4+ walls, 40%+ infill. |
| [Wire dispenser](../models/wirespool/README.md) | Crate | PLA or PETG | |
| | Cradle frame | PETG (PLA ok) | |
| | Axle | PETG | Needs a bed at least 165 mm long, or print diagonally. |
| | Spool washers | PETG | |
| [Wall rail](../models/wallrail/README.md) | Shelves | PETG or ASA | Load-bearing; PLA creeps. On its side, 4 walls, 25% gyroid. Design load 2 kg. |
| | Wall cleats | PETG or ASA | Use at least 2 screws with wall anchors. |
| [Calibration](../models/calibration/README.md) | All | The filament of the parts you are calibrating | Same settings as the real parts. |

## Calibration

The fit of a crate on the crate below, and of a divider in its slot, depends on your printer. The [Calibration](../models/calibration/README.md) family measures both. Source: [`stakee/modules/calibration.py`](../stakee/modules/calibration.py).

| Part | What it is |
| --- | --- |
| `lip-coupon-15`, `lip-coupon-25`, `lip-coupon-35` | 1x1x2 crates with a stacking lip cut at 0.15, 0.25 and 0.35 mm clearance. The value in hundredths of a mm is debossed on the front ("25" = 0.25 mm). No magnets, slots, sockets or label; the floor has a window to save filament. |
| `lip-probe` | A plain default 1x1x2 crate. Its feet are the gauge. It keeps working as a crate. |
| `slot-strip` | An L of crate wall with one divider slot in an X wall and one in a Y wall. |
| `slot-samples` | A comb of divider ends, 1.2, 1.4, 1.5 and 1.55 mm thick, each labelled. |

### Print them

- Lip coupons and probe: the filament, nozzle, layer height and elephant-foot compensation of your crates. Upright, no supports, 2 walls, 15% infill.
- Slot strip: floor on the bed, no supports, the settings of your crates.
- Slot samples: the filament of your dividers, flat, labels up, 100% infill. At 0.2 mm layers the slicer rounds 1.5 and 1.55 mm to whole layers; use 0.1 mm layers or less to see the difference.

### Lip clearance

1. Lower the probe onto a coupon by hand, then let go. It should drop the last few mm on its own and rest flat, with a 0.75 mm shadow gap all round.
2. Try every coupon. Pick the tightest one that the probe drops into by its own weight and that does not rattle when you shake the pair.
3. If even the loosest coupon binds, fix elephant foot first. If the tightest one rattles, print coupons with smaller values (0.15 mm is the lower limit).
4. Use the value:
   - For crates from the CLI: `uv run stakee box 2x2x6 --lip-clearance 0.15` (use your value).
   - For the library in `models/`: set `LIP_CLEARANCE` in [`stakee/core.py`](../stakee/core.py) and run `uv run stakee-build`. This also changes the CLI default.

The clearance is cut into the lip, so it sets the fit of whatever stacks on that crate. The stack pitch stays at `7 × H` for any clearance ([The system](system.md#lip)).

### Divider fit

1. Press the tip edge of each finger into both slots of the strip.
2. The 1.2 mm plate must slide in freely. If it does not, your slots print narrow.
3. Pick the thickest end that goes in by hand in both slots and stays put when you turn the strip upside down.
4. Set `END_THICKNESS` in [`stakee/modules/dividers.py`](../stakee/modules/dividers.py) to that value (now 1.5 mm) and rebuild the dividers with `uv run stakee-build --only dividers`. There is no CLI option for it.

### Other values

```bash
uv run python -m stakee.modules.calibration --clearances 0.2 0.3
uv run python -m stakee.modules.calibration --samples 1.2 1.45 1.5
```

- Clearances must be between 0.15 and 0.99 mm and give distinct labels (0.01 mm steps).
- The command verifies, then writes into `models/calibration/`. It does not remove the default coupons and does not rewrite the README pages. Run `uv run stakee-build --docs-only` to update the pages, or `uv run stakee-build --only calibration` to go back to the defaults.

## Magnets

| Where | Magnet | How |
| --- | --- | --- |
| Feet of every crate-based part: crates, ESD and Bag Library crates, the wire dispenser, drawer sleeves, pocket box bases | 6 × 2 mm discs, 4 per grid cell | Glue into the 6.5 × 2.4 mm pockets under the feet after printing. Optional. `stakee box --no-magnets` removes the pockets. |
| [Magnetic tray](../models/magtray/README.md) | 10 × 2 mm N52 discs, one per compartment | Pause the print at z = 3.0 mm, drop the magnets into the pockets, resume. A 0.6 mm ceiling prints over them. Polarity does not matter. |

## ESD

The [ESD crates](../models/esd/README.md) are standard crates with a ground point in the back wall: a 6.5 mm hole for an M6 4 mm banana socket, or a 10 mm snap stud on an M3/M4 screw.

- **Filament.** Use static-dissipative filament (PETG-ESD or ABS-ESD, sold as 1e6–1e9 Ω surface resistance). Plain PLA or PETG is an insulator and does nothing here. Conductive PLA works but is too conductive for powered boards: it can short pins.
- **Grounding.** Ground each crate through a 1 MΩ cord (mat or common-point cord, or the bench ground point), never straight to mains earth.
- **Stacks.** Stacked crates touch only through the feet in the lip. Do not count on a stack grounding itself: give every crate its own lead, or chain the sockets with banana leads.
- **Check.** Measure between the ground point and the inside floor or a far corner. Dissipative parts read 1e5–1e9 Ω. Above about 40 MΩ a multimeter cannot measure; use a 10/100 V megohmmeter.

**Printed crates are not certified ESD packaging.** Their resistance drifts with humidity, layer direction and wear. Full notes are on the [ESD crates](../models/esd/README.md) page.
