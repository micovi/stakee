"""Wall rail: crates hang on the wall above the bench on a 45 deg French cleat.

Two parts:
- Wall cleat: a strip screwed to the wall, top bevelled at 45 deg so it falls toward the
  wall (the classic French cleat). 10 mm thick, 30 mm tall at its front face, 20 mm at the
  wall face. 4 mm wood screws on a 42 mm pitch (one per grid cell), 90 deg countersinks
  on the front face. Length is ``n * 42 - 0.5`` so strips butt end to end on the grid.
- Shelf: a tray whose top is a grid of per-cell stacking lips (core ``lip_pocket``, one per
  42 mm cell, like a baseplate), so any crate footprint seats on it exactly as it seats on
  another crate. Behind and below the tray: a hook with the matching 45 deg bevel, a back
  plate, a bumper that rests on the wall, and a diagonal brace up to the tray front.

Side profile (wall frame: ``u`` = distance from the wall face, ``z`` = up, 0 = cleat bottom).
The shelf back (tray, hook tip and bumper) is flat at ``u = 0``. The hook rests on the cleat
bevel; a 0.5 mm gap separates the back plate from the cleat's front face.

Tipping: the crates' centre of mass sits ``d = depth / 2`` in front of the wall. The cleat
pushes the hook up and toward the wall with equal components, and the bumper pushes back
at a lever ``L`` below the cleat contact. Without friction the shelf stays hooked while
``L >= d``; the bumper is placed at ``L = 1.25 d`` (and always low enough that lifting the
shelf 10 mm to unhook it does not hit the cleat).

Loads (assumed): a full 2x2x6 crate is 0.5-1 kg; design load 2 kg per shelf (two full
crates stacked), PETG, E ~ 2 GPa. At 2 kg the bumper and hook forces are ~16-20 N, spread
over the full shelf width: stresses stay well under 1 MPa, so walls are sized for stiffness,
impact and printability (>= 2.4 mm), not strength. The weak links are the wall screws and
anchors. PETG/ASA rather than PLA because PLA creeps under a sustained load.

Printing: the shelf is a constant side profile extruded across its width, so it prints on
its side (an end face on the bed) with no supports and the bending loads lie in the layer
planes. The only overhangs are the lip pockets' end walls facing up the print: 45 deg
chamfers and a 1.8 mm ledge, bridged across the pocket.
"""

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Box,
    Cone,
    Cylinder,
    Part,
    Plane,
    Polygon,
    Pos,
    RectangleRounded,
    Rot,
    extrude,
    fillet,
)

from stakee.core import (
    FOOT_STATIONS,
    GAP,
    GRID,
    LIP_CLEARANCE,
    OUTER_RADIUS,
    SEAT_DEPTH,
    BoxSize,
    cell_centers,
    lip_pocket,
    make_box,
)
from stakee.export import PartInfo, save

MODULE = "wallrail"

# --- Wall cleat (profile in u, z; u = 0 is the wall face) ---
CLEAT_THICKNESS = 10.0  # T: also the 45 deg bevel run and the hook engagement depth
CLEAT_HEIGHT = 30.0  # H: height at the front face; the wall face is H - T tall
SCREW_HOLE = 4.5  # clearance for a 4 mm wood screw
COUNTERSINK = 8.6  # 90 deg countersink diameter at the front face (8 mm heads)
SCREW_Z = (CLEAT_HEIGHT - CLEAT_THICKNESS) / 2  # centred on the full-thickness part
MIN_SCREW_WALL = 2.0  # plastic left around every hole and countersink
END_GAP = 2 * GAP  # strips are n * 42 - 0.5 long

# --- Shelf ---
BACK_GAP = 0.5  # back plate to cleat front face
BACK_PLATE = 4.0
BRACE = 3.2  # diagonal brace thickness
BUMPER_HEIGHT = 10.0
HOOK_TOP = 2.0  # tray underside above the cleat's top edge
TRAY_FLOOR = 2.4
FEET_CLEAR = 0.5  # recess floor below the bottom of a seated crate's feet
VOID_FILLET = 2.0
LEVER_FACTOR = 1.25  # bumper lever / centre-of-mass offset
UNHOOK_MARGIN = 2.0  # bumper top below the cleat bottom, after lifting the hook clear
POCKET_INSET = FOOT_STATIONS[0][1] - LIP_CLEARANCE  # lip pocket floor inset

PETG_DENSITY = 1.27e-3  # g/mm^3
DESIGN_LOAD_KG = 2.0

SHELVES = ((2, 1), (2, 2), (3, 2), (4, 1))
CLEAT_LENGTHS = (2, 4)


@dataclass(frozen=True)
class ShelfLayout:
    """Side-profile numbers for a shelf of ``ny`` cells depth, in the wall frame (mm).

    Attributes:
        depth: tray depth along Y (also how far the tray reaches from the wall).
        tray_top: tray top (the lip top).
        tray_bottom: tray underside.
        bottom: lowest point (bumper bottom).
        bumper_top: top of the bumper.
        com_offset: crate centre of mass in front of the wall.
        contact_z: centre of the hook/cleat bevel contact.
        lever: vertical distance from the bevel contact to the bumper centre.
    """

    depth: float
    tray_top: float
    tray_bottom: float
    bottom: float
    bumper_top: float
    com_offset: float
    contact_z: float
    lever: float

    @property
    def seat(self) -> float:
        """Where a seated crate's z = 0 sits (stacking seat), wall frame."""
        return self.tray_top - SEAT_DEPTH


def shelf_layout(ny: int) -> ShelfLayout:
    """Compute the side profile of a shelf ``ny`` grid cells deep."""
    depth = ny * GRID - 2 * GAP
    tray_bottom = CLEAT_HEIGHT + HOOK_TOP
    tray_top = tray_bottom + TRAY_FLOOR + FEET_CLEAR + SEAT_DEPTH
    com_offset = depth / 2
    contact_z = CLEAT_HEIGHT - CLEAT_THICKNESS / 2
    by_lever = contact_z - LEVER_FACTOR * com_offset
    by_unhook = -(CLEAT_THICKNESS + UNHOOK_MARGIN) - BUMPER_HEIGHT / 2
    bumper_mid = min(by_lever, by_unhook)
    return ShelfLayout(
        depth=depth,
        tray_top=tray_top,
        tray_bottom=tray_bottom,
        bottom=bumper_mid - BUMPER_HEIGHT / 2,
        bumper_top=bumper_mid + BUMPER_HEIGHT / 2,
        com_offset=com_offset,
        contact_z=contact_z,
        lever=contact_z - bumper_mid,
    )


def _shelf_outline(lay: ShelfLayout) -> list[tuple[float, float]]:
    t, h = CLEAT_THICKNESS, CLEAT_HEIGHT
    back = t + BACK_GAP
    return [
        (0.0, lay.tray_top),
        (lay.depth, lay.tray_top),
        (lay.depth, lay.tray_bottom),
        (back + BACK_PLATE, lay.bottom),
        (0.0, lay.bottom),
        (0.0, lay.bumper_top),
        (back, lay.bumper_top),
        (back, h + BACK_GAP),  # the hook bevel continues the cleat's 45 deg line
        (0.0, h - t),
    ]


def _brace_void(lay: ShelfLayout) -> list[tuple[float, float]]:
    """Triangle between back plate, tray underside and the inner face of the brace."""
    plate_front = CLEAT_THICKNESS + BACK_GAP + BACK_PLATE
    du, dz = lay.depth - plate_front, lay.tray_bottom - lay.bottom
    length = math.hypot(du, dz)
    nu, nz = -dz / length, du / length  # brace normal, pointing into the void
    u0, z0 = plate_front + BRACE * nu, lay.bottom + BRACE * nz
    z_at_plate = z0 + (plate_front - u0) * dz / du
    u_at_tray = u0 + (lay.tray_bottom - z0) * du / dz
    return [(plate_front, lay.tray_bottom), (plate_front, z_at_plate), (u_at_tray, lay.tray_bottom)]


def _profile_solid(points: list[tuple[float, float]], lay: ShelfLayout, width: float) -> Part:
    """Extrude a wall-frame (u, z) outline across ``width`` into the shelf's local frame."""
    local = [(lay.depth / 2 - u, z - lay.bottom) for u, z in points]
    return extrude(Plane.YZ * Polygon(*local, align=None), amount=width / 2, both=True)


def _lip_cuts(nx: int, ny: int, tray_top: float) -> Part:
    """Per-cell stacking lips plus a recess under the feet, lip top at ``tray_top``."""
    cell = BoxSize(1, 1, 1)
    shift = tray_top - cell.lip_top
    pocket_floor = tray_top - SEAT_DEPTH + LIP_CLEARANCE
    recess_floor = tray_top - SEAT_DEPTH - FEET_CLEAR
    size = cell.width - 2 * POCKET_INSET
    recess = extrude(
        Plane.XY.offset(recess_floor)
        * RectangleRounded(size, size, max(OUTER_RADIUS - POCKET_INSET, 0.4)),
        amount=pocket_floor - recess_floor + 0.05,
    )
    one = (Pos(0, 0, shift) * lip_pocket(cell)) + recess
    cuts = None
    for cx, cy in cell_centers(nx, ny):
        placed = Pos(cx, cy, 0) * one
        cuts = placed if cuts is None else cuts + placed
    return cuts


def make_shelf(nx: int, ny: int) -> Part:
    """Wall shelf for an ``nx`` x ``ny`` cell footprint, hung on a French cleat.

    Local frame: X = width, front is -Y, the wall is the +Y plane at ``y = depth / 2``,
    lowest point at z = 0. A crate seats at z = ``seat_height(ny)``.

    Args:
        nx: width in 42 mm grid cells.
        ny: depth in 42 mm grid cells.
    """
    lay = shelf_layout(ny)
    width = nx * GRID - 2 * GAP
    shelf = _profile_solid(_shelf_outline(lay), lay, width)
    local_void = [(lay.depth / 2 - u, z - lay.bottom) for u, z in _brace_void(lay)]
    void = Plane.YZ * Polygon(*local_void, align=None)
    void = fillet(void.vertices(), VOID_FILLET)
    shelf -= extrude(void, amount=width / 2 + 1, both=True)
    shelf -= _lip_cuts(nx, ny, lay.tray_top - lay.bottom)
    return shelf


def seat_height(ny: int) -> float:
    """Local z of a crate's z = 0 when it sits on a shelf ``ny`` cells deep."""
    lay = shelf_layout(ny)
    return lay.seat - lay.bottom


def shelf_on_cleat(ny: int) -> tuple[float, float, float]:
    """Offset that places a shelf's local origin on a wall cleat's local origin (hung)."""
    lay = shelf_layout(ny)
    return (0.0, CLEAT_THICKNESS / 2 - lay.depth / 2, lay.bottom)


def screw_x_positions(n: int) -> list[float]:
    """Screw hole centres along a cleat ``n`` cells long: one per cell, 42 mm pitch."""
    return [x for x, _ in cell_centers(n, 1)]


def _cleat_body(n: int) -> Part:
    t, h = CLEAT_THICKNESS, CLEAT_HEIGHT
    profile = [(t / 2 - u, z) for u, z in ((0, 0), (t, 0), (t, h), (0, h - t))]
    length = n * GRID - END_GAP
    return extrude(Plane.YZ * Polygon(*profile, align=None), amount=length / 2, both=True)


def _screw_cut(x: float, grow: float = 0.0) -> Part:
    """Clearance hole + 90 deg countersink on the front (-Y) face, grown by ``grow``."""
    t = CLEAT_THICKNESS
    hole_r = SCREW_HOLE / 2 + grow
    sink_r = COUNTERSINK / 2 + grow
    hole = Pos(x, 0, SCREW_Z) * Rot(90, 0, 0) * Cylinder(hole_r, t + 2)
    sink_depth = sink_r - hole_r
    sink = (
        Pos(x, -t / 2 - 1, SCREW_Z)
        * Rot(-90, 0, 0)
        * Cone(sink_r + 1, hole_r, sink_depth + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    )
    return hole + sink


def make_wall_cleat(n: int) -> Part:
    """Wall strip ``n`` cells long; local frame: wall face is +Y, bevel on top.

    Args:
        n: length in 42 mm grid cells (strip is ``n * 42 - 0.5`` mm).
    """
    if n < 1:
        raise ValueError(f"cleat length must be >= 1 cell, got {n}")
    cleat = _cleat_body(n)
    for x in screw_x_positions(n):
        cleat -= _screw_cut(x)
    return cleat


def _shelf_info(nx: int, ny: int) -> PartInfo:
    lay = shelf_layout(ny)
    tag = f"{nx}x{ny}"
    strip = ny == 1 and nx >= 4
    title = f"Wall shelf strip {tag}" if strip else f"Wall shelf {tag}"
    return PartInfo(
        slug=f"shelf-{tag}",
        title=title,
        blurb=(
            f"Hangs on the wall cleat; its top is a grid of stacking lips, so any {tag} "
            "footprint of crates (or smaller ones, cell by cell) seats exactly as on another "
            f"crate. Bumper {lay.lever:.0f} mm below the hook keeps it from tipping forward."
        ),
        material="PETG or ASA (load-bearing, PLA creeps)",
        print_notes=(
            "On its side (an end face on the bed), no supports: the hook, back plate and brace "
            "are one constant profile. 4 walls, 25% gyroid. Design load 2 kg."
        ),
        color="#6b8f71",
        footprint=tag,
    )


def _cleat_info(n: int) -> PartInfo:
    length = n * GRID - END_GAP
    return PartInfo(
        slug=f"wall-cleat-{n}",
        title=f"Wall cleat {n} cells",
        blurb=(
            f"45 deg French cleat, {length:.1f} mm long, {n} countersunk holes for 4 mm wood "
            "screws on a 42 mm pitch. Butt strips end to end; shelves slide anywhere along it."
        ),
        material="PETG or ASA",
        print_notes=(
            "Front face (the countersunk side) on the bed, bevel facing up, no supports. "
            "4 walls, 30% infill. Use at least 2 screws with wall anchors."
        ),
        color="#a0754f",
        footprint=f"{n}x1",
    )


def build() -> None:
    """Verify, then export every shelf and wall cleat into models/wallrail/."""
    if not verify():
        raise SystemExit("wallrail verification failed")
    for nx, ny in SHELVES:
        save(MODULE, make_shelf(nx, ny), _shelf_info(nx, ny))
    for n in CLEAT_LENGTHS:
        save(MODULE, make_wall_cleat(n), _cleat_info(n))


def _overlap(a: Part, b: Part) -> float:
    common = a & b
    return common.volume if common else 0.0


def _report(name: str, passed: bool, detail: str) -> bool:
    print(f"  [{'PASS' if passed else 'FAIL'}] {name} {detail}")
    return passed


def _seats(name: str, part: Part, shelf: Part, z: float, x: float = 0.0, y: float = 0.0) -> bool:
    """Part placed at seat height clears the shelf; 0.05 mm lower it collides."""
    at_seat = _overlap(Pos(x, y, z) * part, shelf)
    lowered = _overlap(Pos(x, y, z - 0.05) * part, shelf)
    ok = _report(f"{name} at seat z={z:.2f}", at_seat < 1e-3, f"overlap {at_seat:.5f} mm^3")
    return ok & _report(f"{name} lowered 0.05 mm", lowered > 0, f"overlap {lowered:.3f} mm^3")


def _verify_hang(nx: int, ny: int, shelf: Part) -> bool:
    """Hang the shelf on a cleat in front of a wall and test contact and removal."""
    lay = shelf_layout(ny)
    off = shelf_on_cleat(ny)
    hung = Pos(*off) * shelf
    cleat = make_wall_cleat(nx + 1)
    wall = Pos(0, CLEAT_THICKNESS / 2, 0) * Box(
        600, 20, 600, align=(Align.CENTER, Align.MIN, Align.CENTER)
    )
    ok = True
    for name, other in (("cleat", cleat), ("wall", wall)):
        vol = _overlap(hung, other)
        ok &= _report(f"hung vs {name}", vol < 1e-3, f"overlap {vol:.5f} mm^3")
    down = _overlap(Pos(0, 0, -1) * hung, cleat)
    ok &= _report("hook engages (1 mm down hits cleat)", down > 0, f"{down:.2f} mm^3")
    back = _overlap(Pos(0, 0.05, 0) * hung, wall)
    ok &= _report("bumper rests on wall (0.05 mm back hits wall)", back > 0, f"{back:.2f} mm^3")
    lifted = Pos(0, 0, CLEAT_THICKNESS + 0.1) * hung
    clear = _overlap(lifted, cleat) + _overlap(Pos(0, -15, 0) * lifted, cleat)
    ok &= _report("lift 10.1 mm then pull 15 mm clears cleat", clear < 1e-3, f"{clear:.5f}")
    crate = Pos(off[0], off[1], off[2] + seat_height(ny)) * make_box(BoxSize(nx, ny, 6))
    vol = _overlap(crate, wall) + _overlap(crate, cleat)
    ok &= _report("hung crate vs wall + cleat", vol < 1e-3, f"overlap {vol:.5f} mm^3")
    ok &= _report(
        "tipping lever >= centre-of-mass offset",
        lay.lever >= lay.com_offset,
        f"L={lay.lever:.1f} d={lay.com_offset:.1f} mm",
    )
    return ok


def _print_statics(ny: int) -> None:
    """Frictionless hand calc at the design load: bumper and hook reactions."""
    lay = shelf_layout(ny)
    weight = DESIGN_LOAD_KG * 9.81
    bumper = weight * lay.com_offset / lay.lever
    hook = weight * math.sqrt(2)
    print(
        f"  statics {DESIGN_LOAD_KG:.0f} kg: hook normal {hook:.1f} N, bumper {bumper:.1f} N, "
        f"top-of-shelf on wall {weight - bumper:.1f} N (>0: stays hooked)"
    )


def _verify_cleat(n: int) -> bool:
    cleat = make_wall_cleat(n)
    body = _cleat_body(n)
    slab = Box(1000, CLEAT_THICKNESS, 1000)
    ok = _report(f"wall-cleat-{n} valid", cleat.is_valid, "")
    for x in screw_x_positions(n):
        fat = _screw_cut(x, MIN_SCREW_WALL)
        escape = _overlap(fat, slab) - _overlap(fat, body)
        ok &= _report(
            f"  screw x={x:+.0f} keeps {MIN_SCREW_WALL} mm wall", escape < 1e-3, f"{escape:.4f}"
        )
    return ok


def verify() -> bool:
    """Print validity, seating, hanging and screw-hole checks; True when all pass."""
    ok = True
    for nx, ny in SHELVES:
        shelf = make_shelf(nx, ny)
        bb = shelf.bounding_box()
        mass = shelf.volume * PETG_DENSITY
        dims = f"{bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm"
        print(f"shelf-{nx}x{ny}: {dims}, ~{mass:.0f} g solid PETG")
        ok &= _report("valid", shelf.is_valid, "")
        z = seat_height(ny)
        ok &= _seats(f"crate {nx}x{ny}x3", make_box(BoxSize(nx, ny, 3)), shelf, z)
        cx, cy = cell_centers(nx, ny)[-1]
        ok &= _seats("crate 1x1x3 in corner cell", make_box(BoxSize(1, 1, 3)), shelf, z, cx, cy)
        ok &= _verify_hang(nx, ny, shelf)
        _print_statics(ny)
    for n in CLEAT_LENGTHS:
        ok &= _verify_cleat(n)
    print("negative control (a broken placement must be caught):")
    shelf = make_shelf(2, 2)
    low = _overlap(Pos(0, 0, seat_height(2) - 1.0) * make_box(BoxSize(2, 2, 3)), shelf)
    caught = _report("crate 1 mm below seat is flagged", low > 1e-3, f"overlap {low:.2f} mm^3")
    hung_low = Pos(*shelf_on_cleat(2)) * Pos(0, 0, -0.5) * shelf
    clash = _overlap(hung_low, make_wall_cleat(3))
    caught &= _report("shelf hung 0.5 mm low is flagged", clash > 1e-3, f"overlap {clash:.2f}")
    ok &= caught
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return ok


if __name__ == "__main__":
    build()
