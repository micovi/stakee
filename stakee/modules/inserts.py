"""Drop-in inserts: trays that sit on a crate floor and turn a generic crate into a kit.

Every insert is modelled in its own frame (centered on XY, bottom at z = 0) and is
meant to sit at z = FLOOR_Z inside the crate it names. Inserts keep CLEARANCE per side
to the cavity walls and stay below the stacking seat (``size.lip_top - SEAT_DEPTH``),
so a crate or cap still stacks on top.
"""

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    Box,
    Cylinder,
    FontStyle,
    Part,
    Pos,
    RectangleRounded,
    Rot,
    SlotCenterToCenter,
    Sphere,
    Text,
    chamfer,
    extrude,
    fillet,
)

from stakee.core import (
    FLOOR_Z,
    HEIGHT_UNIT,
    SEAT_DEPTH,
    BoxSize,
    make_box,
)
from stakee.export import PartInfo, save
from stakee.modules.crates import SIZES

MODULE = "inserts"

CLEARANCE = 0.3  # per side, insert outline to cavity wall
CORNER_RADIUS = 2.0  # >= cavity corner radius (1.75) so corners never bind
MIN = (Align.CENTER, Align.CENTER, Align.MIN)


def crate_size(nx: int, ny: int, h: int) -> BoxSize:
    """Return the crate size from crates.SIZES, failing loudly if it is not in the range.

    Args:
        nx: footprint width in grid units.
        ny: footprint depth in grid units.
        h: height in 7 mm units.

    Returns:
        The matching BoxSize.

    Raises:
        ValueError: if crates.SIZES has no such crate.
    """
    size = BoxSize(nx, ny, h)
    if size not in SIZES:
        raise ValueError(f"no crate {nx}x{ny}x{h} in crates.SIZES ({SIZES}); add it there first")
    return size


def tag(size: BoxSize) -> str:
    return f"{size.nx}x{size.ny}x{size.h}"


def seat_z(size: BoxSize) -> float:
    """Highest local insert z (above its own bottom) that stays below the stacking seat."""
    return size.lip_top - SEAT_DEPTH - FLOOR_Z


def tray_blank(size: BoxSize, height: float) -> Part:
    """Solid slab filling the crate cavity minus CLEARANCE per side, bottom at z = 0."""
    cav_w, cav_d, _ = size.cavity
    if height > seat_z(size):
        raise ValueError(f"insert height {height} exceeds seat height {seat_z(size)} for {size}")
    outline = RectangleRounded(cav_w - 2 * CLEARANCE, cav_d - 2 * CLEARANCE, CORNER_RADIUS)
    return extrude(outline, amount=height)


def deboss_text(label: str, x: float, y: float, top: float, size: float = 5.0) -> Part:
    """Bold text cut 0.6 mm down from the plane z = top (subtract the result)."""
    return extrude(
        Pos(x, y, top) * Text(label, font_size=size, font_style=FontStyle.BOLD), amount=-0.6
    )


# --------------------------------------------------------------------------- dev-board dock

DOCK_CRATE = crate_size(3, 2, 6)
DOCK_PLATE = 2.0
BOARD_Z = 12.0  # board underside; 10 mm under the board clears 8.5 mm male header tails
FENCE_WALL = 1.6
FENCE_GAP = 0.5  # board edge to fence, per side
FENCE_ABOVE_BOARD = 1.0  # fence top sits this far above the board underside
NOTCH_WIDTH = 18.0
LABEL_Y = -35.0


@dataclass(frozen=True)
class Board:
    """A dev board lying flat; X = short side, Y = long side.

    Attributes:
        label: text debossed in front of the bay.
        width: board size along X (mm).
        length: board size along Y (mm).
        thickness: PCB thickness (mm), sets the locating pin height.
        holes: mounting hole rectangle (x pitch, y pitch) or None for an edge cradle.
        hole_d: mounting hole diameter.
        post_d: standoff diameter (must stay inside the pad keep-out).
    """

    label: str
    width: float
    length: float
    thickness: float
    holes: tuple[float, float] | None = None
    hole_d: float = 0.0
    post_d: float = 0.0


PI_ZERO = Board("PI ZERO", 30.0, 65.0, 1.4, (23.0, 58.0), 2.75, 5.0)
PICO = Board("PICO", 21.0, 51.0, 1.0, (11.4, 47.0), 2.1, 3.6)
ESP32 = Board("ESP32", 28.0, 55.0, 1.6)


def bay_size(board: Board) -> tuple[float, float]:
    """Outer (X, Y) size of a board bay including the fence."""
    grow = 2 * (FENCE_GAP + FENCE_WALL)
    return board.width + grow, board.length + grow


def board_bay(board: Board, notch_sides: tuple[int, ...]) -> Part:
    """Fence + supports for one board, centered on XY, sitting on z = DOCK_PLATE.

    The fence rises to just above the board underside: it guards the downward header
    tails and locates the board. Finger notches drop the fence on the given X sides
    (-1, +1) so a fingertip can tip the board up.
    """
    outer_x, outer_y = bay_size(board)
    fence_h = BOARD_Z + FENCE_ABOVE_BOARD - DOCK_PLATE
    bay = Pos(0, 0, DOCK_PLATE) * Box(outer_x, outer_y, fence_h, align=MIN)
    bay -= Pos(0, 0, DOCK_PLATE) * Box(
        board.width + 2 * FENCE_GAP, board.length + 2 * FENCE_GAP, fence_h + 1, align=MIN
    )
    fence_top = DOCK_PLATE + fence_h
    for side in notch_sides:
        notch_x = side * (outer_x / 2 - FENCE_WALL / 2)
        # Semicircular notch centered on the fence top: 18 mm wide, bottom 2 mm above the plate.
        bay -= (
            Pos(notch_x, 0, fence_top) * Rot(0, 90, 0) * Cylinder(NOTCH_WIDTH / 2, FENCE_WALL + 1)
        )
    return bay + board_supports(board)


def board_supports(board: Board) -> Part:
    """Standoffs with locating pins on the mounting holes, or two ribs for hole-less boards."""
    post_h = BOARD_Z - DOCK_PLATE
    if board.holes is None:
        ribs = None
        for sx in (-1, 1):
            rib = Pos(sx * 6.5, 0, DOCK_PLATE) * Box(1.6, board.length - 15.0, post_h, align=MIN)
            ribs = rib if ribs is None else ribs + rib
        return ribs
    pin_d = board.hole_d - 0.4
    pin_h = board.thickness + 1.0
    supports = None
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * board.holes[0] / 2, sy * board.holes[1] / 2
            post = Pos(x, y, DOCK_PLATE) * Cylinder(board.post_d / 2, post_h, align=MIN)
            pin = Pos(x, y, BOARD_Z) * Cylinder(pin_d / 2, pin_h, align=MIN)
            pin = chamfer(pin.edges().sort_by(Axis.Z)[-1], length=0.3)
            post += pin
            supports = post if supports is None else supports + post
    return supports


def dock_layout() -> list[tuple[Board, float, float, tuple[int, ...]]]:
    """(board, bay center x, bay center y, notch sides): bays back-aligned, labels in front.

    Pi Zero on the left, Pico in the middle, ESP32 on the right, with two ~13.6 mm finger
    gaps between bays. Notches face those gaps.
    """
    cav_w, cav_d, _ = DOCK_CRATE.cavity
    half_w, half_d = cav_w / 2 - CLEARANCE, cav_d / 2 - CLEARANCE
    margin = 1.0
    pz_w, _ = bay_size(PI_ZERO)
    esp_w, _ = bay_size(ESP32)
    pz_x = -half_w + margin + pz_w / 2
    esp_x = half_w - margin - esp_w / 2
    pico_x = ((pz_x + pz_w / 2) + (esp_x - esp_w / 2)) / 2
    back = half_d - margin
    return [
        (PI_ZERO, pz_x, back - bay_size(PI_ZERO)[1] / 2, (1,)),
        (PICO, pico_x, back - bay_size(PICO)[1] / 2, (-1, 1)),
        (ESP32, esp_x, back - bay_size(ESP32)[1] / 2, (-1,)),
    ]


def make_dev_dock() -> Part:
    """Raised dock for a Pi Zero / Zero 2 W, a Pico and an ESP32 DevKitC in a 3x2x6 crate."""
    dock = tray_blank(DOCK_CRATE, DOCK_PLATE)
    for board, x, y, notches in dock_layout():
        dock += Pos(x, y, 0) * board_bay(board, notches)
        dock -= deboss_text(board.label, x, LABEL_Y, DOCK_PLATE)
    return dock


def dev_dock_boards() -> Part:
    """Board slabs (with mounting holes) placed on the dock, for fit checks only."""
    slabs = None
    for board, x, y, _ in dock_layout():
        slab = Pos(x, y, BOARD_Z) * Box(board.width, board.length, board.thickness, align=MIN)
        if board.holes is not None:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    slab -= Pos(x + sx * board.holes[0] / 2, y + sy * board.holes[1] / 2, 0) * (
                        Cylinder(board.hole_d / 2, 2 * BOARD_Z, align=MIN)
                    )
        slabs = slab if slabs is None else slabs + slab
    return slabs


# --------------------------------------------------------------------------- solder station

SOLDER_CRATE = crate_size(3, 2, 6)
SOLDER_HEIGHT = 20.0
SYRINGE_CENTER = (0.0, -3.6)
SYRINGE_ANGLE = 23.1  # deg; 125 mm does not fit along X (cavity 121.5), so it lies diagonally
SYRINGE_LENGTH = 127.0  # 125 mm syringe incl. extended plunger + 1 mm each end
SYRINGE_R = 8.4  # 16 mm barrel + 0.4 mm per side
SYRINGE_AXIS_Z = 15.5  # barrel axis; barrel sits 12.5 mm deep, 3.5 mm proud
FLANGE_AXIAL = -20.0  # finger flange position along the axis (plunger end is -axis)
FLANGE_SLOT = (8.0, 27.0)  # axial x lateral; 25 mm flange, either orientation
TUBE_CENTER = (28.2, -26.5)
TUBE_SIZE = (61.6, 22.8)  # 22 x 60 mm solder tube lying along X, 0.4 mm per side
TUBE_AXIS_Z = 17.5  # tube sits 14 mm deep, 8 mm proud
REEL_CENTER = (-38.8, 17.8)
REEL_R = 20.4  # 40 mm reel + 0.4 mm per side
REEL_FLOOR_Z = 12.5  # 6 mm reel in a 7.5 mm well
AXLE_D = 4.5
WICK_PULL = (-52.5, -7.5)  # finger pocket at the end of the wick feed slot
TIN_CENTER = (-1.6, 22.8)
TIN_R = 15.4  # 30 mm tin + 0.4 mm per side
TIN_FLOOR_Z = 8.0  # 18 mm tin sits 12 mm deep, 6 mm proud to grab the lid


def _syringe_frame(part: Part) -> Part:
    return Pos(*SYRINGE_CENTER, 0) * Rot(0, 0, SYRINGE_ANGLE) * part


def syringe_pocket() -> Part:
    """Round-bottomed trough along +X (before rotation) plus the finger-flange slot."""
    sep = SYRINGE_LENGTH - 2 * SYRINGE_R
    top = SOLDER_HEIGHT + 1
    trough = Pos(0, 0, SYRINGE_AXIS_Z) * extrude(
        SlotCenterToCenter(sep, 2 * SYRINGE_R), amount=top - SYRINGE_AXIS_Z
    )
    trough += Pos(0, 0, SYRINGE_AXIS_Z) * Rot(0, 90, 0) * Cylinder(SYRINGE_R, sep)
    for sx in (-1, 1):
        trough += Pos(sx * sep / 2, 0, SYRINGE_AXIS_Z) * Sphere(SYRINGE_R)
    slot_floor = SYRINGE_AXIS_Z - FLANGE_SLOT[1] / 2
    trough += Pos(FLANGE_AXIAL, 0, slot_floor) * Box(
        FLANGE_SLOT[0], FLANGE_SLOT[1], top - slot_floor, align=MIN
    )
    return _syringe_frame(trough)


def solder_pockets() -> list[tuple[str, Part]]:
    """Named pocket solids cut into the solder-station block."""
    top = SOLDER_HEIGHT + 1
    tube_len, tube_w = TUBE_SIZE
    tube = Pos(*TUBE_CENTER, TUBE_AXIS_Z) * Box(tube_len, tube_w, top - TUBE_AXIS_Z, align=MIN)
    tube += Pos(*TUBE_CENTER, TUBE_AXIS_Z) * Rot(0, 90, 0) * Cylinder(tube_w / 2, tube_len)
    reel = Pos(*REEL_CENTER, REEL_FLOOR_Z) * Cylinder(REEL_R, top - REEL_FLOOR_Z, align=MIN)
    dx, dy = WICK_PULL[0] - REEL_CENTER[0], WICK_PULL[1] - REEL_CENTER[1]
    feed_len = math.hypot(dx, dy)
    feed = (
        Pos((REEL_CENTER[0] + WICK_PULL[0]) / 2, (REEL_CENTER[1] + WICK_PULL[1]) / 2, REEL_FLOOR_Z)
        * Rot(0, 0, math.degrees(math.atan2(dy, dx)))
        * Box(feed_len, 4.5, top - REEL_FLOOR_Z, align=MIN)
    )
    pull = Pos(*WICK_PULL, REEL_FLOOR_Z - 2.5) * Cylinder(6.0, top, align=MIN)
    tin = Pos(*TIN_CENTER, TIN_FLOOR_Z) * Cylinder(TIN_R, top - TIN_FLOOR_Z, align=MIN)
    return [
        ("syringe", syringe_pocket()),
        ("solder tube", tube),
        ("wick reel", reel + feed + pull),
        ("tip tinner", tin),
    ]


def make_solder_station() -> Part:
    """Block insert with pockets for flux syringe, wick reel, solder tube and tip tinner."""
    block = tray_blank(SOLDER_CRATE, SOLDER_HEIGHT)
    for _, pocket in solder_pockets():
        block -= pocket
    axle = Pos(*REEL_CENTER, REEL_FLOOR_Z) * Cylinder(AXLE_D / 2, 5.5, align=MIN)
    axle = chamfer(axle.edges().sort_by(Axis.Z)[-1], length=0.6)
    return block + axle


def solder_items() -> list[tuple[str, Part]]:
    """Nominal-size dummies of the stored items, placed in their pockets (fit checks only)."""
    sep = 125.0 - 16.0
    syringe = Pos(0, 0, SYRINGE_AXIS_Z) * Rot(0, 90, 0) * Cylinder(8.0, sep)
    for sx in (-1, 1):
        syringe += Pos(sx * sep / 2, 0, SYRINGE_AXIS_Z) * Sphere(8.0)
    syringe += Pos(FLANGE_AXIAL, 0, SYRINGE_AXIS_Z) * Rot(0, 90, 0) * Cylinder(12.5, 2.0)
    reel = Pos(*REEL_CENTER, REEL_FLOOR_Z) * Cylinder(20.0, 6.0, align=MIN)
    reel -= Pos(*REEL_CENTER, 0) * Cylinder(3.0, 40.0, align=MIN)
    return [
        ("syringe", _syringe_frame(syringe)),
        ("solder tube", Pos(*TUBE_CENTER, TUBE_AXIS_Z) * Rot(0, 90, 0) * Cylinder(11.0, 60.0)),
        ("wick reel", reel),
        ("tip tinner", Pos(*TIN_CENTER, TIN_FLOOR_Z) * Cylinder(15.0, 18.0, align=MIN)),
    ]


# --------------------------------------------------------------------------- small-parts grid

GRID_CRATE = crate_size(2, 2, 3)
GRID_TRAY_HEIGHT = 14.0
GRID_CUPS = 4
GRID_OUTER_WALL = 1.6
GRID_INNER_WALL = 1.2
GRID_FLOOR = 1.2
CUP_RADIUS = 5.0  # scoop radius on the cup floor and corners


def make_parts_grid(size: BoxSize) -> Part:
    """Shallow tray split into GRID_CUPS x GRID_CUPS cups with scooped floors."""
    tray = tray_blank(size, GRID_TRAY_HEIGHT)
    cav_w, cav_d, _ = size.cavity
    span_x, span_y = cav_w - 2 * CLEARANCE, cav_d - 2 * CLEARANCE
    walls = 2 * GRID_OUTER_WALL + (GRID_CUPS - 1) * GRID_INNER_WALL
    cup_x, cup_y = (span_x - walls) / GRID_CUPS, (span_y - walls) / GRID_CUPS
    cup_h = GRID_TRAY_HEIGHT - GRID_FLOOR + 1.0
    cup = Box(cup_x, cup_y, cup_h, align=MIN)
    open_rim = cup.faces().sort_by(Axis.Z)[-1].edges()
    cup = fillet(cup.edges() - open_rim, radius=CUP_RADIUS)
    for i in range(GRID_CUPS):
        for j in range(GRID_CUPS):
            x = -span_x / 2 + GRID_OUTER_WALL + cup_x / 2 + i * (cup_x + GRID_INNER_WALL)
            y = -span_y / 2 + GRID_OUTER_WALL + cup_y / 2 + j * (cup_y + GRID_INNER_WALL)
            tray -= Pos(x, y, GRID_FLOOR) * cup
    return tray


# --------------------------------------------------------------------------- verification


def _volume(part: Part | None) -> float:
    return 0.0 if part is None else abs(part.volume)


def check_in_crate(name: str, size: BoxSize, placed: Part, crate: Part) -> bool:
    """Print and return whether a part placed in crate coordinates fits the crate.

    Checks: valid solid, zero overlap with the crate, top at or below the stacking seat,
    and zero overlap with a crate of the same footprint stacked at z = 7 * h.
    """
    seat = size.lip_top - SEAT_DEPTH
    stacked = Pos(0, 0, size.h * HEIGHT_UNIT) * make_box(BoxSize(size.nx, size.ny, 2))
    hit_crate = _volume(crate & placed)
    hit_stack = _volume(stacked & placed)
    top = placed.bounding_box().max.Z
    ok = placed.is_valid and hit_crate < 1e-3 and hit_stack < 1e-3 and top <= seat
    print(
        f"  {'OK  ' if ok else 'FAIL'} {name:<28} valid={placed.is_valid} "
        f"crate∩={hit_crate:.4f} stacked∩={hit_stack:.4f} top={top:.2f} seat={seat:.2f}"
    )
    return ok


def check_disjoint(name: str, a: Part, b: Part) -> bool:
    """Print and return whether two placed parts do not overlap."""
    overlap = _volume(a & b)
    ok = overlap < 1e-3
    print(f"  {'OK  ' if ok else 'FAIL'} {name:<28} overlap={overlap:.4f}")
    return ok


def verify_dev_dock(dock: Part) -> bool:
    """Fit the dock and board slabs in a 3x2x6 crate."""
    crate = make_box(DOCK_CRATE)
    placed = Pos(0, 0, FLOOR_Z) * dock
    boards = Pos(0, 0, FLOOR_Z) * dev_dock_boards()
    return all(
        [
            check_in_crate("dev dock", DOCK_CRATE, placed, crate),
            check_in_crate("dev dock + boards", DOCK_CRATE, boards, crate),
            check_disjoint("boards vs dock", boards, placed),
        ]
    )


def verify_solder_station(station: Part) -> bool:
    """Fit the station and item dummies; report the thinnest wall between pockets."""
    crate = make_box(SOLDER_CRATE)
    placed = Pos(0, 0, FLOOR_Z) * station
    results = [check_in_crate("solder station", SOLDER_CRATE, placed, crate)]
    for name, item in solder_items():
        item = Pos(0, 0, FLOOR_Z) * item
        results.append(check_in_crate(f"  item: {name}", SOLDER_CRATE, item, crate))
        results.append(check_disjoint(f"  item vs block: {name}", item, placed))
    pockets = solder_pockets()
    walls = [a.distance_to(b) for i, (_, a) in enumerate(pockets) for _, b in pockets[i + 1 :]]
    outline = tray_blank(SOLDER_CRATE, SOLDER_HEIGHT)
    outer = [_outer_wall(outline, pocket) for _, pocket in pockets]
    print(f"  thinnest wall between pockets {min(walls):.2f} mm, to outside {min(outer):.2f} mm")
    results.append(min(walls) >= 0.99 and min(outer) >= 1.19)
    return all(results)


def _outer_wall(outline: Part, pocket: Part) -> float:
    """Distance from a pocket to the insert's side faces."""
    sides = [f for f in outline.faces() if abs(f.normal_at().Z) < 0.5]
    return min(pocket.distance_to(face) for face in sides)


def verify_parts_grid(tray: Part) -> bool:
    """Fit the parts-grid tray in a 2x2x3 crate."""
    crate = make_box(GRID_CRATE)
    return check_in_crate("parts grid", GRID_CRATE, Pos(0, 0, FLOOR_Z) * tray, crate)


# --------------------------------------------------------------------------- build


def verify() -> bool:
    """Build every insert and run its fit checks against its crate."""
    return all(
        [
            verify_dev_dock(make_dev_dock()),
            verify_solder_station(make_solder_station()),
            verify_parts_grid(make_parts_grid(GRID_CRATE)),
        ]
    )


def build() -> None:
    """Build, verify and export every insert into models/inserts/."""
    dock = make_dev_dock()
    station = make_solder_station()
    grid = make_parts_grid(GRID_CRATE)

    print("verification:")
    checks = [
        verify_dev_dock(dock),
        verify_solder_station(station),
        verify_parts_grid(grid),
    ]
    if not all(checks):
        raise RuntimeError("insert verification failed; see FAIL lines above")

    for part, info in part_infos(dock, station, grid):
        save(MODULE, part, info)
        bb = part.bounding_box().size
        print(f"exported {info.slug:<22} {bb.X:.1f} x {bb.Y:.1f} x {bb.Z:.1f} mm  {info.footprint}")


def part_infos(*parts: Part) -> list[tuple[Part, PartInfo]]:
    """Catalogue metadata, in the order (dock, station, grid)."""
    dock, station, grid = parts
    return [
        (dock, _dock_info()),
        (station, _station_info()),
        (grid, _grid_info()),
    ]


def _dock_info() -> PartInfo:
    return PartInfo(
        slug="dev-board-dock",
        title="Dev-board dock",
        blurb=(
            "Holds a Pi Zero / Zero 2 W and a Pico on locating pegs and an ESP32 DevKitC "
            "in an edge cradle, 10 mm off the floor so header tails never take the weight."
        ),
        material="PLA or PETG",
        print_notes=(
            "Plate on the bed, no supports, 0.2 mm layers, 3 walls, 15% infill. "
            "Pegs are 2.35/1.7 mm: print slower for the top 3 mm or ream with a drill."
        ),
        color="#3fa7d6",
        footprint=f"for {tag(DOCK_CRATE)}",
    )


def _station_info() -> PartInfo:
    return PartInfo(
        slug="solder-station",
        title="Solder station insert",
        blurb=(
            "Pockets for a 10 ml flux syringe (lying diagonally), a 40 mm wick reel on a "
            "spin axle with a feed slot, a 22 mm solder tube and a 30 mm tip-tinner tin."
        ),
        material="PETG or ASA (it lives next to the iron); never rest the hot tip on any print",
        print_notes=(
            "Upright, no supports, 3 walls, 10-15% infill. Round trough bottoms print as "
            "steep overhangs and come out fine; the 1 mm ribs between pockets need 0.4 mm nozzle."
        ),
        color="#e4572e",
        footprint=f"for {tag(SOLDER_CRATE)}",
    )


def _grid_info() -> PartInfo:
    return PartInfo(
        slug="parts-grid-2x2",
        title="Small-parts grid 4x4",
        blurb=(
            "Lift-out tray of sixteen 18 mm cups with 5 mm scooped floors for SMD parts, "
            "screws and standoffs; swap whole trays between crates."
        ),
        material="PLA or PETG",
        print_notes="Upright, no supports, 2 walls, 15% infill.",
        color="#8e7dbe",
        footprint=f"for {tag(GRID_CRATE)}",
    )


if __name__ == "__main__":
    build()
