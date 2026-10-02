"""Pocket box: a small hinged, latched box you carry, that is still a Stakee box.

Closed, base + lid have the envelope of a ``BoxSize(nx, ny, 4)`` crate: Gridfinity feet under
the base, a full stacking lip on top of the lid at ``7 * h + 4``. So the closed box seats on
any crate's lip at ``7 * h_lower`` and a crate or cap seats on it at ``7 * h``.

Parting plane ``z = split``: the base is the core crate cut there; the lid is a solid slab
(printed on its flat underside) with the core lip pocket and a floor ``STACK_CLEARANCE`` below
the feet of whatever stacks on it.

Hinge (back, along X): a pin hinge for a length of 1.75 mm filament. The axis lies
``KNUCKLE_R`` in from the back face and ``KNUCKLE_R`` above the parting plane, so every knuckle
stays inside the footprint and the lid's knuckles touch the bed. Five knuckles alternate base /
lid / base / lid / base. Behind the axis the lid only keeps material above a 45 deg chord (inside
the knuckle radius, so it turns in place), and the base is recessed behind the axis down to
``RECESS_BELOW_AXIS`` under it: a lid point can only swing back into the footprint if it lies
within ``KNUCKLE_R / cos(angle / 2)`` of the axis, so the recess sets the opening angle; at
about 120 deg the lid's back rests on the recess floor.

Latch (front, center): a cantilever tab grown from the base inside a front pocket, flush with
the front face. Its inward bump clicks into a notch in the lid's front slot; the bump's flat
underside holds the lid shut, its 45 deg top lets the lid push it aside when closing. To open,
pull the tab top toward you by the nail groove (1.1 mm at the bump) and lift.
"""

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Box,
    Circle,
    Cylinder,
    Location,
    Part,
    Plane,
    Polygon,
    Pos,
    Rectangle,
    RectangleRounded,
    Rot,
    extrude,
)

from stakee.core import (
    DIVIDER_SLOT_DEPTH,
    DIVIDER_THICKNESS,
    FLOOR_Z,
    HEIGHT_UNIT,
    LABEL_DEPTH,
    LABEL_HEIGHT,
    OUTER_RADIUS,
    WALL,
    BoxSize,
    label_width,
    lip_pocket,
    make_box,
    make_cap,
)
from stakee.export import PartInfo, save

MODULE = "pocket"

SIZES = (BoxSize(2, 1, 4), BoxSize(2, 2, 4))
LID_HEIGHT = 10.5  # parting plane to lip top
STACK_CLEARANCE = 0.2  # lid floor below the feet of a part stacked on the lid

# Hinge
KNUCKLE_R = 2.5
KNUCKLES = 5  # base, lid, base, lid, base
AXIAL_CLEAR = 0.4  # between neighbouring knuckles
RADIAL_CLEAR = 0.3  # a knuckle to the other part's cut-out
PIN_D = 1.75  # a length of 1.75 mm filament
PIN_HOLE_BASE = 1.9  # snug: holds the pin (printed holes come out a little small)
PIN_HOLE_LID = 2.0  # free: the lid turns on the pin
PIN_INSET = 0.5  # pin ends stay this far inside the side faces
RECESS_BELOW_AXIS = 5.0  # base recess behind the axis reaches this far below it
OPEN_ANGLE = 110.0  # verified sweep, degrees
SWEEP_STEP = 5.0

# Latch
TAB_WIDTH = 10.0
TAB_THICKNESS = 1.6  # 4 perimeters at 0.4 mm
TAB_ROOT_BELOW = 10.0  # tab root below the parting plane
TAB_TOP_ABOVE = 5.5  # tab top above the parting plane
TAB_SIDE_GAP = 0.5
TAB_BACK_GAP = 0.4  # base pocket behind the tab
LID_SLOT_GAP = 0.2  # tab inner face to the lid's slot face
BUMP = 1.1  # bump height off the tab's inner face; engagement = BUMP - LID_SLOT_GAP
BUMP_Z = 3.0  # bump's flat underside above the parting plane
BUMP_FLAT = 0.6
LATCH_LIFT_PLAY = 0.2  # bump underside to the notch floor
NOTCH_CLEAR = 0.2
BOSS = 1.2  # wall behind the tab pocket, inside the cavity
GROOVE = 0.5  # nail groove depth on the tab's outer face
RELEASE = BUMP - LID_SLOT_GAP + 0.2  # bump travel the release check uses

# Divider
DIVIDER_X = 21.0  # the core slot pair it slides into
DIVIDER_CLEAR = 0.3

EPS = 1e-6
SETTLE = 0.05
LATCH_LIFT = 0.3
_MIN_Z = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class Frame:
    """Derived heights and planes of one pocket box size."""

    size: BoxSize

    @property
    def width(self) -> float:
        return self.size.width

    @property
    def depth(self) -> float:
        return self.size.depth

    @property
    def lip_top(self) -> float:
        return self.size.lip_top

    @property
    def split(self) -> float:
        """Parting plane: base rim = lid underside."""
        return self.lip_top - LID_HEIGHT

    @property
    def axis_y(self) -> float:
        return self.depth / 2 - KNUCKLE_R

    @property
    def axis_z(self) -> float:
        return self.split + KNUCKLE_R

    @property
    def lid_floor(self) -> float:
        return self.size.h * HEIGHT_UNIT - STACK_CLEARANCE

    @property
    def recess_bottom(self) -> float:
        return self.axis_z - RECESS_BELOW_AXIS

    @property
    def wall_reach(self) -> float:
        """How far back the set-in back wall reaches to join the full wall below the recess."""
        return self.depth / 2 - WALL + 0.2

    @property
    def slope_z(self) -> float:
        """Bottom of the set-in back wall's 45 deg underside (it rises toward the front)."""
        run = self.wall_reach - (self.axis_y - WALL)
        return min(self.recess_bottom - 0.5, self.split - run - 0.5)

    @property
    def front(self) -> float:
        return -self.depth / 2

    @property
    def tab_root(self) -> float:
        return self.split - TAB_ROOT_BELOW

    def segments(self) -> list[tuple[str, float, float]]:
        """Knuckles along X as (owner, x0, x1), alternating base / lid, base at both ends."""
        length = (self.width - (KNUCKLES - 1) * AXIAL_CLEAR) / KNUCKLES
        x = -self.width / 2
        result = []
        for i in range(KNUCKLES):
            result.append(("base" if i % 2 == 0 else "lid", x, x + length))
            x += length + AXIAL_CLEAR
        return result


def _yz_prism(points: list[tuple[float, float]], x0: float, x1: float) -> Part:
    """Extrude a (y, z) outline along X from x0 to x1."""
    return Pos(x0, 0, 0) * extrude(Plane.YZ * Polygon(*points), amount=x1 - x0, dir=(1, 0, 0))


def _x_cylinder(radius: float, x0: float, x1: float, y: float, z: float) -> Part:
    length = x1 - x0
    return Pos((x0 + x1) / 2, y, z) * (Rot(0, 90, 0) * Cylinder(radius, length))


def _span_box(x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Part:
    center = Pos((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2)
    return center * Box(x[1] - x[0], y[1] - y[0], z[1] - z[0])


def _outline(f: Frame, z0: float, z1: float) -> Part:
    return Pos(0, 0, z0) * extrude(RectangleRounded(f.width, f.depth, OUTER_RADIUS), z1 - z0)


def _knuckle_profile(f: Frame, x0: float, x1: float) -> Part:
    """Base knuckle: upper half disk + a foot down to the wall top, 45 deg chamfer behind."""
    r, ay, az = KNUCKLE_R, f.axis_y, f.axis_z
    disk = Plane.YZ * Pos(ay, az) * Circle(r)
    back_low = Plane.YZ * Pos(ay + r / 2 + 0.5, az - r / 2 - 0.5) * Rectangle(r + 1, r + 1)
    foot = Plane.YZ * Polygon(
        (ay - r, az),
        (ay - WALL, f.split - 0.01),
        (ay, f.split - 0.01),
        (ay + r, az),
    )
    face = (disk - back_low) + foot
    return Pos(x0, 0, 0) * extrude(face, amount=x1 - x0, dir=(1, 0, 0))


def _lid_notch(f: Frame, x0: float, x1: float) -> Part:
    """Room in the lid for a base knuckle: its profile grown by RADIAL_CLEAR."""
    r, c, ay, az = KNUCKLE_R, RADIAL_CLEAR, f.axis_y, f.axis_z
    grown = c + 0.05
    disk = Plane.YZ * Pos(ay, az) * Circle(r + c)
    front = Plane.YZ * Polygon(
        (ay - r - grown, az),
        (ay - WALL - grown, az - r - 1.0),
        (ay, az - r - 1.0),
        (ay, az),
    )
    return Pos(x0, 0, 0) * extrude(disk + front, amount=x1 - x0, dir=(1, 0, 0))


def _back_wall(f: Frame) -> Part:
    """The base's back wall where it is set in to the axis, sloped 45 deg below so it prints."""
    reach, front = f.wall_reach, f.axis_y - WALL
    points = [
        (front, f.split),
        (f.axis_y, f.split),
        (f.axis_y, f.recess_bottom),
        (reach, f.recess_bottom),
        (reach, f.slope_z),
        (front, f.slope_z + reach - front),
    ]
    wall = _yz_prism(points, -f.width / 2, f.width / 2)
    return wall & _outline(f, 0, f.split)


def _tab(f: Frame, flexed: float = 0.0) -> Part:
    """Latch tab with its bump and nail groove; ``flexed`` swings it outward by that many deg."""
    y0, z0, top = f.front, f.tab_root, f.split + TAB_TOP_ABOVE
    yt = y0 + TAB_THICKNESS
    half = TAB_WIDTH / 2
    tab = _span_box((-half, half), (y0, yt), (z0 - 0.01, top))
    zb = f.split + BUMP_Z
    bump = [
        (yt - 0.1, zb),
        (yt + BUMP, zb),
        (yt + BUMP, zb + BUMP_FLAT),
        (yt, zb + BUMP_FLAT + BUMP),
        (yt - 0.1, zb + BUMP_FLAT + BUMP),
    ]
    tab += _yz_prism(bump, -half, half)
    zg = top - 1.4
    groove = [(y0 - 0.01, zg - GROOVE), (y0 + GROOVE, zg), (y0 - 0.01, zg + GROOVE)]
    tab -= _yz_prism(groove, -half - 0.1, half + 0.1)
    if flexed:
        hinge = Pos(0, y0, z0) * Rot(flexed, 0, 0) * Pos(0, -y0, -z0)
        tab = hinge * tab
    return tab


def _latch_cuts_base(f: Frame) -> tuple[Part, Part]:
    """(pocket the tab stands in, boss that closes the pocket toward the cavity)."""
    half = TAB_WIDTH / 2 + TAB_SIDE_GAP
    back = f.front + TAB_THICKNESS + TAB_BACK_GAP
    pocket = _span_box((-half, half), (f.front - 0.01, back), (f.tab_root, f.split + 0.01))
    boss = _span_box(
        (-half - BOSS, half + BOSS), (f.front + WALL - 0.01, back + BOSS), (FLOOR_Z, f.split)
    )
    return pocket, boss


def _latch_cuts_lid(f: Frame) -> Part:
    """Front slot for the tab, the notch the bump clicks into, open above for the nail."""
    half = TAB_WIDTH / 2 + TAB_SIDE_GAP
    face = f.front + TAB_THICKNESS + LID_SLOT_GAP
    slot = _span_box((-half, half), (f.front - 0.01, face), (f.split - 0.01, f.lip_top + 0.01))
    floor = f.split + BUMP_Z - LATCH_LIFT_PLAY
    deep = f.front + TAB_THICKNESS + BUMP + NOTCH_CLEAR
    flat_top = f.split + BUMP_Z + BUMP_FLAT + NOTCH_CLEAR
    chamfer_top = flat_top + (deep - face)
    notch = [(face - 0.01, floor), (deep, floor), (deep, flat_top), (face - 0.01, chamfer_top)]
    slot += _yz_prism(notch, -half, half)
    above = _span_box(
        (-half, half), (f.front - 0.01, f.front + WALL + 0.01), (chamfer_top, f.lip_top + 0.01)
    )
    return slot + above


def _base_body(size: BoxSize, recess: bool) -> Part:
    """The base without its latch tab."""
    f = Frame(size)
    base = make_box(size, label=False) & _span_box(
        (-f.width, f.width), (-f.depth, f.depth), (-1.0, f.split)
    )
    if recess:
        base -= _span_box(
            (-f.width, f.width), (f.axis_y, f.depth), (f.recess_bottom, f.split + 1.0)
        )
        base += _back_wall(f)
    knuckles = None
    for owner, x0, x1 in f.segments():
        if owner == "lid":
            base -= _x_cylinder(
                KNUCKLE_R + RADIAL_CLEAR, x0 - AXIAL_CLEAR, x1 + AXIAL_CLEAR, f.axis_y, f.axis_z
            )
        else:
            k = _knuckle_profile(f, x0, x1)
            knuckles = k if knuckles is None else knuckles + k
    base += knuckles & _outline(f, 0, f.lip_top)
    base -= _x_cylinder(PIN_HOLE_BASE / 2, -f.width, f.width, f.axis_y, f.axis_z)
    pocket, boss = _latch_cuts_base(f)
    return base - pocket + boss


def make_base(size: BoxSize, recess: bool = True, bump: bool = True) -> Part:
    """Pocket box base: the core crate up to the parting plane, hinge knuckles, latch tab.

    Args:
        size: footprint and closed height (the lid carries the lip at 7 * h + 4).
        recess: cut the hinge recess behind the axis (False only for the negative control).
        bump: give the latch tab its bump (False only for the negative control).
    """
    f = Frame(size)
    tab = _tab(f)
    if not bump:
        tab &= _span_box((-f.width, f.width), (f.front, f.front + TAB_THICKNESS), (0, f.lip_top))
    return _base_body(size, recess) + tab


def make_base_released(size: BoxSize, recess: bool = True) -> Part:
    """The base with its latch tab pulled out by RELEASE at the bump (the opening position)."""
    return _base_body(size, recess) + _tab(Frame(size), flexed=release_angle(size))


def release_angle(size: BoxSize) -> float:
    """Tab swing (deg, outward) that moves the bump's tip RELEASE toward the user."""
    f = Frame(size)
    arm = f.split + BUMP_Z - f.tab_root
    return math.degrees(math.asin(RELEASE / arm))


def make_lid(size: BoxSize) -> Part:
    """Pocket box lid in its closed position (z from the parting plane to the lip top)."""
    f = Frame(size)
    lid = _outline(f, f.split, f.lip_top)
    lid -= lip_pocket(size)
    cav_w, cav_d, _ = size.cavity
    lid -= Pos(0, 0, f.lid_floor) * extrude(
        RectangleRounded(cav_w, cav_d, OUTER_RADIUS - WALL), amount=f.lip_top
    )
    r, ay, az = KNUCKLE_R, f.axis_y, f.axis_z
    below_chord = [
        (ay, f.split - 1),
        (ay, f.split),
        (ay + r + 1, az + 1),
        (ay + r + 1, f.split - 1),
    ]
    lid -= _yz_prism(below_chord, -f.width, f.width)
    for owner, x0, x1 in f.segments():
        if owner == "base":
            lid -= _lid_notch(f, x0 - AXIAL_CLEAR, x1 + AXIAL_CLEAR)
    lid -= _x_cylinder(PIN_HOLE_LID / 2, -f.width, f.width, ay, az)
    lid -= _latch_cuts_lid(f)
    lid -= Pos(0, 0, f.lid_floor - LABEL_DEPTH / 2 + 0.01) * Box(
        label_width(f.width), LABEL_HEIGHT, LABEL_DEPTH + 0.02
    )
    return lid


def make_pin(size: BoxSize) -> Part:
    """The hinge pin: 1.75 mm filament, PIN_INSET short of each side face, on the axis."""
    f = Frame(size)
    half = f.width / 2 - PIN_INSET
    return _x_cylinder(PIN_D / 2, -half, half, f.axis_y, f.axis_z)


def pin_length(size: BoxSize) -> float:
    return size.width - 2 * PIN_INSET


def lid_pose(size: BoxSize, angle: float) -> Location:
    """Location that opens the closed lid by ``angle`` deg about the hinge axis."""
    f = Frame(size)
    return Pos(0, f.axis_y, f.axis_z) * Rot(-angle, 0, 0) * Pos(0, -f.axis_y, -f.axis_z)


def lid_placement(size: BoxSize, angle: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(pos, rot) that places the EXPORTED lid (underside at z = 0) open by ``angle`` deg."""
    f = Frame(size)
    loc = lid_pose(size, angle) * Pos(0, 0, f.split)
    pos = tuple(round(v, 4) for v in loc.position)
    rot = tuple(round(v, 4) for v in loc.orientation)
    return pos, rot


def _divider_profile(f: Frame) -> list[tuple[float, float]]:
    """Divider outline as (along Y, up from the floor), following the back wall's slope."""
    _, cav_d, _ = f.size.cavity
    reach = cav_d / 2 + DIVIDER_SLOT_DEPTH - 0.2
    lift = DIVIDER_CLEAR * math.sqrt(2)

    def slope(y: float) -> float:
        return f.slope_z + (f.wall_reach - y) - lift - FLOOR_Z

    face = f.axis_y - WALL - DIVIDER_CLEAR
    top = f.split - DIVIDER_CLEAR - FLOOR_Z
    return [
        (-reach, 0.0),
        (reach, 0.0),
        (reach, slope(reach)),
        (face, slope(face)),
        (face, top),
        (-reach, top),
    ]


def make_divider(size: BoxSize) -> Part:
    """Divider plate for the slot pair at x = DIVIDER_X; local XZ profile, flat on its -Y face."""
    f = Frame(size)
    plate = extrude(
        Plane.XZ * Polygon(*_divider_profile(f)), amount=DIVIDER_THICKNESS / 2, both=True
    )
    return Pos(0, DIVIDER_THICKNESS / 2, 0) * plate


def divider_placement(
    size: BoxSize,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """(pos, rot) of the exported divider standing in its slots."""
    return (DIVIDER_X + DIVIDER_THICKNESS / 2, 0.0, FLOOR_Z), (0.0, 0.0, 90.0)


def _placed_divider(size: BoxSize) -> Part:
    pos, rot = divider_placement(size)
    return Pos(*pos) * Rot(*rot) * make_divider(size)


def dev_board(
    length: float, width: float, pcb: float, row_gap: float, top: tuple[float, float, float]
) -> Part:
    """A dev board with male headers soldered pins-down, standing on its pin tips at z = 0.

    Args:
        length: PCB length along X.
        width: PCB width along Y.
        pcb: PCB thickness.
        row_gap: center distance of the two header rows (along Y).
        top: (length, width, height) of the tallest part on top (module can / USB).
    """
    plastic, pins = 2.5, 6.0
    run = length - 4.0
    board = Pos(0, 0, pins + plastic) * Box(length, width, pcb, align=_MIN_Z)
    for sy in (-1, 1):
        y = sy * row_gap / 2
        board += Pos(0, y, pins) * Box(run, 2.5, plastic, align=_MIN_Z)
        board += Pos(0, y, 0) * Box(run, 0.64, pins + 0.01, align=_MIN_Z)
    tl, tw, th = top
    board += Pos(length / 2 - tl / 2 - 1.0, 0, pins + plastic + pcb - 0.01) * Box(
        tl, tw, th + 0.01, align=_MIN_Z
    )
    return board


def esp32_devkit() -> Part:
    """ESP32 DevKitC V4: 55 x 28 mm, rows 25.4 mm apart, WROOM can 18 x 25.5 x 3.2 on top."""
    return dev_board(55.0, 28.0, 1.6, 25.4, (18.0, 25.5, 3.2))


def pico() -> Part:
    """Raspberry Pi Pico: 51 x 21 mm, rows 17.78 mm apart, USB connector 8 x 8 x 2.7."""
    return dev_board(51.0, 21.0, 1.0, 17.78, (8.0, 8.0, 2.7))


BOARD_SPOTS = {
    # size -> [(board name, x, y)] with the board standing on the cavity floor
    (2, 1): [("esp32", -9.5, 0.0)],
    (2, 2): [("esp32", -9.5, -18.0), ("pico", -11.5, 18.0)],
}
ALTERNATE_SPOTS = {(2, 1): [("pico", -11.5, 0.0)], (2, 2): []}  # checked one at a time
BOARDS = {"esp32": esp32_devkit, "pico": pico}


def placed_boards(size: BoxSize, alternates: bool = False) -> list[tuple[str, Part]]:
    """Boards in their spots on the cavity floor (``alternates``: the other boards checked)."""
    spots = (ALTERNATE_SPOTS if alternates else BOARD_SPOTS)[(size.nx, size.ny)]
    return [(name, Pos(x, y, FLOOR_Z) * BOARDS[name]()) for name, x, y in spots]


def tag(size: BoxSize) -> str:
    return f"{size.nx}x{size.ny}x{size.h}"


# --- verification -------------------------------------------------------------------------


def _hit(a: Part, b: Part) -> float:
    common = a & b
    return common.volume if common else 0.0


def _line(passed: bool, text: str) -> bool:
    print(f"  [{'PASS' if passed else 'FAIL'}] {text}")
    return passed


def _check_valid(size: BoxSize, parts: dict[str, Part]) -> bool:
    ok = True
    for name, part in parts.items():
        bb = part.bounding_box()
        ok &= _line(
            part.is_valid and len(part.solids()) == 1,
            f"{tag(size)} {name}: valid, {len(part.solids())} solid, "
            f"{bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm",
        )
    return ok


def _check_closed(size: BoxSize, base: Part, lid: Part, pin: Part) -> bool:
    worst = max(_hit(lid, base), _hit(lid, pin), _hit(base, pin))
    return _line(
        worst < EPS,
        f"{tag(size)} closed: lid & base, lid & pin, base & pin = {worst:.6f} mm3",
    )


def sweep(size: BoxSize, base: Part, lid: Part, pin: Part, stop: float) -> tuple[float, float]:
    """Open the lid in SWEEP_STEP steps up to ``stop``; (worst overlap, first colliding angle)."""
    worst, first = 0.0, math.nan
    steps = int(round(stop / SWEEP_STEP))
    for i in range(steps + 1):
        angle = i * SWEEP_STEP
        moved = lid_pose(size, angle) * lid
        v = _hit(moved, base) + _hit(moved, pin)
        worst = max(worst, v)
        if v > EPS and math.isnan(first):
            first = angle
    return worst, first


def _check_hinge(size: BoxSize, lid: Part, pin: Part) -> bool:
    released = make_base_released(size)
    worst, _ = sweep(size, released, lid, pin, OPEN_ANGLE)
    ok = _line(
        worst < EPS,
        f"{tag(size)} hinge sweep 0..{OPEN_ANGLE:.0f} deg every {SWEEP_STEP:.0f} deg "
        f"(tab released): worst overlap {worst:.6f} mm3",
    )
    rest = make_base(size)
    free = max(_hit(lid_pose(size, a) * lid, rest) for a in (15.0, 30.0, 60.0, 90.0, OPEN_ANGLE))
    ok &= _line(free < EPS, f"{tag(size)} tab sprung back, lid at 15..110 deg: {free:.6f} mm3")
    stop = OPEN_ANGLE
    while stop < 180.0:
        stop += SWEEP_STEP
        if _hit(lid_pose(size, stop) * lid, released) > EPS:
            break
    behind = (lid_pose(size, OPEN_ANGLE) * lid).bounding_box().max.Y - size.depth / 2
    print(
        f"  [INFO] {tag(size)} lid comes to rest on the back recess at {stop:.0f} deg; at "
        f"{OPEN_ANGLE:.0f} deg it reaches {behind:.1f} mm behind the back face"
    )
    return ok


def _latch_zone(f: Frame) -> Part:
    half = TAB_WIDTH / 2 + TAB_SIDE_GAP + 0.5
    return _span_box((-half, half), (f.front - 2, f.front + 6), (f.tab_root, f.lip_top))


def _check_latch(size: BoxSize, base: Part, lid: Part) -> bool:
    f = Frame(size)
    zone = _latch_zone(f)
    lifted = Pos(0, 0, LATCH_LIFT) * lid
    held = _hit(lifted & zone, base)
    ok = _line(
        held > EPS,
        f"{tag(size)} latch holds: lid lifted {LATCH_LIFT} mm hits the tab bump, {held:.3f} mm3",
    )
    opened = lid_pose(size, 3.0) * lid
    at_latch = _hit(opened & zone, base)
    elsewhere = _hit(opened - zone, base)
    ok &= _line(
        at_latch > EPS and elsewhere < EPS,
        f"{tag(size)} latch blocks opening: 3 deg open hits {at_latch:.3f} mm3 at the latch, "
        f"{elsewhere:.6f} mm3 elsewhere",
    )
    released = make_base_released(size)
    clear = max(_hit(lid, released), _hit(lifted, released & zone))
    ok &= _line(
        clear < EPS,
        f"{tag(size)} latch releases: tab pulled {RELEASE:.1f} mm at the bump "
        f"({release_angle(size):.1f} deg), lid closed / lifted overlap {clear:.6f} mm3",
    )
    return ok


def latch_strain(size: BoxSize) -> tuple[float, float, float]:
    """(tab length, tip deflection, root strain) for RELEASE at the bump, tip-loaded beam."""
    f = Frame(size)
    length = f.split + TAB_TOP_ABOVE - f.tab_root
    at = (f.split + BUMP_Z - f.tab_root) / length
    shape = at * at * (3 - at) / 2
    tip = RELEASE / shape
    return length, tip, 1.5 * TAB_THICKNESS * tip / length**2


def _check_stack(size: BoxSize, closed: tuple[Part, Part, Part]) -> bool:
    """Closed box on a 3-unit crate; a 2-unit crate and a cap on the closed lid."""
    lower = make_box(BoxSize(size.nx, size.ny, 3))
    seat = 3 * HEIGHT_UNIT
    ok = True
    on, low = 0.0, 0.0
    for part in closed:
        on += _hit(lower, Pos(0, 0, seat) * part)
        low += _hit(lower, Pos(0, 0, seat - SETTLE) * part)
    ok &= _line(
        on < EPS and low > EPS,
        f"{tag(size)} on a crate lip at z={seat:.0f}: {on:.6f} mm3, lowered {SETTLE} mm "
        f"{low:.2f} mm3",
    )
    above = size.h * HEIGHT_UNIT
    for name, upper in (
        ("crate", make_box(BoxSize(size.nx, size.ny, 2))),
        ("cap", make_cap(size.nx, size.ny)),
    ):
        on = sum(_hit(part, Pos(0, 0, above) * upper) for part in closed)
        low = sum(_hit(part, Pos(0, 0, above - SETTLE) * upper) for part in closed)
        ok &= _line(
            on < EPS and low > EPS,
            f"{tag(size)} {name} on the closed lid at z={above:.0f}: {on:.6f} mm3, lowered "
            f"{SETTLE} mm {low:.2f} mm3",
        )
    return ok


def _check_contents(size: BoxSize, base: Part, lid: Part, divider: Part) -> bool:
    f = Frame(size)
    ok = True
    for name, board in placed_boards(size) + placed_boards(size, alternates=True):
        v = _hit(board, base) + _hit(board, lid) + _hit(board, divider)
        head = f.split - board.bounding_box().max.Z
        ok &= _line(
            v < EPS,
            f"{tag(size)} {name} with headers inside, lid closed: {v:.6f} mm3, "
            f"{head:.1f} mm above it",
        )
    v = _hit(divider, base) + _hit(divider, lid)
    ok &= _line(v < EPS, f"{tag(size)} divider in the x={DIVIDER_X:.0f} slots: {v:.6f} mm3")
    return ok


def _negative_controls(size: BoxSize, lid: Part, pin: Part) -> bool:
    """A base without the hinge recess must jam the lid; a tab without a bump must not hold."""
    flat = make_base_released(size, recess=False)
    _, first = sweep(size, flat, lid, pin, OPEN_ANGLE)
    caught_hinge = not math.isnan(first)
    print(
        f"  [{'PASS' if caught_hinge else 'FAIL'}] NEGATIVE {tag(size)} base without the "
        f"hinge recess (tab released): lid jams at {first:.0f} deg "
        f"({'caught' if caught_hinge else 'NOT CAUGHT'})"
    )
    f = Frame(size)
    smooth = make_base(size, bump=False)
    held = _hit((Pos(0, 0, LATCH_LIFT) * lid) & _latch_zone(f), smooth)
    caught_latch = held < EPS
    print(
        f"  [{'PASS' if caught_latch else 'FAIL'}] NEGATIVE {tag(size)} tab without its bump: "
        f"lid lifts {LATCH_LIFT} mm with {held:.6f} mm3 at the latch "
        f"({'caught' if caught_latch else 'NOT CAUGHT'})"
    )
    return caught_hinge and caught_latch


def verify() -> bool:
    """Validity, closed fit, hinge sweep, latch hold/release, stacking, contents, negatives."""
    ok = True
    for size in SIZES:
        base, lid, pin = make_base(size), make_lid(size), make_pin(size)
        divider = _placed_divider(size)
        parts = {"base": base, "lid": lid, "divider": make_divider(size), "pin": pin}
        ok &= _check_valid(size, parts)
        ok &= _check_closed(size, base, lid, pin)
        ok &= _check_hinge(size, lid, pin)
        ok &= _check_latch(size, base, lid)
        length, tip, strain = latch_strain(size)
        print(
            f"  [INFO] {tag(size)} latch tab {length:.1f} x {TAB_WIDTH:.0f} x {TAB_THICKNESS} mm: "
            f"{tip:.2f} mm at the tip to release, root strain {strain * 100:.2f} %"
        )
        ok &= _check_stack(size, (base, lid, pin))
        ok &= _check_contents(size, base, lid, divider)
        ok &= _negative_controls(size, lid, pin)
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return ok


def build() -> None:
    """Export base, lid and divider for every size into models/pocket/."""
    for size in SIZES:
        f = Frame(size)
        t = tag(size)
        foot = f"{size.nx}x{size.ny}"
        length, tip, strain = latch_strain(size)
        save(
            MODULE,
            make_base(size),
            PartInfo(
                slug=f"pocket-base-{t}",
                title=f"Pocket box base {t}",
                blurb=(
                    f"Carry box with Stakee feet: {f.split - FLOOR_Z:.0f} mm deep inside, three "
                    "hinge knuckles at the back, a snap tab at the front. Closed with its lid it "
                    f"stacks like a {t} crate."
                ),
                material="PETG (the latch tab flexes; PLA tabs crack)",
                print_notes=(
                    "Upright on its feet, no supports: the knuckles and the back recess are "
                    "chamfered 45 deg. 4 walls so the 1.6 mm tab is solid perimeters. Optional "
                    "6x2 mm magnets."
                ),
                color="#e8e3d6",
                footprint=t,
            ),
        )
        save(
            MODULE,
            Pos(0, 0, -f.split) * make_lid(size),
            PartInfo(
                slug=f"pocket-lid-{foot}",
                title=f"Pocket box lid {foot}",
                blurb=(
                    "Hinged lid with two knuckles at the back, a notch the latch clicks into, "
                    "a full stacking lip on top and a label recess in its floor."
                ),
                material="PETG",
                print_notes=(
                    "On its flat underside, no supports (knuckle chamfers 45 deg). Hinge: push "
                    f"a {pin_length(size):.1f} mm length of 1.75 mm filament through all five "
                    "knuckles from one side."
                ),
                color="#f2a03d",
                footprint=foot,
            ),
        )
        save(
            MODULE,
            make_divider(size),
            PartInfo(
                slug=f"pocket-divider-{foot}",
                title=f"Pocket box divider {foot}",
                blurb=(
                    f"Plate for the slots at x = {DIVIDER_X:.0f} mm: a cable bay beside the board."
                ),
                material="PLA or PETG",
                print_notes="Flat, no supports.",
                color="#f2f2f2",
            ),
        )
    print(
        f"latch: tab {length:.1f} mm, {tip:.2f} mm tip travel to release, "
        f"{strain * 100:.2f} % root strain"
    )


if __name__ == "__main__":
    if not verify():
        raise SystemExit("pocket verification failed; nothing exported")
    build()
