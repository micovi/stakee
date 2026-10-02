"""Grab-and-go kit: accessories that turn a stack of crates into a carryable hacker kit.

Parts: a bayonet stack clip that locks two stacked crates together at the seam, a tote handle
cap, an NFC label cap with a swappable snap-in text tile, and a tool rack cap.

Clip geometry is expressed relative to the seam ``z = 7 * h_lower`` (the stacking pitch):
the lower crate's lip socket sits at ``LIP_ABOVE_NOMINAL - CLIP_SOCKET_LIP_Z`` = +2.0 mm and
the upper part's base socket at ``CLIP_SOCKET_BASE_Z`` = +6.5 mm, for every box height.
The sockets are core's L pockets: the clip's L nubs go into the windows, then the clip slides
``CLIP_SOCKET_LEG`` along the face so the hooks sit behind the skin.
"""

import math

from build123d import (
    Align,
    Axis,
    Box,
    Cylinder,
    Edge,
    FontStyle,
    Location,
    Part,
    Plane,
    Polygon,
    Pos,
    RectangleRounded,
    Rot,
    Text,
    chamfer,
    extrude,
    fillet,
    mirror,
)

from stakee.core import (
    CAP_PLATE,
    CLIP_SOCKET_BASE_Z,
    CLIP_SOCKET_DEPTH,
    CLIP_SOCKET_HEIGHT,
    CLIP_SOCKET_LEG,
    CLIP_SOCKET_LIP_Z,
    CLIP_SOCKET_OPENING,
    CLIP_SOCKET_SKIN,
    CLIP_SOCKET_WIDTH,
    FOOT_HEIGHT,
    FOOT_STATIONS,
    GAP,
    GRID,
    HEIGHT_UNIT,
    LIP_ABOVE_NOMINAL,
    OUTER_RADIUS,
    BoxSize,
    clip_socket_cuts,
    clip_socket_positions,
    make_box,
    profile_solid,
)
from stakee.export import PartInfo, save

MODULE = "kit"

# --- Stack clip. Local frame = the socket frame on a +X face with the clip LOCKED: the box face
# is x = 0 (clip at x >= 0, nubs toward -X), y = 0 is the socket center, z = 0 is the seam. ---
CLIP_PLATE = 1.6  # plate thickness: 4 perimeters at 0.4 mm
CLIP_HALF_WIDTH = 7.0  # plate spans y = -7..7 when locked: on the flat face (sockets 12 mm in)
CLIP_TOP = 8.5  # plate top above the seam; with the tab a clip spans z = -8.3..8.5, so clips
CLIP_BOTTOM = -1.0  # on both seams of an h = 2 box (14 mm apart) clear each other
TAB_LENGTH = 8.0
TAB_ANGLE = 25.0  # degrees away from the wall
CLEAR_Y = 0.15  # nub ends to the window / leg ends
CLEAR_Z = 0.15  # nub top / bottom to the socket; < 0.3 so the clip carries the lift load
CLEAR_SKIN = 0.15  # hook to the inside of the skin: the clip's in / out play
CLEAR_FLOOR = 0.1  # nub to socket floor (the plate resting on the face is the real stop)
NUB_HEIGHT = CLIP_SOCKET_HEIGHT - 2 * CLEAR_Z
NUB_DEPTH = CLIP_SOCKET_DEPTH - CLEAR_FLOOR
HOOK_FRONT = CLIP_SOCKET_SKIN + CLEAR_SKIN  # hook occupies x = -NUB_DEPTH..-HOOK_FRONT
SKIN_EDGE = CLIP_SOCKET_OPENING - CLIP_SOCKET_WIDTH / 2  # window / leg boundary along y
NUB_START = CLIP_SOCKET_LEG - CLIP_SOCKET_WIDTH / 2 + CLEAR_Y  # -Y end of both nub parts
STEM_END = SKIN_EDGE - CLEAR_Y  # the full-depth stem stays in the window
HOOK_END = CLIP_SOCKET_WIDTH / 2 - CLEAR_Y  # the hook runs on to the end of the leg
SLIDE = CLIP_SOCKET_LEG  # unlock travel along -Y; unlocked, the nubs fill only the window
LOWER_NUB_Z = LIP_ABOVE_NOMINAL - CLIP_SOCKET_LIP_Z  # lip socket of the lower box
UPPER_NUB_Z = CLIP_SOCKET_BASE_Z  # base socket of the upper box / cap
# Detent: a flexing finger (cut free from the plate along -Y) whose bump drops into the end of
# the lower window that the nub vacates when locked; sliding back lifts the finger over it.
DETENT_BUMP = 0.25  # bump height = finger deflection when riding on the face
DETENT_FLAT = 0.6  # flat top of the 45 deg bump
DETENT_START = CLEAR_Y - CLIP_SOCKET_WIDTH / 2  # bump's -Y foot, just inside the window end
FINGER_WIDTH = 2.2  # along Z, centered on the lower nub
FINGER_THICKNESS = 1.0  # thinner than the plate so it flexes (~2 % strain at 0.25 mm)
FINGER_SLOT = 0.8
FINGER_ROOT = NUB_START - 0.25  # slots end just before the lower stem

# --- Caps built on a solid foot so they print upright (or on their side) without bridges ---
CLIP_CAP_TOP = 11.0  # body top of caps that carry clip sockets (socket top is at 7.3)

HANDLE_THICKNESS = 14.0  # along X
HANDLE_WINDOW = 26.0  # finger opening height at the center
HANDLE_BAR = 13.0  # grip bar height
HANDLE_POST = 9.0  # post width at the grip bar
HANDLE_FILLET = 3.0

NFC_TAG_DIAMETER = 25.6  # 25 mm NTAG215 + 0.3 mm per side
NFC_TAG_POCKET = 0.6  # 0.5 mm sticker + 0.1 mm
TILE_SIZE = (52.0, 30.0)
TILE_THICKNESS = 1.6
TILE_TEXT_HEIGHT = 0.6
TILE_CLEARANCE = 0.15
TILE_RADIUS = 2.0
TILE_SLOT = (1.0, 24.0)  # latch slot (width X, length Y) behind each end bar
TILE_BAR = 1.4  # latch bar width (X)
TILE_BUMP = 0.5  # how far the latch bump stands proud of the tile end
TILE_BUMP_LENGTH = 10.0
TILE_RECESS_DEPTH = TILE_THICKNESS + TILE_TEXT_HEIGHT  # text tops end flush with the cap

RACK_INSET = 3.5
RACK_HEIGHT = 28.0
RACK_FLOOR = 3.0  # hole bottoms, local z

_MIN_Z = (Align.CENTER, Align.CENTER, Align.MIN)


def _cz(shape: Edge) -> float:
    return shape.center().Z


def _profile_xz(points: list[tuple[float, float]], width: float) -> Part:
    """Extrude an (x, z) outline symmetrically along Y."""
    return extrude(Plane.XZ * Polygon(*points), amount=width / 2, both=True)


def _span_box(x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Part:
    """Axis-aligned box spanning the given (min, max) ranges."""
    center = Pos((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2)
    return center * Box(x[1] - x[0], y[1] - y[0], z[1] - z[0])


def _nub(z_center: float) -> Part:
    """One L nub: a full-depth stem in the window plus a hook that runs on into the leg."""
    z = (z_center - NUB_HEIGHT / 2, z_center + NUB_HEIGHT / 2)
    stem = _span_box((-NUB_DEPTH, 0.4), (NUB_START, STEM_END), z)  # 0.4 overlaps the plate
    hook = _span_box((-NUB_DEPTH, -HOOK_FRONT), (NUB_START, HOOK_END), z)
    return stem + hook


def _nubs() -> Part:
    return _nub(LOWER_NUB_Z) + _nub(UPPER_NUB_Z)


def _detent_bump() -> Part:
    """45 deg bump on the finger, sized like the nub so it fits the lower window."""
    y0, b, top = DETENT_START, DETENT_BUMP, DETENT_FLAT
    y1 = y0 + 2 * b + top
    pts = [(0.3, y0), (0, y0), (-b, y0 + b), (-b, y0 + b + top), (0, y1), (0.3, y1)]
    z0 = LOWER_NUB_Z - NUB_HEIGHT / 2
    return extrude(Plane.XY.offset(z0) * Polygon(*pts), amount=NUB_HEIGHT, dir=(0, 0, 1))


def _finger_cuts() -> Part:
    """Two through slots that free the detent finger from the plate, plus its thinning."""
    z0, z1 = LOWER_NUB_Z - FINGER_WIDTH / 2, LOWER_NUB_Z + FINGER_WIDTH / 2
    y = (-CLIP_HALF_WIDTH - 1.0, FINGER_ROOT)
    through = (-1.0, CLIP_PLATE + 1.0)
    cuts = _span_box(through, y, (z0 - FINGER_SLOT, z0))
    cuts += _span_box(through, y, (z1, z1 + FINGER_SLOT))
    return cuts + _span_box((FINGER_THICKNESS, CLIP_PLATE + 1.0), y, (z0, z1))


def _clip_plate() -> Part:
    """Plate on the face from the pull tab to CLIP_TOP; the tab bends out at TAB_ANGLE."""
    a = math.radians(TAB_ANGLE)
    down = (math.sin(a), -math.cos(a))
    out = (math.cos(a), math.sin(a))
    p0 = (0.0, CLIP_BOTTOM)
    p1 = (p0[0] + TAB_LENGTH * down[0], p0[1] + TAB_LENGTH * down[1])
    p2 = (p1[0] + CLIP_PLATE * out[0], p1[1] + CLIP_PLATE * out[1])
    back = (p2[0] - CLIP_PLATE) / down[0]
    p3 = (CLIP_PLATE, p2[1] - back * down[1])
    outline = [(0, CLIP_TOP), p0, p1, p2, p3, (CLIP_PLATE, CLIP_TOP)]
    plate = _profile_xz(outline, 2 * CLIP_HALF_WIDTH)
    tab_edges = plate.edges().filter_by(Axis.Y).filter_by(lambda e: _cz(e) < p1[1] + 1.0)
    return fillet(tab_edges, 0.6)


def make_stack_clip() -> Part:
    """Bayonet PETG clip that bridges the seam between two stacked crates (or crate + cap).

    Local frame (locked pose): the box's side face is the plane x = 0, the clip lies at x >= 0
    with its L nubs pointing to -X, y = 0 is the socket center and z = 0 is the seam
    (7 * h of the lower box). Place it on a +X face at (width / 2, socket_y, 7 * h_lower);
    rotate 180 deg about Z for a -X face. Unlocked, it sits SLIDE further toward local -Y.

    Raises:
        ValueError: if core's socket dimensions leave no room for the stem or the hook.
    """
    if STEM_END - NUB_START < 1.0 or NUB_DEPTH - HOOK_FRONT < 0.3:
        raise ValueError(
            f"clip socket too small for an L nub: stem {STEM_END - NUB_START:.2f} mm (need 1.0), "
            f"hook {NUB_DEPTH - HOOK_FRONT:.2f} mm thick (need 0.3); "
            "enlarge CLIP_SOCKET_OPENING / CLIP_SOCKET_DEPTH in core.py"
        )
    plate = _clip_plate() - _finger_cuts()
    return plate + _nubs() + _detent_bump()


def _solid_cap(nx: int, ny: int, top_z: float) -> Part:
    """Cap envelope identical to core.make_cap (seats in any lip) but with a solid foot."""
    width, depth = nx * GRID - 2 * GAP, ny * GRID - 2 * GAP
    cap = profile_solid(width, depth, FOOT_STATIONS)
    cap += Pos(0, 0, FOOT_HEIGHT) * extrude(
        RectangleRounded(width, depth, OUTER_RADIUS), amount=top_z - FOOT_HEIGHT
    )
    return cap


def _base_socket_cuts(nx: int, ny: int) -> Part:
    """Core's L base sockets for this footprint (a cap seats like a box, so same heights)."""
    cuts = clip_socket_cuts(BoxSize(nx, ny, 2), lip=False, base=True)
    if cuts is None:
        raise ValueError(f"core.clip_socket_cuts returned no base sockets for {nx}x{ny}")
    return cuts


def _tote_handle(depth: float, base_z: float) -> Part:
    """Handle running along Y, flush with the front/back faces; window sides at 45 deg."""
    half = depth / 2
    top = base_z + HANDLE_WINDOW + HANDLE_BAR
    win_top = half - HANDLE_POST
    win_bottom = win_top - HANDLE_WINDOW
    sink = 0.5  # overlap into the cap body
    outline = [(-half, base_z - sink), (half, base_z - sink), (half, top), (-half, top)]
    window = [
        (-win_bottom + sink, base_z - sink),
        (win_bottom - sink, base_z - sink),
        (win_top, base_z + HANDLE_WINDOW),
        (-win_top, base_z + HANDLE_WINDOW),
    ]
    amount = HANDLE_THICKNESS / 2
    handle = extrude(Plane.YZ * Polygon(*outline), amount=amount, both=True)
    handle -= extrude(Plane.YZ * Polygon(*window), amount=amount + 1, both=True)
    grip_edges = (
        handle.edges()
        .filter_by(lambda e: abs(abs(e.center().X) - amount) < 1e-6)
        .filter_by(lambda e: _cz(e) > base_z + 0.1)
        .filter_by(lambda e: abs(abs(e.center().Y) - half) > 1e-3)
    )
    return fillet(grip_edges, HANDLE_FILLET)


def make_tote_cap(nx: int, ny: int) -> Part:
    """Cap with an arched carry handle and base clip sockets, so a clipped stack is a tote.

    Args:
        nx: footprint width in grid units.
        ny: footprint depth in grid units (the handle runs along Y).
    """
    depth = ny * GRID - 2 * GAP
    cap = _solid_cap(nx, ny, CLIP_CAP_TOP)
    cap -= _base_socket_cuts(nx, ny)
    return cap + _tote_handle(depth, CLIP_CAP_TOP)


def _tile_outline(clearance: float) -> RectangleRounded:
    w, d = TILE_SIZE
    return RectangleRounded(w + 2 * clearance, d + 2 * clearance, TILE_RADIUS + clearance)


def make_nfc_cap() -> Part:
    """2x2 cap with a recess for the snap-in label tile and a 25 mm NTAG215 pocket under it."""
    top = FOOT_HEIGHT + CAP_PLATE
    cap = _solid_cap(2, 2, top)
    floor = top - TILE_RECESS_DEPTH
    cap -= Pos(0, 0, floor) * extrude(_tile_outline(TILE_CLEARANCE), amount=TILE_RECESS_DEPTH + 1)
    cap -= Pos(0, 0, floor - NFC_TAG_POCKET) * Cylinder(
        NFC_TAG_DIAMETER / 2, NFC_TAG_POCKET + 0.01, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    # Latch grooves in the end walls, matching the tile bumps with 0.15 mm clearance.
    wall_x = TILE_SIZE[0] / 2 + TILE_CLEARANCE
    groove_depth = TILE_BUMP - TILE_CLEARANCE + 0.15
    for sx in (-1, 1):
        cap -= Pos(sx * (wall_x + groove_depth / 2 - 0.01), 0, floor + TILE_THICKNESS / 2) * Box(
            groove_depth + 0.02, TILE_BUMP_LENGTH + 1.0, 1.3
        )
    # Fingernail notch on the back edge to pry the tile out.
    notch_y = TILE_SIZE[1] / 2 + TILE_CLEARANCE
    cap -= Pos(0, notch_y, floor) * Cylinder(5.0, TILE_RECESS_DEPTH + 1, align=_MIN_Z)
    return cap


def make_label_tile(text: str = "ESP32") -> Part:
    """Snap-in label tile for the NFC cap: flexible end bars with bumps, embossed text on top.

    Args:
        text: label text, embossed 0.6 mm for a colour swap at layer z = 1.6 mm.
    """
    w, _ = TILE_SIZE
    tile = extrude(_tile_outline(0.0), amount=TILE_THICKNESS)
    slot_w, slot_l = TILE_SLOT
    for sx in (-1, 1):
        slot_x = sx * (w / 2 - TILE_BAR - slot_w / 2)
        tile -= Pos(slot_x, 0, -0.5) * Box(slot_w, slot_l, TILE_THICKNESS + 1, align=_MIN_Z)
        bump = [(0, 0.3), (TILE_BUMP, 0.3 + TILE_BUMP), (TILE_BUMP, 1.3 - TILE_BUMP), (0, 1.3)]
        bump = [(-0.3, 0.3)] + bump + [(-0.3, 1.3)]
        bar = _profile_xz(bump, TILE_BUMP_LENGTH)
        tile += Pos(sx * w / 2, 0, 0) * (Rot(0, 0, 0 if sx > 0 else 180) * bar)
    label = Text(text, font_size=11, font_style=FontStyle.BOLD)
    tile += Pos(0, 0, TILE_THICKNESS - 0.01) * extrude(label, amount=TILE_TEXT_HEIGHT + 0.01)
    return tile


# Tool positions on a 2x2 rack: (x, y, shape) with shape = diameter or (len_x, len_y, radius).
RACK_TOOLS: tuple[tuple[float, float, float | tuple[float, float, float]], ...] = (
    (-27.0, 26.0, 9.0),  # screwdrivers, 6-8 mm shafts
    (-9.0, 26.0, 9.0),
    (9.0, 26.0, 9.0),
    (27.0, 26.0, 9.0),
    (-19.0, 2.0, (24.0, 13.0, 3.0)),  # flush cutter jaws
    (16.0, 2.0, (30.0, 17.0, 4.0)),  # wire stripper handles
    (-22.0, -24.0, (16.0, 4.5, 1.5)),  # tweezers
    (0.0, -24.0, (16.0, 4.5, 1.5)),
    (22.0, -24.0, (16.0, 4.5, 1.5)),
)


def make_tool_rack_cap() -> Part:
    """2x2 cap carrying a rack block with holes and slots for tools standing upright."""
    width = 2 * GRID - 2 * GAP
    cap = _solid_cap(2, 2, CLIP_CAP_TOP)
    block_w = width - 2 * RACK_INSET
    block = Pos(0, 0, CLIP_CAP_TOP - 0.5) * extrude(
        RectangleRounded(block_w, block_w, OUTER_RADIUS), amount=RACK_HEIGHT + 0.5
    )
    block = fillet(block.edges().group_by(Axis.Z)[-1], 2.0)
    cap += block
    cap -= _base_socket_cuts(2, 2)
    top = CLIP_CAP_TOP + RACK_HEIGHT
    depth = top - RACK_FLOOR
    for x, y, shape in RACK_TOOLS:
        if isinstance(shape, tuple):
            sx, sy, r = shape
            hole = extrude(RectangleRounded(sx, sy, r), amount=depth + 1)
        else:
            hole = Cylinder(shape / 2, depth + 1, align=_MIN_Z)
        cap -= Pos(x, y, RACK_FLOOR) * hole
    rims = cap.faces().sort_by(Axis.Z)[-1].inner_wires().edges()
    return chamfer(rims, 0.8)


def build() -> None:
    """Export every kit part into models/kit/."""
    save(
        MODULE,
        make_stack_clip(),
        PartInfo(
            slug="stack-clip",
            title="Stack clip",
            blurb=(
                "Bayonet clip that locks two stacked crates (or a crate and a handle cap) "
                "together at the seam, so the stack lifts as one and the clip cannot be pulled "
                "straight off. Fits every box height."
            ),
            material="PETG (PLA is too brittle for the hooks and detent finger)",
            print_notes=(
                "Print on its side, the detent-finger end (opposite the hooks) on the bed, so "
                "the hooks grow straight up from their stems; no supports, 100% infill, thin "
                f"walls / Arachne on (hooks are {NUB_DEPTH - HOOK_FRONT:.2f} mm). To fit: tab "
                "down, push both hooks into "
                "the socket windows, slide 5 mm the way the hooks point until the detent clicks. "
                "To remove: slide back 5 mm, pull the tab. Two per side, four per seam."
            ),
            color="#3d9df2",
        ),
    )
    for nx, ny in ((2, 2), (3, 2)):
        save(
            MODULE,
            make_tote_cap(nx, ny),
            PartInfo(
                slug=f"tote-cap-{nx}x{ny}",
                title=f"Tote handle cap {nx}x{ny}",
                blurb=(
                    "Cap with a carry handle and clip sockets: clip it to the top crate and the "
                    "whole stack becomes a grab-and-go tote."
                ),
                material="PETG",
                print_notes=(
                    "Print on its front face (-Y on the bed): the handle profile then has only "
                    "vertical walls and 45 deg window sides, and the L clip sockets only bridge "
                    "1.6 mm; no supports. 4 walls, 20% infill."
                ),
                color="#2bb673",
                footprint=f"{nx}x{ny}",
            ),
        )
    save(
        MODULE,
        make_nfc_cap(),
        PartInfo(
            slug="nfc-cap-2x2",
            title="NFC label cap 2x2",
            blurb=(
                "Lid hiding a 25 mm NTAG215 under a swappable label tile: tap a phone to open "
                "the box's inventory page."
            ),
            material="PETG or PLA",
            print_notes=(
                "Upright, no supports. Stick the NTAG215 in the round pocket, then snap the "
                "label tile over it."
            ),
            color="#9b6bf2",
            footprint="2x2",
        ),
    )
    save(
        MODULE,
        make_label_tile(),
        PartInfo(
            slug="nfc-label-tile",
            title="NFC label tile",
            blurb="Snap-in label tile with embossed text; covers the NFC tag in the NFC cap.",
            material="PLA or PETG, two colours",
            print_notes=(
                "Flat, text up, no supports. Filament swap at z = 1.6 mm for coloured text. "
                "Edit the text in make_label_tile()."
            ),
            color="#f2f2f2",
        ),
    )
    save(
        MODULE,
        make_tool_rack_cap(),
        PartInfo(
            slug="tool-rack-cap-2x2",
            title="Tool rack cap 2x2",
            blurb=(
                "Cap with a rack for four screwdrivers, flush cutters, wire strippers and three "
                "tweezers, so your hand tools ride on top of the stack."
            ),
            material="PETG (TPU 95A for a softer, rattle-free rack)",
            print_notes=(
                "Upright, no supports (the L clip sockets in the rim only bridge 0.6-1.2 mm). "
                "3 walls, 15% infill."
            ),
            color="#e85d4a",
            footprint="2x2",
        ),
    )


EPS = 1e-6
PROBE = 0.05  # growth of the leg box that measures hook engagement
SLIDE_STEPS = (0.0, 1.25, 2.5, 3.75, SLIDE)
OUT_STEPS = (0.25, 0.5, 1.0, 1.5, 2.0)


def _pose(x_face: float, y: float, seam_z: float) -> Location:
    """Locked clip pose on the socket pair at (x_face, y) around the seam at ``seam_z``."""
    return Pos(x_face, y, seam_z) * Rot(0, 0, 0 if x_face > 0 else 180)


def _hit(part: Part, solids: tuple[Part, ...]) -> float:
    return sum((part & solid).volume for solid in solids)


def _leg_probe(z_center: float) -> Part:
    """A socket's hidden leg (behind the skin) grown by PROBE, in the clip's local frame."""
    g = PROBE
    return _span_box(
        (-CLIP_SOCKET_DEPTH - g, -CLIP_SOCKET_SKIN + g),
        (SKIN_EDGE - g, CLIP_SOCKET_WIDTH / 2 + g),
        (z_center - CLIP_SOCKET_HEIGHT / 2 - g, z_center + CLIP_SOCKET_HEIGHT / 2 + g),
    )


def _hook_fractions(placed_clip: Part, pose: Location) -> list[float]:
    """Share of each designed hook volume found inside its socket's leg."""
    fractions = []
    for z in (LOWER_NUB_Z, UPPER_NUB_Z):
        expected = (_nub(z) & _leg_probe(z)).volume
        fractions.append((placed_clip & (pose * _leg_probe(z))).volume / expected)
    return fractions


def _clip_checks(
    pose: Location, boxes: tuple[Part, Part], clip: Part, nubs: Part
) -> tuple[dict[str, bool], list[float]]:
    """Run every locking check for one clip on one socket pair (lower box, upper part)."""

    def at(part: Part, out: float = 0.0, back: float = 0.0, dz: float = 0.0) -> Part:
        return pose * Pos(out, -back, dz) * part

    locked = at(clip)
    hooks = _hook_fractions(locked, pose)
    lifted = [at(clip, dz=dz) for dz in (-0.3, 0.3)]
    results = {
        "clear": _hit(locked, boxes) < EPS,
        "hooked": min(hooks) > 0.999,
        "pull-off": all((at(clip, out=0.5) & box).volume > EPS for box in boxes),
        "lift": all((part & box).volume > EPS for part in lifted for box in boxes),
        "detent": _hit(at(clip, back=0.5), boxes) > EPS > _hit(at(nubs, back=0.5), boxes),
        "slide": all(_hit(at(nubs, back=s), boxes) < EPS for s in SLIDE_STEPS),
        "removal": all(_hit(at(nubs, back=SLIDE, out=o), boxes) < EPS for o in OUT_STEPS)
        and _hit(at(clip, back=SLIDE, out=2.0), boxes) < EPS,
    }
    return results, hooks


def _report(label: str, results: dict[str, bool], hooks: list[float]) -> bool:
    failed = [name for name, passed in results.items() if not passed]
    verdict = "all ok" if not failed else "FAILED: " + ", ".join(failed)
    print(f"    {label} hooks in legs {hooks[0]:.3f}/{hooks[1]:.3f}, {verdict}")
    return not failed


def _crop(parts: tuple[Part, Part], pose: Location) -> tuple[Part, Part]:
    """The neighbourhood of one clip, so the many boolean checks stay fast."""
    region = pose * _span_box((-5.0, 5.0), (-CLIP_HALF_WIDTH - SLIDE - 3.0, 10.0), (-12.0, 12.0))
    return (parts[0] & region, parts[1] & region)


def _verify_seam(lower_size: BoxSize, lower: Part, upper: Part, seam_z: float) -> bool:
    """Clips on all four lip sockets of ``lower`` (base at seam_z - 7 * h) bridging to upper."""
    clip, nubs = make_stack_clip(), _nubs()
    lip_z = lower_size.lip_top - CLIP_SOCKET_LIP_Z
    ok = True
    for x, y, z in clip_socket_positions(lower_size):
        if z != lip_z:
            continue
        pose = _pose(x, y, seam_z)
        results, hooks = _clip_checks(pose, _crop((lower, upper), pose), clip, nubs)
        ok &= _report(f"clip seam z={seam_z:.0f} x={x:+.2f} y={y:+.2f}:", results, hooks)
    return ok


def _verify_clip_spacing(size: BoxSize, seam_lo: float, seam_hi: float) -> bool:
    """Clips on both seams of one box (base at seam_lo, lip at seam_hi) must not touch."""
    clip = make_stack_clip()
    worst = 0.0
    for x, y, _ in clip_socket_positions(size):
        worst = max(worst, (_pose(x, y, seam_lo) * clip & _pose(x, y, seam_hi) * clip).volume)
    print(f"    clips on both seams of the h={size.h} crate: intersection = {worst:.6f} mm^3")
    return worst < EPS


def _verify_stack(nx: int, ny: int, top_name: str, top: Part, top_clips: bool) -> bool:
    """Crate h=3 + crate h=2 + ``top`` at pitch 7 * h; locked clips on every socket pair."""
    low, mid = BoxSize(nx, ny, 3), BoxSize(nx, ny, 2)
    seam1 = low.h * HEIGHT_UNIT
    seam2 = seam1 + mid.h * HEIGHT_UNIT
    a = make_box(low)
    b = Pos(0, 0, seam1) * make_box(mid)
    cap = Pos(0, 0, seam2) * top
    print(f"  stack {nx}x{ny}: crate h3 @0, crate h2 @{seam1:.0f}, {top_name} @{seam2:.0f}")
    ok = True
    for label, p, q in (("h3 & h2", a, b), ("h2 & top", b, cap), ("h3 & top", a, cap)):
        v = (p & q).volume
        print(f"    {label:9s} intersection = {v:.6f} mm^3")
        ok &= v < EPS
    ok &= _verify_seam(low, a, b, seam1)
    if top_clips:
        ok &= _verify_seam(mid, b, cap, seam2)
        ok &= _verify_clip_spacing(mid, seam1, seam2)
    return ok


def _verify_wrong_hook() -> bool:
    """A clip with its hooks pointing -Y (mirrored) must fail the hook and pull-off checks."""
    low = BoxSize(2, 2, 3)
    seam = low.h * HEIGHT_UNIT
    lower, upper = make_box(low), Pos(0, 0, seam) * make_box(BoxSize(2, 2, 2))
    x, y, _ = clip_socket_positions(low)[0]
    pose = _pose(x, y, seam)
    wrong = mirror(make_stack_clip(), about=Plane.XZ)
    wrong_nubs = mirror(_nubs(), about=Plane.XZ)
    results, hooks = _clip_checks(pose, _crop((lower, upper), pose), wrong, wrong_nubs)
    _report(f"NEGATIVE: hooks toward -Y at x={x:+.2f} y={y:+.2f}:", results, hooks)
    caught = not results["hooked"] and not results["pull-off"]
    print(f"    negative control {'caught' if caught else 'NOT CAUGHT'}")
    return caught


def verify() -> bool:
    """Assemble 3-high stacks with locked clips and print interference / locking results."""
    ok = True
    for name, part in (
        ("stack-clip", make_stack_clip()),
        ("tote-cap-2x2", make_tote_cap(2, 2)),
        ("tote-cap-3x2", make_tote_cap(3, 2)),
        ("nfc-cap-2x2", make_nfc_cap()),
        ("nfc-label-tile", make_label_tile()),
        ("tool-rack-cap-2x2", make_tool_rack_cap()),
    ):
        bb = part.bounding_box()
        print(
            f"{name:20s} valid={part.is_valid}  {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f}"
        )
        ok &= part.is_valid
    ok &= _verify_stack(2, 2, "tote-cap-2x2", make_tote_cap(2, 2), top_clips=True)
    ok &= _verify_stack(3, 2, "tote-cap-3x2", make_tote_cap(3, 2), top_clips=True)
    ok &= _verify_stack(2, 2, "tool-rack-cap", make_tool_rack_cap(), top_clips=True)
    ok &= _verify_stack(2, 2, "nfc-cap", make_nfc_cap(), top_clips=False)
    ok &= _verify_wrong_hook()
    ok &= _verify_nfc()
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return ok


def _verify_nfc() -> bool:
    cap = make_nfc_cap()
    top = FOOT_HEIGHT + CAP_PLATE
    floor = top - TILE_RECESS_DEPTH
    tag_z = floor - NFC_TAG_POCKET
    tag_r = 12.5
    tag = Pos(0, 0, tag_z) * Cylinder(tag_r, 0.5, align=_MIN_Z)
    below = Cylinder(tag_r, tag_z, align=_MIN_Z)
    tile = Pos(0, 0, floor) * make_label_tile()
    above = Pos(0, 0, tag_z + 0.5) * Cylinder(tag_r, 10, align=_MIN_Z)
    solid_below = (cap & below).volume / (math.pi * tag_r**2)
    solid_above = (tile & above).volume / (math.pi * tag_r**2)
    clash = (cap & tag).volume + (cap & tile).volume
    print(f"  NFC: plastic below tag = {solid_below:.2f} mm, tile above tag = {solid_above:.2f} mm")
    print(f"  NFC: tag/tile vs cap intersection = {clash:.6f} mm^3")
    return clash < 1e-6 and solid_below >= 0.6 and solid_above >= 0.6


if __name__ == "__main__":
    build()
    verify()
