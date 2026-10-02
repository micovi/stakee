"""Stakee core geometry: the shared contract every module builds on.

Coordinate system: X = width, Y = depth (front face is -Y), Z = up.
Every part is centered on the XY origin with its lowest point at z = 0.

Grid: 42 mm footprint units, 7 mm height units (Gridfinity-compatible feet).
A box of height ``h`` units stacks onto the box below with a pitch of exactly
``7 * h`` mm: its feet drop into the lower box's stacking lip and seat on the
45 deg chamfers, leaving a 0.75 mm shadow gap between the bodies.
"""

from dataclasses import dataclass

from build123d import (
    Align,
    Box,
    Cylinder,
    Part,
    Plane,
    Pos,
    RectangleRounded,
    extrude,
    loft,
)

GRID = 42.0
HEIGHT_UNIT = 7.0
GAP = 0.25  # clearance per side between neighbouring cells
OUTER_RADIUS = 3.75
WALL = 2.0
FLOOR_Z = 5.5  # top of the solid floor, local z
FOOT_HEIGHT = 4.75
# Gridfinity foot profile as (z, inset from cell outline) stations.
FOOT_STATIONS = ((0.0, 2.95), (0.8, 2.15), (2.6, 2.15), (4.75, 0.0))
LIP_CLEARANCE = 0.25  # horizontal clearance between foot and lip chamfers
LIP_ABOVE_NOMINAL = 4.0  # lip top sits this far above 7 * h
SEAT_DEPTH = 4.0  # how deep an upper box's feet sink below the lower lip top

MAGNET_DIAMETER = 6.5
MAGNET_DEPTH = 2.4
MAGNET_OFFSET = 13.0  # from cell center, both axes

DIVIDER_SLOT_WIDTH = 1.6
DIVIDER_SLOT_DEPTH = 0.8
DIVIDER_THICKNESS = 1.2  # slides into a DIVIDER_SLOT_WIDTH slot

# Clip sockets are horizontal L (bayonet) pockets: a window open to the outside plus a leg
# that runs on along the face behind a thin skin. A clip nub enters the window, then the clip
# slides along Y so its hook sits behind the skin and cannot be pulled straight off.
# On the +X face the leg runs toward +Y, on the -X face toward -Y (the clip is rotated 180°).
CLIP_SOCKET_OPENING = 7.4  # window length along the face
CLIP_SOCKET_LEG = 5.0  # hidden leg length along the face
CLIP_SOCKET_WIDTH = CLIP_SOCKET_OPENING + CLIP_SOCKET_LEG  # total footprint along Y
CLIP_SOCKET_HEIGHT = 1.6  # along Z
CLIP_SOCKET_DEPTH = 1.4  # into the wall, along X (leaves a 0.55 mm hook)
CLIP_SOCKET_SKIN = 0.6  # wall left in front of the leg
CLIP_SOCKET_INSET = 12.0  # socket center from the front/back outer face
CLIP_SOCKET_LIP_Z = 2.0  # socket center, measured down from the lip top
CLIP_SOCKET_BASE_Z = 6.5  # socket center, local z near the bottom of the body

LABEL_HEIGHT = 12.0
LABEL_DEPTH = 0.6
LABEL_MAX_WIDTH = 60.0
LABEL_MIN_HEIGHT_UNITS = 3  # lower boxes have no room for a front label
LABEL_TOP_OFFSET = 1.5  # label recess top, below the stacking seat


@dataclass(frozen=True)
class BoxSize:
    """Footprint in grid units and height in 7 mm units."""

    nx: int
    ny: int
    h: int

    @property
    def width(self) -> float:
        return self.nx * GRID - 2 * GAP

    @property
    def depth(self) -> float:
        return self.ny * GRID - 2 * GAP

    @property
    def lip_top(self) -> float:
        return self.h * HEIGHT_UNIT + LIP_ABOVE_NOMINAL

    @property
    def cavity(self) -> tuple[float, float, float]:
        """Usable interior (width, depth, height) below the stacking seat."""
        usable_h = self.lip_top - SEAT_DEPTH - FLOOR_Z
        return (self.width - 2 * WALL, self.depth - 2 * WALL, usable_h)


def _rounded_section(width: float, depth: float, inset: float, z: float):
    radius = max(OUTER_RADIUS - inset, 0.4)
    return Plane.XY.offset(z) * RectangleRounded(width - 2 * inset, depth - 2 * inset, radius)


def profile_solid(width: float, depth: float, stations: tuple[tuple[float, float], ...]) -> Part:
    """Stack ruled lofts/extrusions through (z, inset) stations of a rounded rectangle."""
    pieces = []
    for (z0, i0), (z1, i1) in zip(stations, stations[1:], strict=False):
        if i0 == i1:
            pieces.append(extrude(_rounded_section(width, depth, i0, z0), amount=z1 - z0))
        else:
            pieces.append(
                loft(
                    [
                        _rounded_section(width, depth, i0, z0),
                        _rounded_section(width, depth, i1, z1),
                    ],
                    ruled=True,
                )
            )
    solid = pieces[0]
    for piece in pieces[1:]:
        solid += piece
    return solid


def cell_centers(nx: int, ny: int) -> list[tuple[float, float]]:
    return [
        ((i - (nx - 1) / 2) * GRID, (j - (ny - 1) / 2) * GRID) for i in range(nx) for j in range(ny)
    ]


def feet(nx: int, ny: int, magnets: bool = True) -> Part:
    """Per-cell Gridfinity feet, optionally with 6x2 mm magnet pockets underneath."""
    cell = GRID - 2 * GAP
    one_foot = profile_solid(cell, cell, FOOT_STATIONS)
    result = None
    for cx, cy in cell_centers(nx, ny):
        placed = Pos(cx, cy, 0) * one_foot
        result = placed if result is None else result + placed
    if magnets:
        for cx, cy in cell_centers(nx, ny):
            for sx in (-1, 1):
                for sy in (-1, 1):
                    result -= Pos(cx + sx * MAGNET_OFFSET, cy + sy * MAGNET_OFFSET, 0) * Cylinder(
                        MAGNET_DIAMETER / 2,
                        MAGNET_DEPTH,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                    )
    return result


def lip_pocket(size: BoxSize, clearance: float = LIP_CLEARANCE) -> Part:
    """The cut that forms the stacking lip: the foot envelope, clearance-expanded.

    The foot is lifted by ``clearance`` and grown by it horizontally, so on the 45 deg
    chamfers it still seats exactly at ``lip_top - SEAT_DEPTH`` (stack pitch stays 7 * h);
    only the play on the vertical faces changes.
    """
    min_clearance = FOOT_STATIONS[1][1] - WALL
    if not min_clearance <= clearance < 1.0:
        raise ValueError(
            f"lip clearance {clearance} mm out of range: below {min_clearance:.2f} mm the cavity "
            "wall, not the lip, sets the play; use 0.15-0.99 mm"
        )
    z0 = size.lip_top - SEAT_DEPTH + clearance
    stations = [
        (z0 + foot_z, foot_inset - clearance)
        for foot_z, foot_inset in FOOT_STATIONS
        if z0 + foot_z < size.lip_top
    ]
    top_inset = _foot_inset_at(size.lip_top - z0) - clearance
    stations.append((size.lip_top, top_inset))
    stations.append((size.lip_top + 1.0, top_inset))
    return profile_solid(size.width, size.depth, tuple(stations))


def _foot_inset_at(foot_z: float) -> float:
    for (z0, i0), (z1, i1) in zip(FOOT_STATIONS, FOOT_STATIONS[1:], strict=False):
        if z0 <= foot_z <= z1:
            return i0 + (i1 - i0) * (foot_z - z0) / (z1 - z0)
    raise ValueError(f"foot_z {foot_z} outside the foot profile (0..{FOOT_HEIGHT})")


def divider_slot_positions(n: int) -> list[float]:
    """Centers of the divider slots along an axis that is ``n`` grid units long (every 21 mm)."""
    return [k * GRID / 2 - n * GRID / 2 for k in range(1, 2 * n)]


def _divider_slots(size: BoxSize) -> Part:
    cav_w, cav_d, _ = size.cavity
    # Slots run out through the lip: a plate reaches 0.6 mm into its slots, so a slot that
    # stopped at the seat would leave a band of wall that blocks dropping it straight in.
    slot_h = size.lip_top + 1.0 - FLOOR_Z
    cuts = None
    for x in divider_slot_positions(size.nx):
        for sy in (-1, 1):
            y = sy * (cav_d / 2 + DIVIDER_SLOT_DEPTH / 2)
            slot = Pos(x, y, FLOOR_Z) * Box(
                DIVIDER_SLOT_WIDTH,
                DIVIDER_SLOT_DEPTH + 0.02,
                slot_h,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
            cuts = slot if cuts is None else cuts + slot
    for y in divider_slot_positions(size.ny):
        for sx in (-1, 1):
            x = sx * (cav_w / 2 + DIVIDER_SLOT_DEPTH / 2)
            slot = Pos(x, y, FLOOR_Z) * Box(
                DIVIDER_SLOT_DEPTH + 0.02,
                DIVIDER_SLOT_WIDTH,
                slot_h,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
            cuts = slot if cuts is None else cuts + slot
    return cuts


def clip_socket_positions(size: BoxSize) -> list[tuple[float, float, float]]:
    """(x_face, y, z) centers of the clip sockets on the +/-X outer faces."""
    y = size.depth / 2 - CLIP_SOCKET_INSET
    positions = []
    for sx in (-1, 1):
        x = sx * size.width / 2
        for sy in (-1, 1):
            positions.append((x, sy * y, size.lip_top - CLIP_SOCKET_LIP_Z))
            positions.append((x, sy * y, CLIP_SOCKET_BASE_Z))
    return positions


def clip_socket_cut(x_face: float, y: float, z: float) -> Part:
    """The L-shaped cut for one socket centered at (x_face, y, z) on a +/-X outer face."""
    inward = -1 if x_face > 0 else 1
    slide = 1 if x_face > 0 else -1
    start = y - slide * CLIP_SOCKET_WIDTH / 2
    window_mid = start + slide * CLIP_SOCKET_OPENING / 2
    leg_mid = start + slide * (CLIP_SOCKET_OPENING + CLIP_SOCKET_LEG / 2)
    window_depth = CLIP_SOCKET_DEPTH + 0.02
    window = Pos(x_face + inward * (CLIP_SOCKET_DEPTH / 2 - 0.01), window_mid, z) * Box(
        window_depth, CLIP_SOCKET_OPENING, CLIP_SOCKET_HEIGHT
    )
    leg_depth = CLIP_SOCKET_DEPTH - CLIP_SOCKET_SKIN
    leg_x = x_face + inward * (CLIP_SOCKET_SKIN + leg_depth / 2)
    leg = Pos(leg_x, leg_mid, z) * Box(leg_depth, CLIP_SOCKET_LEG + 0.02, CLIP_SOCKET_HEIGHT)
    return window + leg


def clip_socket_cuts(size: BoxSize, lip: bool = True, base: bool = True) -> Part | None:
    """All socket cuts of a box: ``lip`` ones near the lip top, ``base`` ones near the bottom."""
    lip_z = size.lip_top - CLIP_SOCKET_LIP_Z
    cuts = None
    for x, y, z in clip_socket_positions(size):
        if (z == lip_z and not lip) or (z == CLIP_SOCKET_BASE_Z and not base):
            continue
        cut = clip_socket_cut(x, y, z)
        cuts = cut if cuts is None else cuts + cut
    return cuts


def label_width(width: float) -> float:
    """Label recess width for a box or cap of outer ``width``."""
    return min(width - 16.0, LABEL_MAX_WIDTH)


def label_z(size: BoxSize) -> float:
    """Center height of the front label recess of a box."""
    return size.lip_top - SEAT_DEPTH - LABEL_HEIGHT / 2 - LABEL_TOP_OFFSET


def label_recess(width: float, front_y: float, z_center: float) -> Part:
    label_w = label_width(width)
    return Pos(0, front_y + LABEL_DEPTH / 2 - 0.01, z_center) * Box(
        label_w, LABEL_DEPTH + 0.02, LABEL_HEIGHT
    )


def make_box(
    size: BoxSize,
    magnets: bool = True,
    dividers: bool = True,
    clip_sockets: bool = True,
    label: bool = True,
    lip_clearance: float = LIP_CLEARANCE,
) -> Part:
    """A stackable Stakee box: Gridfinity feet, open top, stacking lip.

    Args:
        size: footprint (nx, ny) in 42 mm units and height in 7 mm units (h >= 2).
        magnets: 6.5x2.4 mm magnet pockets under each foot.
        dividers: vertical slots on all inner walls every half cell (21 mm).
        clip_sockets: dimples on the side walls for stack clips.
        label: shallow label recess on the front face.
        lip_clearance: play between an upper box's feet and this lip (printer tuning).
    """
    if size.h < 2:
        raise ValueError(f"box height must be >= 2 units, got {size.h}; use make_cap() for lids")
    body = feet(size.nx, size.ny, magnets)
    body += Pos(0, 0, FOOT_HEIGHT) * extrude(
        RectangleRounded(size.width, size.depth, OUTER_RADIUS), amount=size.lip_top - FOOT_HEIGHT
    )
    cav_w, cav_d, _ = size.cavity
    body -= Pos(0, 0, FLOOR_Z) * extrude(
        RectangleRounded(cav_w, cav_d, OUTER_RADIUS - WALL), amount=size.lip_top
    )
    body -= lip_pocket(size, lip_clearance)
    if dividers:
        body -= _divider_slots(size)
    if clip_sockets:
        body -= clip_socket_cuts(size)
    if label and size.h >= LABEL_MIN_HEIGHT_UNITS:
        body -= label_recess(size.width, -size.depth / 2, label_z(size))
    return body


CAP_PLATE = 2.4
CAP_SHELL = 1.6


def make_cap(nx: int, ny: int, label: bool = True) -> Part:
    """A lid that seats into any box's stacking lip (one big hollow foot + top plate)."""
    width, depth = nx * GRID - 2 * GAP, ny * GRID - 2 * GAP
    cap = profile_solid(width, depth, FOOT_STATIONS)
    hollow_inset = FOOT_STATIONS[0][1] + CAP_SHELL
    cap -= extrude(
        RectangleRounded(width - 2 * hollow_inset, depth - 2 * hollow_inset, 1.0),
        amount=FOOT_HEIGHT,
    )
    cap += Pos(0, 0, FOOT_HEIGHT) * extrude(
        RectangleRounded(width, depth, OUTER_RADIUS), amount=CAP_PLATE
    )
    if label:
        top = FOOT_HEIGHT + CAP_PLATE
        label_w = label_width(width)
        cap -= Pos(0, 0, top - LABEL_DEPTH / 2 + 0.01) * Box(
            label_w, LABEL_HEIGHT, LABEL_DEPTH + 0.02
        )
    return cap
