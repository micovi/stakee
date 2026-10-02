"""Magnetic repair tray: a 1-unit stackable cap whose top is a numbered screw tray.

Design: the tray side is the top, so it never has to be flipped (a flipped tray would pour
its screws out). The underside is the solid cap foot (same envelope as ``make_cap``), so it
seats in any crate's stacking lip at ``z = 7 * h``. The rim is a full stacking lip at the
1-unit height (lip top 11 mm, like a ``BoxSize(nx, ny, 1)``), so crates and caps stack on
top of it at a 7 mm pitch: put the tray on a crate mid-repair, stack the next crate on it,
and the screws stay put underneath. On the bench it stands on its flat foot.

Each compartment (one per disassembly step, debossed step number in the back-left corner)
has filleted floor edges and one 10x2 mm N52 disc magnet at its center, sealed in by a print
pause under a 0.6 mm ceiling (3 layers at 0.2 mm). Divider tops stop 0.2 mm below the feet
of a crate stacked on top; screws lying flat (M2.5 head <= 2.5 mm) clear those feet.
"""

import math

from build123d import (
    Align,
    Axis,
    Box,
    Cylinder,
    FontStyle,
    Part,
    Pos,
    RectangleRounded,
    Shell,
    Solid,
    Text,
    extrude,
    fillet,
)
from OCP.BRepClass3d import BRepClass3d

from stakee.core import (
    FOOT_HEIGHT,
    FOOT_STATIONS,
    HEIGHT_UNIT,
    OUTER_RADIUS,
    WALL,
    BoxSize,
    lip_pocket,
    make_box,
    make_cap,
    profile_solid,
)
from stakee.export import PartInfo, save

MODULE = "magtray"

LAYER = 0.2
MAGNET_D, MAGNET_T = 10.0, 2.0  # 10x2 mm N52 disc
POCKET_D = MAGNET_D + 0.3
POCKET_T = MAGNET_T + 0.2  # magnet sits 0.2 below the pocket top: the nozzle never hits it
SKIN = 0.6  # plastic under each pocket
CEILING = 0.6  # plastic over each pocket: 3 layers at 0.2 mm
POCKET_Z0 = SKIN
POCKET_TOP = POCKET_Z0 + POCKET_T  # 2.8: pause after this layer, magnets in, resume
FLOOR = POCKET_TOP + CEILING  # 3.4: compartment floor
STACK_CLEARANCE = 0.2  # divider tops to the feet of a crate stacked on top
DIVIDER_TOP = HEIGHT_UNIT - STACK_CLEARANCE
DIVIDER = 1.2
CORNER_RADIUS = 3.0
FLOOR_FILLET = 2.5
DIGIT_SIZE = 5.0
DIGIT_DEPTH = 0.4
DIGIT_INSET = FLOOR_FILLET + 3.0  # digit center from the compartment's back-left walls

LAYOUTS = {(2, 2): (3, 3), (3, 2): (4, 3)}  # footprint -> compartment (columns, rows)
_MIN_Z = (Align.CENTER, Align.CENTER, Align.MIN)


def tray_size(nx: int, ny: int) -> BoxSize:
    """The tray behaves like a 1-unit box: lip top at 11 mm, stacking pitch 7 mm."""
    return BoxSize(nx, ny, 1)


def compartments(nx: int, ny: int) -> list[tuple[int, float, float, float, float]]:
    """(step number, center x, center y, width, depth) of each compartment.

    Steps are numbered left to right, back (+Y) to front, like reading a page.
    """
    cols, rows = LAYOUTS[(nx, ny)]
    size = tray_size(nx, ny)
    field_w, field_d = size.width - 2 * WALL, size.depth - 2 * WALL
    cw = (field_w - (cols - 1) * DIVIDER) / cols
    cd = (field_d - (rows - 1) * DIVIDER) / rows
    cells = []
    for r in range(rows):
        y = field_d / 2 - cd / 2 - r * (cd + DIVIDER)
        for c in range(cols):
            x = -field_w / 2 + cw / 2 + c * (cw + DIVIDER)
            cells.append((r * cols + c + 1, x, y, cw, cd))
    return cells


def _compartment_cut(width: float, depth: float) -> Part:
    cut = Box(width, depth, DIVIDER_TOP - FLOOR + 1.0, align=_MIN_Z)
    cut = fillet(cut.edges().filter_by(Axis.Z), CORNER_RADIUS)
    return fillet(cut.edges().group_by(Axis.Z)[0], FLOOR_FILLET)


def _digit(step: int) -> Part:
    label = Text(str(step), font_size=DIGIT_SIZE, font_style=FontStyle.BOLD)
    return extrude(label, amount=DIGIT_DEPTH + 0.01)


def pocket(x: float, y: float) -> Part:
    """The magnet pocket under the compartment centered at (x, y)."""
    return Pos(x, y, POCKET_Z0) * Cylinder(POCKET_D / 2, POCKET_T, align=_MIN_Z)


def magnet(x: float, y: float) -> Part:
    """A seated magnet: on the pocket bottom, centered."""
    return Pos(x, y, POCKET_Z0) * Cylinder(MAGNET_D / 2, MAGNET_T, align=_MIN_Z)


def make_tray(nx: int, ny: int) -> Part:
    """Magnetic repair tray / stackable cap.

    Args:
        nx: footprint width in grid units (2 or 3).
        ny: footprint depth in grid units (2).

    Returns:
        One solid with a sealed magnet void under every compartment.
    """
    size = tray_size(nx, ny)
    width, depth = size.width, size.depth
    body = profile_solid(width, depth, FOOT_STATIONS)
    body += Pos(0, 0, FOOT_HEIGHT) * extrude(
        RectangleRounded(width, depth, OUTER_RADIUS), amount=size.lip_top - FOOT_HEIGHT
    )
    field = RectangleRounded(width - 2 * WALL, depth - 2 * WALL, OUTER_RADIUS - WALL)
    body -= Pos(0, 0, DIVIDER_TOP) * extrude(field, amount=size.lip_top)
    body -= lip_pocket(size)
    for step, x, y, cw, cd in compartments(nx, ny):
        body -= Pos(x, y, FLOOR) * _compartment_cut(cw, cd)
        corner = (x - cw / 2 + DIGIT_INSET, y + cd / 2 - DIGIT_INSET, FLOOR - DIGIT_DEPTH)
        body -= Pos(*corner) * _digit(step)
        body -= pocket(x, y)
    return body


def build() -> None:
    """Export the 2x2 and 3x2 trays into models/magtray/."""
    for nx, ny in LAYOUTS:
        cols, rows = LAYOUTS[(nx, ny)]
        count = cols * rows
        save(
            MODULE,
            make_tray(nx, ny),
            PartInfo(
                slug=f"magtray-{nx}x{ny}",
                title=f"Magnetic repair tray {nx}x{ny}",
                blurb=(
                    f"{count} numbered compartments, one per disassembly step, each with a "
                    "hidden magnet that grabs M2/M2.5 screws. Seats on any crate as a cap and "
                    "crates stack on top of it, so a half-done repair can be put away."
                ),
                material="PLA or PETG + 10x2 mm N52 disc magnets",
                print_notes=(
                    f"Upright (foot on the bed), no supports, 0.2 mm layers including the first. "
                    f"Insert a pause at z = {POCKET_TOP + LAYER:.1f} mm (before the first layer "
                    f"over the pockets, i.e. after the {POCKET_TOP:.1f} mm layer): drop {count} "
                    f"10x2 mm N52 magnets into the pockets, resume. The {CEILING:.1f} mm ceiling "
                    "prints on top of them; magnet polarity does not matter."
                ),
                color="#e0529c",
                footprint=f"{nx}x{ny}x1",
            ),
        )


def _envelope(part: Part) -> Solid:
    """The part with its internal voids filled: the solid bounded by its outer shell only."""
    solids = part.solids()
    if len(solids) != 1:
        raise ValueError(f"expected one solid, got {len(solids)}")
    return Solid(Shell(BRepClass3d.OuterShell_s(solids[0].wrapped)))


def _check_pockets(name: str, part: Part, nx: int, ny: int) -> bool:
    """Every magnet fits its pocket, every pocket is sealed, ceiling and skin are as designed."""
    envelope = _envelope(part)
    voids = len(part.solids()[0].shells()) - 1
    cells = compartments(nx, ny)
    area = math.pi * (POCKET_D / 2) ** 2
    leaks, clashes, ceilings, skins = [], [], [], []
    for _, x, y, _, _ in cells:
        leaks.append((pocket(x, y) - envelope).volume)
        clashes.append((part & magnet(x, y)).volume)
        above = Pos(x, y, POCKET_TOP) * Cylinder(POCKET_D / 2, 20.0, align=_MIN_Z)
        below = Pos(x, y, 0) * Cylinder(POCKET_D / 2, POCKET_Z0, align=_MIN_Z)
        ceilings.append((part & above).volume / area)
        skins.append((part & below).volume / area)
    magnets = None
    for _, x, y, _, _ in cells:
        magnets = magnet(x, y) if magnets is None else magnets + magnet(x, y)
    lost = part.volume - (part - magnets).volume
    print(
        f"  {name}: sealed voids = {voids}/{len(cells)}, pocket volume outside envelope max = "
        f"{max(leaks):.6f} mm^3, magnets & part = {max(clashes):.6f} mm^3, "
        f"part - (part - magnets) = {lost:.6f} mm^3"
    )
    print(
        f"  {name}: ceiling over pockets = {min(ceilings):.3f}..{max(ceilings):.3f} mm, "
        f"skin under = {min(skins):.3f}..{max(skins):.3f} mm"
    )
    sealed = voids == len(cells) and max(leaks) < 1e-6
    fits = max(clashes) < 1e-6 and abs(lost) < 1e-6
    thick = all(abs(c - CEILING) < 1e-3 for c in ceilings) and min(skins) > SKIN - 1e-3
    return sealed and fits and thick


def _clash(a: Part, b: Part) -> float:
    return (a & b).volume


def _check_stack(nx: int, ny: int, tray: Part) -> bool:
    """Crate h3 / tray as a cap / crate h3 on top / core cap on that crate's place on the tray."""
    low = BoxSize(nx, ny, 3)
    seat = low.h * HEIGHT_UNIT
    above = seat + tray_size(nx, ny).h * HEIGHT_UNIT
    crate = make_box(low)
    upper = make_box(low)
    cap = make_cap(nx, ny)
    checks = (
        ("tray on crate lip", crate, tray, seat),
        ("crate on tray lip", Pos(0, 0, seat) * tray, upper, above),
        ("cap on tray lip", Pos(0, 0, seat) * tray, cap, above),
    )
    ok = True
    for label, base, top, z in checks:
        seated = _clash(base, Pos(0, 0, z) * top)
        lowered = _clash(base, Pos(0, 0, z - 0.05) * top)
        print(
            f"  {nx}x{ny} {label:18s} @ z={z:4.1f}: intersection = {seated:.6f} mm^3, "
            f"lowered 0.05 mm = {lowered:.4f} mm^3"
        )
        ok &= seated < 1e-6 and lowered > 1e-3
    through = _clash(crate, Pos(0, 0, above) * upper)
    headroom = above - (seat + FLOOR)
    print(f"  {nx}x{ny} lower crate & upper crate = {through:.6f} mm^3")
    print(f"  {nx}x{ny} screw headroom: floor to upper crate feet = {headroom:.2f} mm")
    return ok and through < 1e-6


def verify() -> bool:
    """Validity, sealed magnet pockets, ceiling thickness, cap seating and stacking on top."""
    ok = True
    for nx, ny in LAYOUTS:
        tray = make_tray(nx, ny)
        bb = tray.bounding_box()
        print(
            f"magtray-{nx}x{ny} valid={tray.is_valid}  "
            f"{bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm"
        )
        ok &= tray.is_valid
        ok &= _check_pockets(f"magtray-{nx}x{ny}", tray, nx, ny)
        ok &= _check_stack(nx, ny, tray)
    print("negative control: 2x2 with the ceiling of step 5's pocket drilled away")
    _, x, y, _, _ = compartments(2, 2)[4]
    drill = Pos(x, y, POCKET_TOP - 0.01) * Cylinder(POCKET_D / 2, CEILING + 0.02, align=_MIN_Z)
    broken = make_tray(2, 2) - drill
    caught = not _check_pockets("broken-2x2", broken, 2, 2)
    print(f"  broken pocket caught = {caught}")
    ok &= caught
    print(f"pause at z = {POCKET_TOP + LAYER:.1f} mm (after the {POCKET_TOP:.1f} mm layer)")
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return ok


if __name__ == "__main__":
    build()
    verify()
