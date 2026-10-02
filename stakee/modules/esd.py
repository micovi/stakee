"""ESD crates: the standard Stakee crate with a ground point, for static-dissipative filament.

The ground point is a 6.5 mm through hole in the back (+Y) wall, backed by a pad on the inside
that makes the wall 6 mm thick there and carries a flat-top hex pocket for the nut. It takes
either hardware option, both of which clamp metal against the printed wall from both sides:

- a 4 mm banana socket with an M6 threaded body (the common panel-mount type, e.g. Electro-PJP
  3240 / 3115: M6 stud, 10 mm A/F nut): collar outside, nut captive in the hex pocket, so it
  tightens from outside with a spanner on the collar. Sockets made for an 8 mm hole (e.g. PJP
  3230) fit after drilling the hole out to 8 mm; their nut then bears on the pad face.
- a 10 mm male snap stud (the ESD wrist-strap / mat-cord snap) with a screw post or centre
  hole: M3 or M4 screw through the hole, DIN 125 washer (9 mm OD) + nut in the hex pocket.

Location: centre x = GRID / 4 (10.5 mm), midway between the divider slots at x = 0 and 21 for
every footprint width, hole centre 12.75 mm above the bottom. That keeps the 18 mm pad 0.9 mm
clear of both neighbouring divider plates, below the stacking seat (pad top 20.0 mm vs
seat >= 21.0 mm), and the 14 mm outside clamp face away from clip sockets (+/-X) and label (-Y).

Stacked crates touch only through the feet resting in the lip. Printed-surface to
printed-surface contact resistance is high and unpredictable, so do not count on a stack
grounding itself: give every crate its own lead, or chain the jacks with banana leads.
"""

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Box,
    Circle,
    Cylinder,
    Part,
    Plane,
    Polygon,
    Pos,
    RectangleRounded,
    RegularPolygon,
    Rot,
    extrude,
)

from stakee.core import (
    CLIP_SOCKET_INSET,
    DIVIDER_SLOT_DEPTH,
    DIVIDER_THICKNESS,
    FLOOR_Z,
    GRID,
    HEIGHT_UNIT,
    SEAT_DEPTH,
    WALL,
    BoxSize,
    clip_socket_cuts,
    divider_slot_positions,
    label_recess,
    label_z,
    lip_pocket,
    make_box,
)
from stakee.export import PartInfo, save

MODULE = "esd"

SIZES = (BoxSize(2, 2, 3), BoxSize(2, 2, 6), BoxSize(3, 2, 6))

GROUND_ALONG = GRID / 4  # midway between divider slots at 0 and GRID / 2
GROUND_Z = 12.75  # hole centre; same on every height so jumper leads are predictable
HOLE_D = 6.5  # M6 banana-socket thread + 0.5 mm; teardrop roof for printing upright
NUT_AF = 10.3  # M6 nut is 10 mm across flats
NUT_POCKET = 3.0  # leaves 3 mm of clamped wall between collar and nut
PAD_W = 18.0  # along the wall
PAD_T = 4.0  # inward from the inner wall face: 6 mm total at the hole
PAD_BELOW = GROUND_Z - FLOOR_Z + 0.5  # pad starts 0.5 mm inside the floor
PAD_ABOVE = 7.25  # pad top at 20.0, below the 21.0 mm seat of the lowest (h = 3) crate
PAD_RADIUS = 2.0
FLANGE_D = 14.0  # outside clamp face: banana collar / snap base / washer, plus margin
MIN_H = 3

_MIN_Z = (Align.CENTER, Align.CENTER, Align.MIN)
_ROTATION = {"+Y": 0.0, "-X": 90.0, "-Y": 180.0, "+X": -90.0}


@dataclass(frozen=True)
class GroundPoint:
    """Ground hole placement: wall ("+Y", "+X", "-Y", "-X"), offset along it, centre height."""

    wall: str = "+Y"
    along: float = GROUND_ALONG
    z: float = GROUND_Z


def _inner_half(size: BoxSize, wall: str) -> float:
    cav_w, cav_d, _ = size.cavity
    return cav_d / 2 if wall in ("+Y", "-Y") else cav_w / 2


def _on_wall(point: GroundPoint, part: Part) -> Part:
    """Rotate a part modelled on the +Y wall onto the point's wall."""
    return Rot(0, 0, _ROTATION[point.wall]) * part


def _y_prism(profile, along: float, y0: float, y1: float, z: float) -> Part:
    """Extrude an (x, z) profile through y0..y1 and centre it at (along, z)."""
    prism = extrude(Plane.XZ * profile, amount=abs(y1 - y0) / 2, both=True)
    return Pos(along, (y0 + y1) / 2, z) * prism


def ground_pad(size: BoxSize, point: GroundPoint) -> Part:
    """Inside thickening of the wall around the ground hole (rises from the floor)."""
    inner = _inner_half(size, point.wall)
    depth = PAD_T + WALL - 0.5
    pad = Pos(point.along, inner - PAD_T + depth / 2, point.z - PAD_BELOW) * extrude(
        RectangleRounded(PAD_W, depth, PAD_RADIUS), amount=PAD_BELOW + PAD_ABOVE
    )
    return _on_wall(point, pad)


def ground_cuts(size: BoxSize, point: GroundPoint) -> Part:
    """Teardrop through hole plus the flat-top hex nut pocket on the pad's inner face."""
    inner = _inner_half(size, point.wall)
    pad_face = inner - PAD_T
    r = HOLE_D / 2
    c = r * math.cos(math.radians(45))
    teardrop = Circle(r) + Polygon((-c, c), (0, r * math.sqrt(2)), (c, c))
    hole = _y_prism(teardrop, point.along, pad_face - 1, inner + WALL + 1, point.z)
    hexagon = RegularPolygon(NUT_AF / 2, 6, major_radius=False)
    pocket = _y_prism(hexagon, point.along, pad_face - 1, pad_face + NUT_POCKET, point.z)
    return _on_wall(point, hole + pocket)


def ground_keepout(size: BoxSize, point: GroundPoint) -> Part:
    """Everything the ground point occupies: pad, wall under the clamp face, the hole."""
    outer = _inner_half(size, point.wall) + WALL
    span = WALL + 0.5
    flange = Pos(point.along, outer + 0.5 - span / 2, point.z) * (
        Rot(90, 0, 0) * Cylinder(FLANGE_D / 2, span)
    )
    return ground_pad(size, point) + _on_wall(point, flange)


def make_esd_crate(size: BoxSize, point: GroundPoint | None = None) -> Part:
    """A standard Stakee crate with a ground point for a banana socket or 10 mm snap stud.

    Args:
        size: crate size; h must be >= 3 so the pad stays below the stacking seat.
        point: ground hole placement; defaults to the back wall, 10.5 mm right of centre.
    """
    if size.h < MIN_H:
        raise ValueError(f"ESD crate needs h >= {MIN_H} for the ground pad, got h = {size.h}")
    point = point or GroundPoint()
    crate = make_box(size) + ground_pad(size, point)
    return crate - ground_cuts(size, point)


MATERIAL = (
    "Static-dissipative filament (PETG-ESD / ABS-ESD sold as 1e6-1e9 ohm surface resistance; "
    "aim for 1e5-1e9 ohm/sq). Conductive PLA (~1e1-1e4 ohm*cm, e.g. Protopasta 30-115) also "
    "works but is too conductive for powered boards: it can short pins and discharges a "
    "charged part fast. Plain PLA/PETG is an insulator and does nothing here."
)
PRINT_NOTES = (
    "Upright, no supports: the hole has a 45 deg teardrop roof and the hex pocket a 6 mm flat "
    "bridge. Hardened nozzle (carbon-filled filaments are abrasive); 4+ walls and 40%+ infill "
    "so the body conducts well. Ground point: M6 4 mm banana socket (collar outside, 10 mm "
    "nut in the pocket; 3 mm clamped wall, needs >= 7 mm of thread) or 10 mm male snap stud "
    "on an M3/M4 screw with washer + nut in the pocket. A toothed lock washer under the outer "
    "collar bites through the printed skin. Ground it through a 1 Mohm cord (mat/common-point "
    "cord or the bench ground point), never straight to mains earth. Check it: meter between "
    "the stud and the inside floor or a far corner; dissipative parts read 1e5-1e9 ohm, above "
    "~40 Mohm a multimeter is blind and you need a 10/100 V megohmmeter. Printed crates are "
    "not certified ESD packaging; resistance drifts with humidity, layer direction and wear."
)


def build() -> None:
    """Export every ESD crate into models/esd/."""
    for size in SIZES:
        tag = f"{size.nx}x{size.ny}x{size.h}"
        cav_w, cav_d, cav_h = size.cavity
        save(
            MODULE,
            make_esd_crate(size),
            PartInfo(
                slug=f"esd-crate-{tag}",
                title=f"ESD crate {tag}",
                blurb=(
                    f"Stakee crate ({cav_w:.0f}x{cav_d:.0f}x{cav_h:.0f} mm cavity) for "
                    "static-dissipative filament, with a ground point in the back wall for a "
                    "4 mm banana socket or a 10 mm snap stud, so it bonds to your ESD mat ground. "
                    "Stacked crates do not ground each other: lead each one, or chain the jacks."
                ),
                material=MATERIAL,
                print_notes=PRINT_NOTES,
                color="#3a3f44",
                footprint=tag,
            ),
        )


def _divider_plates(size: BoxSize) -> list[Part]:
    """A 1.2 mm plate in every divider slot, reaching 0.6 mm into the slots, floor to seat."""
    cav_w, cav_d, _ = size.cavity
    height = size.lip_top - SEAT_DEPTH - FLOOR_Z
    reach = DIVIDER_SLOT_DEPTH - 0.2
    plates = []
    for x in divider_slot_positions(size.nx):
        box = Box(DIVIDER_THICKNESS, cav_d + 2 * reach, height, align=_MIN_Z)
        plates.append(Pos(x, 0, FLOOR_Z) * box)
    for y in divider_slot_positions(size.ny):
        box = Box(cav_w + 2 * reach, DIVIDER_THICKNESS, height, align=_MIN_Z)
        plates.append(Pos(0, y, FLOOR_Z) * box)
    return plates


def _clamp_face_ratio(crate: Part, size: BoxSize, point: GroundPoint) -> float:
    """Fraction of the outside clamp ring (hole edge to 14 mm, 0.5 mm deep) that is solid."""
    outer = _inner_half(size, point.wall) + WALL
    ring = Cylinder(FLANGE_D / 2, 0.5) - Cylinder(HOLE_D / 2 * math.sqrt(2) + 0.1, 0.5)
    ring = _on_wall(point, Pos(point.along, outer - 0.25, point.z) * (Rot(90, 0, 0) * ring))
    return (crate & ring).volume / ring.volume


def _hardware(size: BoxSize, point: GroundPoint) -> Part:
    """An M6 thread (6.0 mm) through wall and pad, plus a 10 mm A/F x 3 mm nut in the pocket."""
    inner = _inner_half(size, point.wall)
    pad_face = inner - PAD_T
    thread = _y_prism(Circle(3.0), point.along, pad_face - 2, inner + WALL + 2, point.z)
    nut = _y_prism(
        RegularPolygon(5.0, 6, major_radius=False), point.along, pad_face, pad_face + 3, point.z
    )
    return _on_wall(point, thread + nut)


def _checks(size: BoxSize, point: GroundPoint, crate: Part) -> list[tuple[str, bool, str]]:
    """Run every fit check; returns (name, passed, detail) rows."""
    keep = ground_keepout(size, point)
    plates = _divider_plates(size)
    pitch = size.h * HEIGHT_UNIT
    upper = make_box(size)
    label = label_recess(size.width, -size.depth / 2, label_z(size))
    rows = [("valid", crate.is_valid, f"is_valid={crate.is_valid}")]
    volumes = {
        "clip sockets": (keep & clip_socket_cuts(size)).volume,
        "label recess": (keep & label).volume,
        "lip pocket": (keep & lip_pocket(size)).volume,
        "divider plates vs boss": sum((keep & p).volume for p in plates),
        "divider plates vs crate": sum((crate & p).volume for p in plates),
        "stack @7h": (crate & Pos(0, 0, pitch) * upper).volume,
        "M6 thread + nut fit": (crate & _hardware(size, point)).volume,
    }
    for name, vol in volumes.items():
        rows.append((name, vol < 1e-6, f"intersection {vol:.4f} mm^3"))
    seated = (crate & Pos(0, 0, pitch - 0.05) * upper).volume
    rows.append(("stack seats (-0.05)", seated > 1e-3, f"intersection {seated:.4f} mm^3"))
    ratio = _clamp_face_ratio(crate, size, point)
    rows.append(("clamp face solid", ratio > 0.999, f"{ratio:.4f} of 14 mm ring"))
    return rows


def _print_rows(rows: list[tuple[str, bool, str]]) -> None:
    for name, ok, detail in rows:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:24s} {detail}")


def _verify_misplaced() -> bool:
    """Deliberately bad ground points: each must fail the check named next to it."""
    size = BoxSize(2, 2, 3)
    cases = (
        ("over centre divider slot", GroundPoint(along=0.0), "divider plates vs boss"),
        ("pad up into the lip", GroundPoint(z=size.lip_top - 7.0), "stack @7h"),
        (
            "on +X clip socket",
            GroundPoint("+X", along=-(size.depth / 2 - CLIP_SOCKET_INSET), z=10.0),
            "clip sockets",
        ),
        ("on front label", GroundPoint("-Y", along=0.0, z=label_z(size)), "label recess"),
    )
    all_caught = True
    for title, point, expected in cases:
        rows = _checks(size, point, make_esd_crate(size, point))
        failed = [name for name, ok, _ in rows if not ok]
        caught = expected in failed
        all_caught &= caught
        print(f"MISPLACED {title}: {'CAUGHT' if caught else 'MISSED'} (failed: {failed})")
    return all_caught


def verify() -> bool:
    """Check every exported crate, then prove the checks catch misplaced ground points."""
    passed = True
    for size in SIZES:
        crate = make_esd_crate(size)
        bb = crate.bounding_box().size
        tag = f"{size.nx}x{size.ny}x{size.h}"
        print(f"esd-crate-{tag}  {bb.X:.2f} x {bb.Y:.2f} x {bb.Z:.2f} mm")
        rows = _checks(size, GroundPoint(), crate)
        _print_rows(rows)
        passed &= all(ok for _, ok, _ in rows)
    passed &= _verify_misplaced()
    print("ALL CHECKS PASSED" if passed else "SOME CHECKS FAILED")
    return passed


if __name__ == "__main__":
    build()
    if not verify():
        raise SystemExit("esd verification failed")
