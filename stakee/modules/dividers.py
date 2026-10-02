"""Modular dividers: interlocking rails plus short hook-on plates, all printed flat.

System:
- Rails span the whole cavity and sit in the core wall slots (every 21 mm). An X rail
  (running along X) is notched from the bottom, a Y rail from the top, so any X and Y
  rails cross like an egg crate. Rail ends are 1.5 mm thick in the 1.6 mm slot: they
  stay put but slide out by hand.
- Hook plates start in a wall slot and hang on an X rail with a hook over its top edge,
  anywhere along it. Bridges hang between two X rails.
- Hooks only go on X rails: a Y rail has notches in its top edge at every slot.

Every part is a profile in its local XZ plane, extruded through its thickness, so it
prints flat with no supports. Local Y spans [-0.75, 0.45] (plate) and [-0.75, 0.75]
(thick ends), so a part laid on its -Y face sits flat on the bed.
"""

from build123d import Align, Box, Cylinder, Part, Pos, Rot

from stakee.core import (
    DIVIDER_SLOT_DEPTH,
    DIVIDER_SLOT_WIDTH,
    DIVIDER_THICKNESS,
    FLOOR_Z,
    GAP,
    GRID,
    HEIGHT_UNIT,
    SEAT_DEPTH,
    WALL,
    BoxSize,
    divider_slot_positions,
    make_box,
)
from stakee.export import PartInfo, save

MODULE = "dividers"

INSERT = DIVIDER_SLOT_DEPTH - 0.2  # how far a plate end reaches into a slot
END_THICKNESS = 1.5  # snug in the 1.6 mm slot
END_LENGTH = 1.0
FACE_LO = -0.75  # plate faces in local Y; the thick end grows only toward +Y
FACE_HI = FACE_LO + DIVIDER_THICKNESS
HOOK_GAP = 0.15  # clearance between a hook and the rail it hangs on
HOOK_BAR = 1.2  # hook bar height above the rail top
HOOK_DROP = 5.0  # how far the hook reaches down the far face of the rail
TOP_CLEARANCE = 2.0  # rail top to the stacking seat; leaves room for the hook bar
NOTCH_PLAY = 0.2
FINGER_HOLE = 8.0
MIN_HEIGHT_FOR_HOLE = 13.0

SIZES = (BoxSize(2, 2, 3), BoxSize(2, 2, 6), BoxSize(3, 2, 6))
BOTTOM = (Align.CENTER, Align.MIN, Align.MIN)


def plate_height(size: BoxSize) -> float:
    """Height of every divider for this crate: cavity height minus the hook clearance."""
    return size.cavity[2] - TOP_CLEARANCE


def _slab(x0: float, x1: float, z0: float, z1: float, y0: float = FACE_LO, y1: float = FACE_HI):
    return Pos((x0 + x1) / 2, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=BOTTOM)


def _thick_end(x0: float, height: float) -> Part:
    return _slab(x0, x0 + END_LENGTH, 0, height, FACE_LO, FACE_LO + END_THICKNESS)


def make_rail(size: BoxSize, along_x: bool) -> Part:
    """Full-span rail for the wall slots, centered on local X, standing on z = 0.

    Args:
        size: crate the rail is for.
        along_x: True for an X rail (notched from the bottom, carries hooks),
            False for a Y rail (notched from the top).
    """
    cav_w, cav_d, _ = size.cavity
    span = cav_w if along_x else cav_d
    crossings = divider_slot_positions(size.nx if along_x else size.ny)
    height = plate_height(size)
    half = span / 2 + INSERT
    rail = _slab(-half, half, 0, height)
    rail += _thick_end(-half, height) + _thick_end(half - END_LENGTH, height)
    notch_h = height / 2 + NOTCH_PLAY
    notch_z = 0 if along_x else height - notch_h
    for x in crossings:
        rail -= _slab(
            x - DIVIDER_SLOT_WIDTH / 2,
            x + DIVIDER_SLOT_WIDTH / 2,
            notch_z - 0.01,
            notch_z + notch_h + 0.01,
            FACE_LO - 1,
            FACE_LO + END_THICKNESS + 1,
        )
    if height >= MIN_HEIGHT_FOR_HOLE:
        hole_x = crossings[0] + GRID / 4
        rail -= (
            Pos(hole_x, 0, height - FINGER_HOLE / 2 - 2.0)
            * Rot(90, 0, 0)
            * Cylinder(FINGER_HOLE / 2, 5)
        )
    return rail


def _hook(face_near: float, direction: int, height: float) -> Part:
    """Hook over a rail whose near face is at local x = face_near; direction +1 hooks toward +X."""
    bar_start = face_near - direction * (HOOK_GAP + 1.0)
    drop_start = face_near + direction * (HOOK_GAP + DIVIDER_THICKNESS + HOOK_GAP)
    drop_end = drop_start + direction * DIVIDER_THICKNESS
    bar = _slab(min(bar_start, drop_end), max(bar_start, drop_end), height, height + HOOK_BAR)
    drop = _slab(
        min(drop_start, drop_end), max(drop_start, drop_end), height - HOOK_DROP, height + HOOK_BAR
    )
    return bar + drop


def make_wall_hook(size: BoxSize, slots_from_wall: int) -> Part:
    """Plate from a wall slot (local x = 0 is the cavity wall) to an X rail, hooked over it.

    Args:
        size: crate the plate is for.
        slots_from_wall: which slot the rail sits in, counting 1, 2, ... from this wall.
    """
    height = plate_height(size)
    rail_center = rail_center_from_wall(slots_from_wall)
    face_near = rail_center + FACE_LO
    plate = _slab(-INSERT, face_near - HOOK_GAP, 0, height) + _thick_end(-INSERT, height)
    return plate + _hook(face_near, +1, height)


def make_bridge(size: BoxSize, slots_apart: int) -> Part:
    """Plate between X rails ``slots_apart`` slots apart; local x = 0 is the first rail."""
    height = plate_height(size)
    pitch = slots_apart * GRID / 2
    first_far = FACE_HI
    second_near = pitch + FACE_LO
    plate = _slab(first_far + HOOK_GAP, second_near - HOOK_GAP, 0, height)
    plate += _hook(second_near, +1, height)
    plate += _hook(first_far, -1, height)
    return plate


def rail_center_from_wall(slots_from_wall: int) -> float:
    """Distance from the cavity wall to the center of slot ``slots_from_wall`` (1, 2, ...)."""
    return slots_from_wall * GRID / 2 - (GAP + WALL)


def _info(slug: str, title: str, blurb: str, size: BoxSize, color: str) -> PartInfo:
    return PartInfo(
        slug=slug,
        title=title,
        blurb=blurb,
        material="PLA (rails) · PETG (hook plates and bridges, the hooks flex better)",
        print_notes="Flat on the bed (the thick-end side up), no supports, 100% infill.",
        color=color,
        footprint=f"for {size.nx}x{size.ny}x{size.h}",
    )


def parts_for(size: BoxSize) -> list[tuple[Part, PartInfo]]:
    """The divider set for one crate size: two rails, wall hooks and bridges."""
    tag = f"{size.nx}x{size.ny}x{size.h}"
    height = plate_height(size)
    parts = [
        (
            make_rail(size, along_x=True),
            _info(
                f"rail-x-{tag}",
                f"X rail {tag}",
                f"Full-width, {height:.1f} mm tall, notched from below; hook plates hang on it.",
                size,
                "#f0c419",
            ),
        ),
        (
            make_rail(size, along_x=False),
            _info(
                f"rail-y-{tag}",
                f"Y rail {tag}",
                "Full-depth rail notched from the top: goes in first, X rails drop over it.",
                size,
                "#e8a33d",
            ),
        ),
    ]
    for j in range(1, 2 * size.ny - 1):
        reach = rail_center_from_wall(j)
        parts.append(
            (
                make_wall_hook(size, j),
                _info(
                    f"hook-{j * 21}-{tag}",
                    f"Hook plate {j * 21} mm {tag}",
                    f"From a front/back wall slot to an X rail {reach:.1f} mm away.",
                    size,
                    "#4fb3bf",
                ),
            )
        )
    for m in range(1, 2 * size.ny - 1):
        parts.append(
            (
                make_bridge(size, m),
                _info(
                    f"bridge-{m * 21}-{tag}",
                    f"Bridge {m * 21} mm {tag}",
                    f"Hangs between two X rails {m * 21} mm apart, at any position along them.",
                    size,
                    "#7d8ce0",
                ),
            )
        )
    return parts


def build() -> None:
    """Export the divider sets for every crate size in SIZES, after verifying them."""
    for size in SIZES:
        if not verify_size(size):
            raise SystemExit(f"divider verification failed for {size}")
        for part, info in parts_for(size):
            save(MODULE, part, info)


def _overlap(a: Part, b: Part) -> float:
    common = a & b
    return common.volume if common else 0.0


def _insertion_blocked(part: Part, crate: Part, travel: float) -> float | None:
    """First lift (mm, 1 mm steps) at which ``part`` collides with ``crate`` on its way down."""
    lift = 1.0
    while lift <= travel + 1.0:
        if _overlap(Pos(0, 0, lift) * part, crate) > 1e-6:
            return lift
        lift += 1.0
    return None


def demo_layout(size: BoxSize) -> list[tuple[str, Part]]:
    """A placed example: X rails at y = 0 and +21, a Y rail at x = 0, a wall hook, a bridge."""
    cav_d = size.cavity[1]
    z = FLOOR_Z + 0.01
    front = -cav_d / 2
    rail_y = Rot(0, 0, 90) * make_rail(size, along_x=False)
    placed = [
        ("x rail @0", Pos(0, 0, z) * make_rail(size, along_x=True)),
        ("x rail @21", Pos(0, 21, z) * make_rail(size, along_x=True)),
        ("y rail @0", Pos(0, 0, z) * rail_y),
        ("wall hook", Pos(-21, front, z) * Rot(0, 0, 90) * make_wall_hook(size, size.ny)),
        ("bridge", Pos(21, 0, z) * Rot(0, 0, 90) * make_bridge(size, 1)),
    ]
    return placed


def verify() -> bool:
    """Run verify_size for every crate size in SIZES."""
    return all([verify_size(size) for size in SIZES])


def verify_size(size: BoxSize) -> bool:
    """Every placed part clears the crate, each other and the stacking seat; hooks engage."""
    crate = make_box(size)
    upper = Pos(0, 0, size.h * HEIGHT_UNIT) * make_box(BoxSize(size.nx, size.ny, 2))
    seat = size.lip_top - SEAT_DEPTH
    placed = demo_layout(size)
    ok = True

    def check(name: str, passed: bool, detail: str) -> None:
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {size}: {name} {detail}")

    for name, part in placed:
        check(f"{name} valid", part.is_valid, "")
        check(f"{name} vs crate", _overlap(part, crate) < 1e-6, f"{_overlap(part, crate):.4f}")
        check(f"{name} vs upper box", _overlap(part, upper) < 1e-6, f"{_overlap(part, upper):.4f}")
        top = part.bounding_box().max.Z
        check(f"{name} below seat", top <= seat, f"top {top:.2f} <= {seat:.2f}")
    for i, (name_a, a) in enumerate(placed):
        for name_b, b in placed[i + 1 :]:
            vol = _overlap(a, b)
            check(f"{name_a} vs {name_b}", vol < 1e-6, f"{vol:.4f}")
    z = FLOOR_Z + 0.01
    far_rails = [Pos(0, y, z) * make_rail(size, along_x=True) for y in (-GRID / 2, GRID / 2)]
    long_bridge = Pos(-GRID / 2, -GRID / 2, z) * Rot(0, 0, 90) * make_bridge(size, 2)
    for rail_part in far_rails:
        vol = _overlap(long_bridge, rail_part)
        check("42 mm bridge vs its rail", vol < 1e-6, f"{vol:.4f}")
    vol = _overlap(long_bridge, crate)
    check("42 mm bridge vs crate", vol < 1e-6, f"{vol:.4f}")
    for name, part in placed:
        blocked = _insertion_blocked(part, crate, size.lip_top - FLOOR_Z)
        check(
            f"{name} drops straight in",
            blocked is None,
            f"blocked at +{blocked} mm" if blocked else "",
        )
    hook = dict(placed)["wall hook"]
    rail = dict(placed)["x rail @0"]
    pulled = _overlap(Pos(0, -1.0, 0) * hook, rail)
    check("hook engages (pulled 1 mm toward the wall collides)", pulled > 0, f"{pulled:.2f}")
    return ok


if __name__ == "__main__":
    build()
