"""Drawer cabinet: stackable sleeves with an open front, and the drawers that slide into them.

A sleeve keeps the whole crate contract (core feet underneath, core lip pocket on top, clip
sockets on the sides), so sleeves stack on each other at exactly 7 * h, sit on Gridfinity
baseplates and on any crate of the same footprint, and take a crate or a cap on top. Its front
wall is cut away below a lintel; a stack of sleeves is the cabinet.

Frames: a sleeve is centered on XY with its feet on z = 0 (front face -Y). A drawer is exported
in the frame of its sleeve, lowered by FLOOR_Z: placed at (0, 0, FLOOR_Z) it is closed.

Mechanism, all in the printed geometry (no hardware):
- Closing stop: the front plate is wider and taller than the opening; its back face lands on
  the sleeve's front face (side walls and lintel). The tray keeps BACK_CLEARANCE to the back.
- Retention stop: a 1 mm block on the sleeve floor, just behind the front wall, runs in a
  groove under the drawer floor. A catch in the groove meets it after TRAVEL mm. The catch is
  rigid: lift the drawer front (it tilts about its back edge, the lintel leaves TOP_CLEARANCE)
  and the catch rises over the block, so the drawer comes out; pushing it back in, the 45 deg
  ramp behind the catch lifts it the same way.
- Closed detent: two tongues cut free in the drawer side walls carry 45 deg bumps that click
  into vertical dimples in the sleeve walls when the drawer is closed. They only rub for the
  first few mm of travel, then leave the sleeve.

Print: sleeves upright on their feet; the lintel is the only bridge (as wide as the cavity).
Drawers upright on their floor; the groove under the floor bridges GROOVE_WIDTH. No supports.
"""

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    Box,
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
    CLIP_SOCKET_LIP_Z,
    DIVIDER_SLOT_DEPTH,
    DIVIDER_SLOT_WIDTH,
    FLOOR_Z,
    FOOT_HEIGHT,
    GRID,
    HEIGHT_UNIT,
    LABEL_HEIGHT,
    OUTER_RADIUS,
    WALL,
    BoxSize,
    clip_socket_cuts,
    clip_socket_positions,
    divider_slot_positions,
    feet,
    label_recess,
    lip_pocket,
    make_box,
    make_cap,
)
from stakee.export import PartInfo, save
from stakee.modules.dividers import make_rail as make_divider_rail
from stakee.modules.dividers import plate_height
from stakee.modules.kit import make_stack_clip

MODULE = "drawers"

SIZES = (BoxSize(2, 2, 3), BoxSize(2, 2, 6))

# --- Opening and fits ---
LINTEL_MARGIN = 0.5  # lintel underside below 7 * h; the upper sleeve's feet hang down to 7 * h
SIDE_CLEARANCE = 0.35  # drawer side to sleeve wall, per side
BACK_CLEARANCE = 0.5  # drawer back to the sleeve's back wall when closed
TOP_CLEARANCE = 2.0  # drawer rim to lintel: the room the front is lifted to pass the stop
CORNER_RADIUS = 2.0  # rounded back corners of the tray (the cavity corners are 1.75)

# --- Drawer ---
DRAWER_WALL = 1.6
DRAWER_FLOOR = 2.0
FRONT_THICKNESS = 2.4
FRONT_REVEAL = 0.25  # front plate inset from the sleeve's sides
FRONT_GAP = 0.5  # vertical gap between the fronts of stacked drawers
FRONT_RADIUS = 2.0
LABEL_MARGIN = 1.0  # label recess top below the front plate top
PULL_WIDTH = 36.0
PULL_REACH = 5.0  # how far the finger cup stands proud of the front plate
PULL_SHELL = 2.0  # cup wall, measured horizontally
PULL_MAX_HEIGHT = 10.0

# --- Retention: block on the sleeve floor, groove + catch under the drawer floor ---
STOP_HEIGHT = 1.0
STOP_WIDTH = 6.0  # along X
STOP_SETBACK = 0.8  # ramp foot behind the front wall's inner face
STOP_FLAT = 1.2  # flat top of the block
GROOVE_DEPTH = 1.4  # 0.4 mm over the block; leaves 0.6 mm of floor
GROOVE_WIDTH = 7.6
GROOVE_FRONT = 1.5  # solid floor between the front plate and the groove
CATCH_FROM_BACK = 22.0  # catch face to the drawer's back: what stays inside at the stop
CATCH_FLAT = 1.0

# --- Closed detent: tongues in the drawer side walls, dimples in the sleeve walls ---
TONGUE_SLOT = 0.8
TONGUE_WIDTH = 6.0  # along Y
TONGUE_MAX_LENGTH = 12.0
BUMP_PROUD = 0.7  # beyond the drawer side face; 0.35 mm of it presses into the sleeve wall
BUMP_FLAT = 0.6
BUMP_HEIGHT = 5.0
BUMP_BELOW_RIM = 1.0
DIMPLE_CLEARANCE = 0.1

_MIN_Z = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class DrawerInterior(BoxSize):
    """A drawer's inside, shaped like a BoxSize so dividers.make_rail sizes rails for it."""

    inner: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def cavity(self) -> tuple[float, float, float]:
        return self.inner


def _span_box(x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Part:
    center = Pos((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2)
    return center * Box(x[1] - x[0], y[1] - y[0], z[1] - z[0])


def _profile_yz(points: list[tuple[float, float]], x0: float, x1: float) -> Part:
    """Extrude a (y, z) outline from x0 to x1."""
    face = Plane.YZ * Polygon(*points, align=None)
    return Pos(x0, 0, 0) * extrude(face, amount=x1 - x0, dir=(1, 0, 0))


def _profile_xy(points: list[tuple[float, float]], z0: float, z1: float) -> Part:
    """Extrude an (x, y) outline from z0 to z1."""
    return Pos(0, 0, z0) * extrude(Polygon(*points, align=None), amount=z1 - z0, dir=(0, 0, 1))


# --- Shared dimensions (sleeve frame unless noted) ---


def open_top(size: BoxSize) -> float:
    """Underside of the lintel, sleeve frame."""
    return size.h * HEIGHT_UNIT - LINTEL_MARGIN


def rim(size: BoxSize) -> float:
    """Drawer rim height, drawer frame (z = 0 is the drawer's underside)."""
    return open_top(size) - TOP_CLEARANCE - FLOOR_Z


def front_top(size: BoxSize) -> float:
    """Top of the drawer's front plate, drawer frame."""
    return size.h * HEIGHT_UNIT - FRONT_GAP


def tray_width(size: BoxSize) -> float:
    return size.cavity[0] - 2 * SIDE_CLEARANCE


def tray_back(size: BoxSize) -> float:
    """Y of the drawer's back face when closed."""
    return size.depth / 2 - WALL - BACK_CLEARANCE


def stop_back(size: BoxSize) -> float:
    """Y of the stop block's vertical back face (the face the catch meets)."""
    return -size.cavity[1] / 2 + STOP_SETBACK + STOP_HEIGHT + STOP_FLAT


def catch_y(size: BoxSize) -> float:
    """Y of the catch's vertical front face when the drawer is closed."""
    return tray_back(size) - CATCH_FROM_BACK


def travel(size: BoxSize) -> float:
    """How far the drawer slides out before the catch meets the stop block."""
    return catch_y(size) - stop_back(size)


def interior(size: BoxSize) -> DrawerInterior:
    """Usable inside of the drawer (width, depth, height), as a BoxSize for the rails."""
    width = tray_width(size) - 2 * DRAWER_WALL
    depth = tray_back(size) - DRAWER_WALL + size.depth / 2
    return DrawerInterior(size.nx, size.ny, size.h, (width, depth, rim(size) - DRAWER_FLOOR))


def interior_center_y(size: BoxSize) -> float:
    return (tray_back(size) - DRAWER_WALL - size.depth / 2) / 2


def tongue_span(size: BoxSize) -> tuple[float, float]:
    """(y0, y1) of the detent tongue, closed position."""
    y0 = -size.depth / 2 + TONGUE_SLOT * 2
    return y0, y0 + TONGUE_WIDTH


def bump_z(size: BoxSize) -> tuple[float, float]:
    """(z0, z1) of the detent bump, drawer frame."""
    top = rim(size) - BUMP_BELOW_RIM
    return top - BUMP_HEIGHT, top


# --- Sleeve ---


def _stop_block(size: BoxSize) -> Part:
    """The retention block on the sleeve floor: 45 deg ramp in front, vertical face behind."""
    y0 = -size.cavity[1] / 2 + STOP_SETBACK
    y1 = stop_back(size)
    z0, z1 = FLOOR_Z - 0.3, FLOOR_Z + STOP_HEIGHT
    points = [(y0, z0), (y0, FLOOR_Z), (y0 + STOP_HEIGHT, z1), (y1, z1), (y1, z0)]
    return _profile_yz(points, -STOP_WIDTH / 2, STOP_WIDTH / 2)


def _detent_outline(
    tip_x: float, flat: float, depth: float, side: int
) -> list[tuple[float, float]]:
    """45 deg trapezoid (x, y offsets) pointing along +X (side=1) or -X (side=-1)."""
    base = tip_x - side * depth
    half_tip, half_base = flat / 2, flat / 2 + depth
    return [
        (base, -half_base),
        (tip_x, -half_tip),
        (tip_x, half_tip),
        (base, half_base),
    ]


def _dimples(size: BoxSize) -> Part:
    """Vertical grooves in the sleeve's side walls, the bump grown by DIMPLE_CLEARANCE."""
    y_mid = sum(tongue_span(size)) / 2
    z0, z1 = bump_z(size)
    c = DIMPLE_CLEARANCE
    cuts = None
    for side in (-1, 1):
        tip = side * (tray_width(size) / 2 + BUMP_PROUD + c)
        flat = BUMP_FLAT + 2 * c * (math.sqrt(2) - 1)
        reach = abs(tip) - size.cavity[0] / 2 + 0.5  # start inside the cavity
        outline = [(x, y + y_mid) for x, y in _detent_outline(tip, flat, reach, side)]
        cut = _profile_xy(outline, FLOOR_Z + z0 - c, FLOOR_Z + z1 + c)
        cuts = cut if cuts is None else cuts + cut
    return cuts


def make_sleeve(size: BoxSize, magnets: bool = True, clip_sockets: bool = True) -> Part:
    """Drawer sleeve: a crate shell (core feet, lip pocket, clip sockets) with an open front.

    Args:
        size: footprint in 42 mm units and height in 7 mm units (h >= 3).
        magnets: 6.5x2.4 mm magnet pockets under each foot.
        clip_sockets: core L sockets on the side walls, so sleeves clip like crates.

    Raises:
        ValueError: if the height leaves no room for a drawer with dividers.
    """
    if size.h < 3:
        raise ValueError(f"sleeve height must be >= 3 units, got {size.h}: the drawer is too low")
    body = feet(size.nx, size.ny, magnets)
    body += Pos(0, 0, FOOT_HEIGHT) * extrude(
        RectangleRounded(size.width, size.depth, OUTER_RADIUS), amount=size.lip_top - FOOT_HEIGHT
    )
    cav_w, cav_d, _ = size.cavity
    body -= Pos(0, 0, FLOOR_Z) * extrude(
        RectangleRounded(cav_w, cav_d, OUTER_RADIUS - WALL), amount=size.lip_top
    )
    # The opening: the front wall below the lintel, plus the cavity's rounded front corners so
    # the drawer's square front corners pass.
    square = -cav_d / 2 + OUTER_RADIUS - WALL + 0.01
    body -= _span_box((-cav_w / 2, cav_w / 2), (-size.depth, square), (FLOOR_Z, open_top(size)))
    body -= lip_pocket(size)
    if clip_sockets:
        body -= clip_socket_cuts(size)
    body -= _dimples(size)
    return body + _stop_block(size)


# --- Drawer ---


def _tray(size: BoxSize) -> Part:
    """Tray behind the front plate: walls and floor, back corners rounded like the cavity."""
    half = tray_width(size) / 2
    front, back = -size.depth / 2, tray_back(size)
    top = rim(size)
    tray = _span_box((-half, half), (front, back), (0, top))
    back_edges = tray.edges().filter_by(Axis.Z).filter_by(lambda e: e.center().Y > 0)
    tray = fillet(back_edges, CORNER_RADIUS)
    inner = half - DRAWER_WALL
    tray -= _span_box((-inner, inner), (front - 1, back - DRAWER_WALL), (DRAWER_FLOOR, top + 1))
    return tray


def _front_plate(size: BoxSize) -> Part:
    """Plate over the opening; its back face is the closing stop."""
    width = size.width - 2 * FRONT_REVEAL
    height = front_top(size)
    plate = Pos(0, -size.depth / 2, height / 2) * extrude(
        Plane.XZ * RectangleRounded(width, height, FRONT_RADIUS), amount=FRONT_THICKNESS
    )
    front_y = -size.depth / 2 - FRONT_THICKNESS
    label_top = height - LABEL_MARGIN
    plate -= label_recess(width, front_y, label_top - LABEL_HEIGHT / 2)
    return plate + _finger_pull(size, front_y)


def pull_height(size: BoxSize) -> float:
    """Finger cup height: whatever the label leaves at the bottom of the plate, capped."""
    label_bottom = front_top(size) - LABEL_MARGIN - LABEL_HEIGHT
    return min(PULL_MAX_HEIGHT, label_bottom - 0.5)


def _finger_pull(size: BoxSize, front_y: float) -> Part:
    """Cup at the bottom of the plate: a 45 deg wall, then a vertical lip the finger pulls on.

    The finger drops in from above. The cup grows from the bed with no overhang past 45 deg;
    its end cheeks close the cup and tie it to the plate.
    """
    top = pull_height(size)
    r, t, y = PULL_REACH, PULL_SHELL, front_y
    wall = [(y + 0.3, 0), (y - t, 0), (y - t - r, r), (y - t - r, top), (y - r, top)]
    wall += [(y - r, r), (y, t), (y + 0.3, t)]
    cup = _profile_yz(wall, -PULL_WIDTH / 2, PULL_WIDTH / 2)
    envelope = [(y + 0.3, 0), (y - t, 0), (y - t - r, r), (y - t - r, top), (y + 0.3, top)]
    half = PULL_WIDTH / 2
    cup += _profile_yz(envelope, -half, -half + t) + _profile_yz(envelope, half - t, half)
    return cup


def _divider_slots(size: BoxSize) -> Part:
    """Core-size slots (1.6 x 0.8 mm, every 21 mm) on all four inner walls of the drawer."""
    cav_w = interior(size).cavity[0]
    y_mid = interior_center_y(size)
    top = front_top(size) + 1
    d = DIVIDER_SLOT_DEPTH + 0.02
    cuts = None
    for x in divider_slot_positions(size.nx):
        for y_face, sy in ((-size.depth / 2, -1), (tray_back(size) - DRAWER_WALL, 1)):
            y = y_face + sy * (DIVIDER_SLOT_DEPTH / 2 - 0.01)
            slot = Pos(x, y, DRAWER_FLOOR) * Box(DIVIDER_SLOT_WIDTH, d, top, align=_MIN_Z)
            cuts = slot if cuts is None else cuts + slot
    for y in divider_slot_positions(size.ny):
        for sx in (-1, 1):
            x = sx * (cav_w / 2 + DIVIDER_SLOT_DEPTH / 2 - 0.01)
            slot = Pos(x, y + y_mid, DRAWER_FLOOR) * Box(d, DIVIDER_SLOT_WIDTH, top, align=_MIN_Z)
            cuts = slot if cuts is None else cuts + slot
    return cuts


def _groove(size: BoxSize, catch: bool = True) -> Part:
    """Channel under the floor for the stop block, open at the back, minus the catch."""
    half = GROOVE_WIDTH / 2
    y0 = -size.depth / 2 + GROOVE_FRONT
    groove = _span_box((-half, half), (y0, tray_back(size) + 1), (-1, GROOVE_DEPTH))
    if not catch:
        return groove
    yc = catch_y(size)
    ramp_end = yc + CATCH_FLAT + GROOVE_DEPTH
    points = [(yc, -1.1), (yc + CATCH_FLAT, -1.1), (yc + CATCH_FLAT, 0), (ramp_end, GROOVE_DEPTH)]
    points += [(ramp_end, GROOVE_DEPTH + 0.1), (yc, GROOVE_DEPTH + 0.1)]
    return groove - _profile_yz(points, -half - 0.1, half + 0.1)


def _tongue_slots(size: BoxSize) -> Part:
    """Two through slots per side wall that free the detent tongues from the rim down."""
    y0, y1 = tongue_span(size)
    top = rim(size)
    root = top - min(TONGUE_MAX_LENGTH, top - DRAWER_FLOOR - 1.0)
    half = tray_width(size) / 2
    cuts = None
    for side in (-1, 1):
        x = (side * (half - DRAWER_WALL - 0.5), side * (half + 0.5))
        for ya, yb in ((y0 - TONGUE_SLOT, y0), (y1, y1 + TONGUE_SLOT)):
            slot = _span_box((min(x), max(x)), (ya, yb), (root, top + 1))
            cuts = slot if cuts is None else cuts + slot
    return cuts


def _bumps(size: BoxSize) -> Part:
    """45 deg detent bumps on the outer face of each tongue."""
    y_mid = sum(tongue_span(size)) / 2
    z0, z1 = bump_z(size)
    half = tray_width(size) / 2
    bumps = None
    for side in (-1, 1):
        tip = side * (half + BUMP_PROUD)
        outline = [
            (x, y + y_mid) for x, y in _detent_outline(tip, BUMP_FLAT, BUMP_PROUD + 0.3, side)
        ]
        bump = _profile_xy(outline, z0, z1)
        bumps = bump if bumps is None else bumps + bump
    return bumps


def make_drawer(size: BoxSize, bumps: bool = True, catch: bool = True) -> Part:
    """Drawer for ``make_sleeve(size)``, in the sleeve's frame lowered by FLOOR_Z.

    Args:
        size: the sleeve it slides into.
        bumps: the closed-detent bumps (False gives the rigid body used for sliding checks).
        catch: the retention catch in the floor groove (False only for the negative control).
    """
    drawer = _tray(size) + _front_plate(size)
    drawer -= _divider_slots(size)
    drawer -= _tongue_slots(size)
    drawer -= _groove(size, catch)
    if bumps:
        drawer += _bumps(size)
    return drawer


def make_rail(size: BoxSize, along_x: bool) -> Part:
    """dividers.make_rail sized for this drawer's interior (same slots, same notches)."""
    return make_divider_rail(interior(size), along_x)


# --- Export ---


def _tag(size: BoxSize) -> str:
    return f"{size.nx}x{size.ny}x{size.h}"


def _sleeve_info(size: BoxSize) -> PartInfo:
    tag = _tag(size)
    span = size.cavity[0]
    return PartInfo(
        slug=f"sleeve-{tag}",
        title=f"Drawer sleeve {tag}",
        blurb=(
            "Crate shell with an open front: same feet, lip and clip sockets as a crate, so "
            "sleeves stack into a cabinet and take a crate or a cap on top. Holds one drawer."
        ),
        material="PLA or PETG",
        print_notes=(
            f"Upright on its feet, no supports. The lintel over the opening bridges {span:.1f} mm: "
            "print a bridge test first and keep part cooling at 100% for bridges. "
            "3 walls, 15% infill. Optional 6x2 mm magnets."
        ),
        color="#e8e3d6",
        footprint=tag,
    )


def _drawer_info(size: BoxSize) -> PartInfo:
    tag = _tag(size)
    w, d, h = interior(size).cavity
    return PartInfo(
        slug=f"drawer-{tag}",
        title=f"Drawer {tag}",
        blurb=(
            f"Drawer for the {tag} sleeve, inside {w:.1f} x {d:.1f} x {h:.1f} mm, divider slots "
            f"every 21 mm, label recess and finger cup on the front. Slides out "
            f"{travel(size):.0f} mm to a stop; lift the front to take it out."
        ),
        material="PETG (the detent tongues flex) or PLA",
        print_notes=(
            "Upright on its floor, no supports: the groove under the floor bridges "
            f"{GROOVE_WIDTH:.1f} mm, the finger cup grows at 45 deg. 4 walls (the walls are "
            f"{DRAWER_WALL:.1f} mm), 15% infill."
        ),
        color="#f2a03d",
        footprint=tag,
    )


def _rail_info(size: BoxSize, along_x: bool) -> PartInfo:
    tag = _tag(size)
    axis = "x" if along_x else "y"
    height = plate_height(interior(size))
    notch = "from below; goes in after the Y rail" if along_x else "from the top; goes in first"
    return PartInfo(
        slug=f"rail-{axis}-drawer-{tag}",
        title=f"{axis.upper()} rail for drawer {tag}",
        blurb=(
            f"Divider rail sized for the {tag} drawer, {height:.1f} mm tall, notched {notch}. "
            "Same profile as the crate rails."
        ),
        material="PLA",
        print_notes="Flat on the bed (the thick-end side up), no supports, 100% infill.",
        color="#f0c419" if along_x else "#e8a33d",
        footprint=f"for drawer {tag}",
    )


def build() -> None:
    """Export sleeves, drawers and drawer rails for every size in SIZES into models/drawers/."""
    for size in SIZES:
        save(MODULE, make_sleeve(size), _sleeve_info(size))
        save(MODULE, make_drawer(size), _drawer_info(size))
        for along_x in (True, False):
            save(MODULE, make_rail(size, along_x), _rail_info(size, along_x))


# --- Verification ---

EPS = 1e-6
SETTLE = 0.05  # mm a part is pushed past a stop to prove contact
STEP = 1.0  # slide step


def _overlap(a: Part, b: Part) -> float:
    common = a & b
    return common.volume if common else 0.0


def _line(passed: bool, text: str) -> bool:
    print(f"  [{'PASS' if passed else 'FAIL'}] {text}")
    return passed


def _at(part: Part, out: float = 0.0) -> Part:
    """A drawer pulled ``out`` mm along -Y from closed (sleeve frame)."""
    return Pos(0, -out, FLOOR_Z) * part


def _lifted(size: BoxSize, part: Part, out: float, degrees: float) -> Part:
    """Drawer pulled ``out`` mm, front lifted: tilted nose-up about its back-bottom edge."""
    pivot_y = tray_back(size) - out
    tilt = Pos(0, pivot_y, FLOOR_Z) * Rot(-degrees, 0, 0) * Pos(0, -pivot_y, -FLOOR_Z)
    return tilt * _at(part, out)


def _verify_stacking(size: BoxSize, sleeve: Part) -> bool:
    """Sleeves keep the crate contract: 7 * h pitch on and under sleeves, crates and caps."""
    pitch = size.h * HEIGHT_UNIT
    low = BoxSize(size.nx, size.ny, 3)
    pairs = (
        ("sleeve on sleeve", sleeve, make_sleeve(low), pitch),
        ("crate h2 on sleeve", sleeve, make_box(BoxSize(size.nx, size.ny, 2)), pitch),
        ("cap on sleeve", sleeve, make_cap(size.nx, size.ny), pitch),
        ("sleeve on crate h3", make_box(low), sleeve, low.h * HEIGHT_UNIT),
    )
    ok = True
    for name, lower, upper, z in pairs:
        clear = _overlap(lower, Pos(0, 0, z) * upper)
        seated = _overlap(lower, Pos(0, 0, z - SETTLE) * upper)
        ok &= _line(
            clear < EPS < seated,
            f"{name}: {clear:.6f} mm3 at {z:.0f} mm, {seated:.2f} mm3 lowered {SETTLE} mm",
        )
    bottom = _span_box((-size.width, size.width), (-size.depth, size.depth), (-1, FOOT_HEIGHT))
    base = sleeve & bottom
    reference = feet(size.nx, size.ny)
    diff = (base - reference).volume + (reference - base).volume
    ok &= _line(diff < 1e-3, f"feet identical to core.feet (Gridfinity): {diff:.6f} mm3 differ")
    return ok


def _verify_clips(size: BoxSize, parts: tuple[Part, ...]) -> bool:
    """kit's stack clips, locked in the lip sockets at the seam, touch nothing in the cabinet."""
    clip = make_stack_clip()
    seam = size.h * HEIGHT_UNIT
    lip_z = size.lip_top - CLIP_SOCKET_LIP_Z
    placed = [
        Pos(x, y, seam) * Rot(0, 0, 0 if x > 0 else 180) * clip
        for x, y, z in clip_socket_positions(size)
        if z == lip_z
    ]
    worst = max(_overlap(c, p) for c in placed for p in parts)
    return _line(
        worst < EPS, f"{len(placed)} stack clips locked on the seam: worst {worst:.6f} mm3"
    )


def _verify_closed(size: BoxSize, sleeve: Part, drawer: Part, rigid: Part) -> bool:
    """Closed: no interference; the front plate is the stop; the detent bump is engaged."""
    closed = _overlap(sleeve, _at(drawer))
    pushed = _overlap(sleeve, _at(rigid, out=-SETTLE))
    tray_only = _overlap(sleeve, _at(_tray(size) - _groove(size), out=-(BACK_CLEARANCE - SETTLE)))
    ok = _line(closed < EPS, f"drawer closed in sleeve: {closed:.6f} mm3")
    ok &= _line(
        pushed > EPS > tray_only,
        f"closing stop is the front plate: pushed {SETTLE} mm in = {pushed:.2f} mm3; "
        f"the tray alone still clears the back wall by {BACK_CLEARANCE} mm",
    )
    full_1 = _overlap(sleeve, _at(drawer, out=STEP))
    rigid_1 = _overlap(sleeve, _at(rigid, out=STEP))
    ok &= _line(
        full_1 > EPS > rigid_1,
        f"detent engaged: opened {STEP:.0f} mm the bumps hit the dimple flanks "
        f"({full_1:.2f} mm3), the drawer without bumps clears ({rigid_1:.6f} mm3)",
    )
    return ok


def _verify_travel(size: BoxSize, sleeve: Part, rigid: Part, upper: Part) -> bool:
    """Slide out in 1 mm steps to the stop; the upper sleeve never meets the drawer."""
    stop = travel(size)
    steps = [STEP * k for k in range(1, int(stop / STEP) + 1)]
    worst_sleeve = max(_overlap(sleeve, _at(rigid, s)) for s in steps)
    worst_upper = max(_overlap(upper, _at(rigid, s)) for s in steps)
    ok = _line(
        worst_sleeve < EPS and steps[-1] == stop,
        f"slides out {len(steps)} x {STEP:.0f} mm to the stop at {stop:.1f} mm: "
        f"worst {worst_sleeve:.6f} mm3",
    )
    ok &= _line(
        worst_upper < EPS,
        f"upper sleeve's feet + drawer clear of the whole travel: worst {worst_upper:.6f} mm3",
    )
    past = _overlap(sleeve, _at(rigid, stop + SETTLE))
    step_past = _overlap(sleeve, _at(rigid, stop + STEP))
    ok &= _line(
        past > EPS and step_past > EPS,
        f"stop engaged: {SETTLE} mm past = {past:.2f} mm3, one more step = {step_past:.2f} mm3",
    )
    return ok


def _verify_lift(size: BoxSize, sleeve: Part, drawer: Part, upper: Part) -> bool:
    """At the stop, lifting the front tilts the catch over the stop block and out."""
    stop = travel(size)
    lever = tray_back(size) - stop + size.depth / 2  # pivot to the lintel's front edge
    angle = 0.9 * math.degrees(math.atan(TOP_CLEARANCE / lever))
    rise = CATCH_FROM_BACK * math.sin(math.radians(angle))
    poses = [_lifted(size, drawer, stop, angle * k / 3) for k in (1, 2, 3)]
    tilt = max(_overlap(sleeve, p) + _overlap(upper, p) for p in poses)
    ok = _line(
        tilt < EPS and rise > STOP_HEIGHT,
        f"lift at the stop: front tilts {angle:.2f} deg ({TOP_CLEARANCE} mm under the lintel), "
        f"catch rises {rise:.2f} mm over the {STOP_HEIGHT} mm block: {tilt:.6f} mm3",
    )
    out = tray_back(size) + size.depth / 2 + 1.0
    steps = [stop + STEP * k for k in range(1, int((out - stop) / STEP) + 1)]
    worst = max(_overlap(sleeve, _lifted(size, drawer, s, angle)) for s in steps)
    ok &= _line(
        worst < EPS,
        f"lifted, it slides the remaining {steps[-1] - stop:.0f} mm out: worst {worst:.6f} mm3",
    )
    return ok


def _droop_angle(size: BoxSize) -> float:
    """Nose-down tilt (deg) about the sill at which the drawer's back rim meets 7 * h."""
    stop = travel(size)
    run = tray_back(size) - stop + size.depth / 2  # sill edge to the drawer's back
    rise = rim(size)
    room = size.h * HEIGHT_UNIT - FLOOR_Z  # the upper part's feet hang down to 7 * h
    # rise * cos(a) + run * sin(a) = room
    hyp = math.hypot(rise, run)
    return math.degrees(math.asin(room / hyp) - math.atan2(rise, run))


def _drooped(size: BoxSize, part: Part, out: float, degrees: float) -> Part:
    """Drawer pulled ``out`` mm and tipped nose-down about the sill edge by its own weight."""
    sill = -size.depth / 2
    tilt = Pos(0, sill, FLOOR_Z) * Rot(degrees, 0, 0) * Pos(0, -sill, -FLOOR_Z)
    return tilt * _at(part, out)


def _verify_droop(size: BoxSize, sleeve: Part, drawer: Part, uppers: dict[str, Part]) -> bool:
    """Pulled to the stop, the drawer tips until the part above holds its back; the catch holds."""
    stop = travel(size)
    angle = _droop_angle(size)
    rise = (stop_back(size) + size.depth / 2) * math.sin(math.radians(angle))
    ok = True
    for name, upper in uppers.items():
        # Tipping swings the catch face forward by ~0.1 mm, so it rests just short of the stop.
        resting = _drooped(size, drawer, stop - 0.2, angle - 0.05)
        held = _overlap(upper, _drooped(size, drawer, stop - 0.2, angle + 0.3))
        clear = _overlap(upper, resting) + _overlap(sleeve, resting)
        pulled = _overlap(sleeve, _drooped(size, drawer, stop + STEP, angle - 0.05))
        ok &= _line(
            clear < EPS < held and pulled > EPS and rise < STOP_HEIGHT,
            f"droop under {name}: tips {angle:.2f} deg until its back meets the feet above "
            f"({held:.2f} mm3 at +0.3 deg); catch rises {rise:.2f} of {STOP_HEIGHT} mm and "
            f"still stops a pull ({pulled:.2f} mm3)",
        )
    return ok


def _verify_dividers(size: BoxSize, drawer: Part) -> bool:
    """dividers.make_rail sized for the drawer: fits, crosses, drops in, ends sit in slots."""
    z = DRAWER_FLOOR + 0.01
    y_mid = interior_center_y(size)
    rail_x, rail_y = make_rail(size, along_x=True), make_rail(size, along_x=False)
    placed = [
        ("y rail @0", Pos(0, y_mid, z) * Rot(0, 0, 90) * rail_y),
        *[(f"x rail @{p:+.0f}", Pos(0, y_mid + p, z) * rail_x) for p in (0.0, GRID / 2)],
    ]
    ok = True
    for name, part in placed:
        hit = _overlap(drawer, part)
        top = part.bounding_box().max.Z
        drop = next(
            (
                lift
                for lift in range(1, int(front_top(size)) + 2)
                if _overlap(Pos(0, 0, lift) * part, drawer) > EPS
            ),
            None,
        )
        ok &= _line(
            part.is_valid and hit < EPS and top < rim(size) and drop is None,
            f"{name}: {hit:.6f} mm3 in the drawer, top {top:.1f} < rim {rim(size):.1f} mm, "
            f"drops straight in{'' if drop is None else f' (blocked at +{drop} mm)'}",
        )
    cross = _overlap(placed[0][1], placed[1][1]) + _overlap(placed[1][1], placed[2][1])
    ok &= _line(cross < EPS, f"rails cross like an egg crate: {cross:.6f} mm3")
    seated = _overlap(drawer, Pos(STEP, 0, 0) * placed[1][1]) * _overlap(
        drawer, Pos(0, STEP, 0) * placed[0][1]
    )
    ok &= _line(seated > EPS, f"rail ends sit in the slots: shifted {STEP:.0f} mm they collide")
    return ok


def _verify_negative(size: BoxSize, sleeve: Part) -> bool:
    """A drawer without its catch must fail the stop check (it would slide straight out)."""
    loose = make_drawer(size, bumps=False, catch=False)
    past = _overlap(sleeve, _at(loose, travel(size) + STEP))
    caught = past < EPS
    print(
        f"  NEGATIVE: drawer without catch, {STEP:.0f} mm past the stop: {past:.6f} mm3 -> "
        f"stop check {'fails as it must (caught)' if caught else 'PASSES (NOT CAUGHT)'}"
    )
    return caught


def verify_size(size: BoxSize) -> bool:
    """Every check for one sleeve/drawer size; prints one PASS/FAIL line per check."""
    print(f"{_tag(size)}:")
    sleeve, drawer = make_sleeve(size), make_drawer(size)
    rigid = make_drawer(size, bumps=False)
    upper_size = BoxSize(size.nx, size.ny, 3)
    upper = Pos(0, 0, size.h * HEIGHT_UNIT) * (
        make_sleeve(upper_size) + _at(make_drawer(upper_size))
    )
    ok = True
    for name, part in (("sleeve", sleeve), ("drawer", drawer)):
        bb = part.bounding_box().size
        ok &= _line(part.is_valid, f"{name} valid, {bb.X:.1f} x {bb.Y:.1f} x {bb.Z:.1f} mm")
    w, d, h = interior(size).cavity
    print(
        f"    opening {size.cavity[0]:.1f} mm wide (the lintel bridge), drawer inside "
        f"{w:.1f} x {d:.1f} x {h:.1f} mm, side clearance {SIDE_CLEARANCE} mm"
    )
    ok &= _verify_stacking(size, sleeve)
    cabinet = _overlap(sleeve, _at(drawer)) + _overlap(upper, _at(drawer))
    cabinet += _overlap(upper, sleeve)
    ok &= _line(
        cabinet < EPS,
        f"cabinet: sleeve + drawer + upper sleeve + its drawer, all closed: {cabinet:.6f} mm3",
    )
    ok &= _verify_clips(size, (sleeve, _at(drawer), upper))
    ok &= _verify_closed(size, sleeve, drawer, rigid)
    ok &= _verify_travel(size, sleeve, rigid, upper)
    ok &= _verify_lift(size, sleeve, drawer, upper)
    cap = Pos(0, 0, size.h * HEIGHT_UNIT) * make_cap(size.nx, size.ny)
    ok &= _verify_droop(size, sleeve, drawer, {"a sleeve": upper, "a cap": cap})
    ok &= _verify_dividers(size, drawer)
    ok &= _verify_negative(size, sleeve)
    return ok


def verify() -> bool:
    """Run verify_size for every size in SIZES."""
    ok = all([verify_size(size) for size in SIZES])
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return ok


if __name__ == "__main__":
    if not verify():
        raise SystemExit("drawer verification failed; nothing exported")
    build()
