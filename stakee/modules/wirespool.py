"""Wire dispenser: a crate that holds hookup-wire spools on an axle, with one eyelet per spool.

Pull the colour you need through its eyelet in the front (-Y) wall; the spools spin
independently on a lift-out axle, so nothing tangles.

Parts: the crate (core box + eyelet ledge + eyelets + optional snip slot), a drop-in cradle
frame with two open-top U-cradles, a printed axle (or an 8 mm steel / M8 threaded rod) and
spacer washers. Everything is parametric in ``SpoolSpec``; the footprint and height are
the smallest that fit, so ``uv run python -m stakee.modules.wirespool`` re-plans the whole
dispenser for your spools once you edit ``DEFAULT_SPOOLS``.

Default spools: the common 6-colour 22 AWG kits (TUOFENG, Etokfoks...) ship six 9 m spools
in a ~145 x 55 x 55 mm box, so each spool is about 52 mm across the flanges and 23 mm wide.
Six of those need 158.5 mm of axle span, more than a 3-wide crate's 121.5 mm cavity: the
dispenser is 4x2. A 3x2 dispenser fits six spools up to ~16.7 mm wide (see verify()).
"""

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    Box,
    CenterArc,
    Cylinder,
    GeomType,
    Line,
    Part,
    Plane,
    Polygon,
    Pos,
    RectangleRounded,
    Rot,
    chamfer,
    extrude,
    make_face,
    revolve,
)

from stakee.core import (
    FLOOR_Z,
    FOOT_HEIGHT,
    HEIGHT_UNIT,
    LABEL_HEIGHT,
    SEAT_DEPTH,
    WALL,
    BoxSize,
    label_z,
    make_box,
    make_cap,
)
from stakee.export import PartInfo, save

MODULE = "wirespool"

MIN = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class SpoolSpec:
    """What you are storing: measure one of your spools with calipers.

    Attributes:
        diameter: flange diameter, mm.
        width: overall width across both flanges, mm.
        hole: centre hole diameter, mm (must clear the axle by >= 0.5 mm).
        count: number of spools on the axle.
        axle: axle diameter, mm: 8 = printed rod, 8 mm steel rod or M8 threaded rod;
            set 5 or 6 for M5 / M6 threaded rod and the U-cradles shrink to match.
        washer: spacer washer thickness between spools, mm; 0 drops the washers.
    """

    diameter: float = 52.0
    width: float = 23.0
    hole: float = 12.0
    count: int = 6
    axle: float = 8.0
    washer: float = 1.5


DEFAULT_SPOOLS = SpoolSpec()

CLEARANCE = 0.3  # per side, cradle frame outline to cavity wall
PLAY = 0.3  # modelled axial gap between neighbouring spools / washers
END_GAP = 1.0  # outer spool flange to cradle upright
SPOOL_FLOOR_GAP = 2.0  # lowest flange point above the crate floor
TOP_MARGIN = 1.0  # spool top below the stacking seat, at least
REST_GAP = 0.02  # resting contacts are modelled 0.02 mm apart so booleans stay robust

UPRIGHT_T = 4.0  # cradle upright thickness (X)
UPRIGHT_TOP_HALF = 9.0  # half-width (Y) of the upright at its top
U_CLEAR = 0.3  # radial play of the axle in the U-cradle
U_ABOVE_AXLE = 1.5  # upright top above the axle top
U_MOUTH = 0.6  # 45 deg lead-in chamfer at the U mouth
RAIL_W = 6.0  # floor rails tying the uprights together (Y)
RAIL_H = 3.0
FRAME_RADIUS = 2.0  # >= cavity corner radius (1.75) so the frame corners never bind

AXLE_WALL_GAP = 1.0  # axle end to crate inner wall: the axle can slide 1 mm at most
AXLE_FLAT = 0.5  # flat on the printed axle so it prints lying down without supports

WASHER_ID_PLAY = 0.6  # washer bore over the axle diameter
WASHER_OD_OVER_HOLE = 6.0  # washer OD over the spool hole, so it bears on the flange hub

EYELET_BORE = 2.6  # AWG22 insulation is 1.55-1.8 mm OD; printed holes shrink ~0.2 mm
EYELET_ROUND = 0.8  # outer edge radius, so insulation slides over a smooth curve
EYELET_LEAD_IN = 1.2  # inner 45 deg lead-in chamfer
LEDGE_DEPTH = 4.0  # eyelet ledge on the inside of the front wall: 6 mm long eyelets
LEDGE_HALF = 5.0  # ledge half-height around the eyelet axis (plus a 45 deg underside)
LEDGE_END = 6.0  # ledge reaches this far past the outer eyelets (X)

SNIP_WIDTH = 1.2  # pinch slot: grips 1.55-1.8 mm insulation, parks the free end
SNIP_DEPTH = 3.0  # into wall + ledge (6 mm), leaves 3 mm behind the slot
SNIP_MOUTH = 0.8  # V lead-in at the face
SNIP_HALF_HEIGHT = 4.0

LABEL_MIN_GAP = 3.0  # eyelet flare to label recess, at least

EYELET_TOLERANCE = 0.5  # max eyelet-axis offset from its spool centre (X and Z), mm


@dataclass(frozen=True)
class Layout:
    """Where everything goes, in crate coordinates (crate bottom at z = 0)."""

    spec: SpoolSpec
    size: BoxSize
    axle_z: float
    spool_z: float
    spool_xs: tuple[float, ...]
    washer_xs: tuple[float, ...]
    upright_x: float  # center of the +X upright (the other is mirrored)

    @property
    def seat(self) -> float:
        return self.size.lip_top - SEAT_DEPTH


def _stack_length(spec: SpoolSpec) -> float:
    return spec.count * spec.width + (spec.count - 1) * _between(spec)


def _between(spec: SpoolSpec) -> float:
    return 2 * PLAY + spec.washer if spec.washer > 0 else PLAY


def _frame_span(spec: SpoolSpec) -> float:
    """Outer-to-outer distance of the two cradle uprights."""
    return _stack_length(spec) + 2 * (END_GAP + UPRIGHT_T)


def _fits(spec: SpoolSpec, size: BoxSize) -> bool:
    cav_w, cav_d, _ = size.cavity
    wide = _frame_span(spec) + 2 * CLEARANCE <= cav_w
    deep = spec.diameter / 2 + max(RAIL_W, LEDGE_DEPTH) + CLEARANCE + 1.0 <= cav_d / 2
    return wide and deep


def plan(spec: SpoolSpec) -> Layout:
    """Pick the smallest crate that fits ``spec`` and place spools, washers, axle and cradles.

    Args:
        spec: the spools to store.

    Returns:
        The layout in crate coordinates.

    Raises:
        ValueError: if the spool hole does not clear the axle or nothing up to 8x8 fits.
    """
    if spec.hole < spec.axle + 0.5:
        raise ValueError(
            f"spool hole {spec.hole} mm must clear the {spec.axle} mm axle by >= 0.5 mm; "
            "use a thinner axle (SpoolSpec.axle=5 or 6 for M5/M6 threaded rod)"
        )
    spool_z = FLOOR_Z + SPOOL_FLOOR_GAP + spec.diameter / 2
    axle_z = spool_z + (spec.hole - spec.axle) / 2 - REST_GAP
    top = max(
        spool_z + spec.diameter / 2, axle_z + spec.axle / 2 + U_CLEAR + U_ABOVE_AXLE + REST_GAP
    )
    h = max(2, math.ceil((top + TOP_MARGIN) / HEIGHT_UNIT))
    by_area = sorted(
        ((nx, ny) for nx in range(1, 9) for ny in range(1, 9)), key=lambda n: (n[0] * n[1], n[1])
    )
    fitting = [BoxSize(nx, ny, h) for nx, ny in by_area if _fits(spec, BoxSize(nx, ny, h))]
    if not fitting:
        raise ValueError(f"{spec} does not fit any crate up to 8x8; use fewer spools")
    stack = _stack_length(spec)
    pitch = spec.width + _between(spec)
    spool_xs = tuple(-stack / 2 + spec.width / 2 + i * pitch for i in range(spec.count))
    washer_offset = spec.width / 2 + PLAY + spec.washer / 2
    washer_xs = tuple(x + washer_offset for x in spool_xs[:-1]) if spec.washer > 0 else ()
    return Layout(
        spec=spec,
        size=fitting[0],
        axle_z=axle_z,
        spool_z=spool_z,
        spool_xs=spool_xs,
        washer_xs=washer_xs,
        upright_x=stack / 2 + END_GAP + UPRIGHT_T / 2,
    )


def eyelet_cutter(length: float) -> Part:
    """Revolved eyelet bore along +Z from the outer face (z = 0) to the inner face (z = length).

    Outer end: the material edge is rounded with EYELET_ROUND; inner end: 45 deg lead-in.
    """
    r0, rf, c, over = EYELET_BORE / 2, EYELET_ROUND, EYELET_LEAD_IN, 0.3
    edges = [
        Line((0, -over), (r0 + rf, -over)),
        Line((r0 + rf, -over), (r0 + rf, 0)),
        CenterArc((r0 + rf, rf), rf, 270, -90),
        Line((r0, rf), (r0, length - c)),
        Line((r0, length - c), (r0 + c, length)),
        Line((r0 + c, length), (r0 + c, length + over)),
        Line((r0 + c, length + over), (0, length + over)),
        Line((0, length + over), (0, -over)),
    ]
    return revolve(Plane.XZ * make_face(edges), Axis.Z)


def _ledge(lay: Layout) -> Part:
    """Eyelet ledge on the inner front wall, 45 deg underside so it prints without supports."""
    _, cav_d, _ = lay.size.cavity
    y0, z = -cav_d / 2, lay.spool_z
    bottom = z - LEDGE_HALF - LEDGE_DEPTH
    outline = [
        (y0 - 0.5, bottom),
        (y0, bottom),
        (y0 + LEDGE_DEPTH, z - LEDGE_HALF),
        (y0 + LEDGE_DEPTH, z + LEDGE_HALF),
        (y0 - 0.5, z + LEDGE_HALF),
    ]
    x0, x1 = lay.spool_xs[0] - LEDGE_END, lay.spool_xs[-1] + LEDGE_END
    ledge = extrude(Plane.YZ * Polygon(*outline, align=None), amount=x1 - x0)
    return Pos(x0, 0, 0) * ledge


def snip_x(lay: Layout) -> float:
    """X of the snip slot: between the two middle eyelets (or beside a lone one)."""
    xs = lay.spool_xs
    if len(xs) < 2:
        return xs[0] + lay.spec.width / 2
    k = len(xs) // 2 - 1
    return (xs[k] + xs[k + 1]) / 2


def _snip_slot(lay: Layout) -> Part:
    """Vertical pinch slot open to the front face, with a V mouth."""
    front = -lay.size.depth / 2
    m, w, d = SNIP_MOUTH, SNIP_WIDTH / 2, SNIP_DEPTH
    outline = [(-w - m, -0.3), (-w - m, 0), (-w, m), (-w, d), (w, d), (w, m), (w + m, 0)]
    outline.append((w + m, -0.3))
    slot = extrude(Polygon(*outline, align=None), amount=SNIP_HALF_HEIGHT, both=True)
    return Pos(snip_x(lay), front, lay.spool_z) * slot


def eyelet_axes(lay: Layout) -> list[tuple[float, float]]:
    """Designed (x, z) of each eyelet axis: under each spool centre."""
    return [(x, lay.spool_z) for x in lay.spool_xs]


def _label_gap(lay: Layout) -> float:
    """Distance from the eyelet flare top to core's label recess bottom on the front face."""
    label_bottom = label_z(lay.size) - LABEL_HEIGHT / 2
    return label_bottom - (lay.spool_z + EYELET_BORE / 2 + EYELET_ROUND)


def make_crate(lay: Layout, snip: bool = True) -> Part:
    """Core box (no divider slots) with an eyelet ledge, one eyelet per spool, a snip slot.

    The core label recess is kept when it clears the eyelets by LABEL_MIN_GAP, else dropped.

    Args:
        lay: the dispenser layout from plan().
        snip: cut the wire-parking pinch slot between the middle eyelets.
    """
    label = _label_gap(lay) >= LABEL_MIN_GAP
    crate = make_box(lay.size, dividers=False, label=label) + _ledge(lay)
    length = WALL + LEDGE_DEPTH
    cutter = eyelet_cutter(length)
    front = -lay.size.depth / 2
    for x, z in eyelet_axes(lay):
        crate -= Pos(x, front, z) * (Rot(-90, 0, 0) * cutter)
    if snip:
        crate -= _snip_slot(lay)
    return crate


def _upright(lay: Layout, half_d: float) -> Part:
    """One cradle upright in frame coordinates (frame bottom at z = 0), centred on x = 0."""
    axle_r = lay.spec.axle / 2
    u_r = axle_r + U_CLEAR
    u_center = lay.axle_z - FLOOR_Z + U_CLEAR - REST_GAP  # the axle rests 0.02 mm above
    top = lay.axle_z - FLOOR_Z + axle_r + U_ABOVE_AXLE
    outline = [(-half_d, 0), (half_d, 0), (UPRIGHT_TOP_HALF, top), (-UPRIGHT_TOP_HALF, top)]
    upright = extrude(Plane.YZ * Polygon(*outline, align=None), amount=UPRIGHT_T / 2, both=True)
    slot = Pos(0, 0, u_center) * Box(UPRIGHT_T + 2, 2 * u_r, top, align=MIN)
    slot += Pos(0, 0, u_center) * (Rot(0, 90, 0) * Cylinder(u_r, UPRIGHT_T + 2))
    upright -= slot
    mouth = (
        upright.edges()
        .filter_by(Axis.X)
        .filter_by(lambda e: abs(e.center().Z - top) < 1e-6 and abs(abs(e.center().Y) - u_r) < 1e-6)
    )
    return chamfer(mouth, U_MOUTH)


def make_cradle_frame(lay: Layout) -> Part:
    """Drop-in frame: two U-cradle uprights hugging the spool stack, joined by floor rails.

    The rails run the full cavity length, so the frame (and with it every spool) is located
    in X by the crate's end walls and the eyelets stay aligned. Frame bottom at z = 0;
    it sits on the crate floor at z = FLOOR_Z.
    """
    cav_w, cav_d, _ = lay.size.cavity
    length, depth = cav_w - 2 * CLEARANCE, cav_d - 2 * CLEARANCE
    frame = None
    for sy in (-1, 1):
        rail = Pos(0, sy * (depth / 2 - RAIL_W / 2), 0) * Box(length, RAIL_W, RAIL_H, align=MIN)
        frame = rail if frame is None else frame + rail
    for sx in (-1, 1):
        frame += Pos(sx * lay.upright_x, 0, 0) * _upright(lay, depth / 2)
    outline = extrude(RectangleRounded(length, depth, FRAME_RADIUS), amount=200)
    return frame & outline


def make_axle(lay: Layout) -> Part:
    """Axle rod along X with a flat underneath (prints lying on the flat). Flat at z = 0."""
    cav_w, _, _ = lay.size.cavity
    r = lay.spec.axle / 2
    rod = Cylinder(r, cav_w - 2 * AXLE_WALL_GAP)
    rod = Rot(0, 90, 0) * chamfer(rod.edges().filter_by(GeomType.CIRCLE), 0.6)
    rod -= Pos(0, 0, -r) * Box(cav_w, 2 * r, 2 * AXLE_FLAT, align=(Align.CENTER,) * 3)
    return Pos(0, 0, r - AXLE_FLAT) * rod


def axle_z_offset(lay: Layout) -> float:
    """z at which the exported axle (flat at z = 0) sits in the crate."""
    return lay.axle_z - lay.spec.axle / 2 + AXLE_FLAT


def washer_dims(spec: SpoolSpec) -> tuple[float, float]:
    """(inner, outer) washer diameters."""
    return spec.axle + WASHER_ID_PLAY, spec.hole + WASHER_OD_OVER_HOLE


def make_washer(spec: SpoolSpec) -> Part:
    """Flat spacer washer, axis Z, bottom at z = 0."""
    inner, outer = washer_dims(spec)
    return Cylinder(outer / 2, spec.washer, align=MIN) - Cylinder(inner / 2, spec.washer, align=MIN)


def spool_dummy(spec: SpoolSpec) -> Part:
    """Stand-in spool envelope: flange cylinder with its centre hole, axis X, centred."""
    body = Cylinder(spec.diameter / 2, spec.width) - Cylinder(spec.hole / 2, spec.width + 1)
    return Rot(0, 90, 0) * body


def _tag(lay: Layout) -> str:
    return f"{lay.size.nx}x{lay.size.ny}x{lay.size.h}"


def _infos(lay: Layout) -> dict[str, PartInfo]:
    spec, tag = lay.spec, _tag(lay)
    inner, outer = washer_dims(spec)
    spools = f"{spec.count} spools of {spec.diameter:g} x {spec.width:g} mm (hole {spec.hole:g})"
    return {
        "crate": PartInfo(
            slug=f"wire-dispenser-{tag}",
            title=f"Wire dispenser crate {tag}",
            blurb=(
                f"Holds {spools} on a lift-out axle; pull each colour through its own rounded "
                "eyelet in the front wall. Pinch slot between the middle eyelets parks a cut end."
            ),
            material="PLA or PETG",
            print_notes=(
                "Upright, no supports: the eyelet ledge has a 45 deg underside and the 2.6 mm "
                "eyelets bridge cleanly. 3 walls, 15% infill. Ream eyelets with a 2.5 mm drill "
                "if your printer runs tight. No divider slots on this variant."
            ),
            color="#c9a227",
            footprint=tag,
        ),
        "frame": PartInfo(
            slug=f"wire-cradle-frame-{tag}",
            title=f"Spool cradle frame {tag}",
            blurb=(
                "Drops onto the dispenser floor: two open-top U-cradles hold the axle so you "
                "lift the whole spool set out to swap one. Rails locate it against the end walls."
            ),
            material="PETG (PLA ok)",
            print_notes="Flat on its rails, U-cradles up, no supports. 3 walls, 20% infill.",
            color="#0f8b8d",
            footprint=f"{lay.size.nx}x{lay.size.ny}",
        ),
        "axle": PartInfo(
            slug=f"wire-axle-{spec.axle:g}mm",
            title=f"Spool axle {spec.axle:g} mm",
            blurb=(
                f"{spec.axle:g} mm rod, {lay.size.cavity[0] - 2 * AXLE_WALL_GAP:.1f} mm long. "
                f"Or skip printing: cut an {spec.axle:g} mm steel rod or M{spec.axle:g} threaded "
                "rod to the same length."
            ),
            material="PETG (stiffer and less creep-prone than PLA under the spool load)",
            print_notes=(
                f"Lying on its {AXLE_FLAT} mm flat along X, no supports, 4 walls, 40% infill; "
                "needs a bed at least 165 mm long (print diagonally on smaller beds)."
            ),
            color="#1d3557",
        ),
        "washer": PartInfo(
            slug=f"wire-spool-washer-{spec.axle:g}mm",
            title="Spool spacer washer",
            blurb=(
                f"{outer:g}/{inner:g} x {spec.washer:g} mm washer between neighbouring spools "
                f"so each spins on its own. Print {len(lay.washer_xs)}."
            ),
            material="PETG",
            print_notes="Flat, no supports, 100% infill. Smooth side (bed side) toward a spool.",
            color="#8d99ae",
        ),
    }


def build(spec: SpoolSpec = DEFAULT_SPOOLS) -> Layout:
    """Plan the dispenser for ``spec`` and export crate, cradle frame, axle and washer.

    Args:
        spec: the spools to store.

    Returns:
        The layout used, for verification.
    """
    lay = plan(spec)
    infos = _infos(lay)
    save(MODULE, make_crate(lay), infos["crate"])
    save(MODULE, make_cradle_frame(lay), infos["frame"])
    save(MODULE, make_axle(lay), infos["axle"])
    if spec.washer > 0:
        save(MODULE, make_washer(spec), infos["washer"])
    return lay


# --- verification -------------------------------------------------------------------------


def assemble(lay: Layout, shift_spool: tuple[int, float] | None = None) -> dict[str, Part]:
    """Every part placed in crate coordinates; spools are stand-in envelopes.

    Args:
        lay: the layout.
        shift_spool: (index, dx) to deliberately misplace one spool (for the self-test).
    """
    spec = lay.spec
    parts = {
        "crate": make_crate(lay),
        "frame": Pos(0, 0, FLOOR_Z) * make_cradle_frame(lay),
        "axle": Pos(0, 0, axle_z_offset(lay)) * make_axle(lay),
    }
    washer = Rot(0, 90, 0) * Pos(0, 0, -spec.washer / 2) * make_washer(spec)
    washer_z = lay.axle_z - (washer_dims(spec)[0] - spec.axle) / 2 + REST_GAP
    for i, x in enumerate(lay.washer_xs):
        parts[f"washer{i}"] = Pos(x, 0, washer_z) * washer
    spool = spool_dummy(spec)
    for i, x in enumerate(lay.spool_xs):
        dx = shift_spool[1] if shift_spool and shift_spool[0] == i else 0.0
        parts[f"spool{i}"] = Pos(x + dx, 0, lay.spool_z) * spool
    return parts


def _bbox_overlap(a: Part, b: Part) -> bool:
    ba, bb = a.bounding_box(), b.bounding_box()
    lo_a, hi_a, lo_b, hi_b = tuple(ba.min), tuple(ba.max), tuple(bb.min), tuple(bb.max)
    return all(lo_a[k] < hi_b[k] and lo_b[k] < hi_a[k] for k in range(3))


def interferences(parts: dict[str, Part]) -> list[tuple[str, str, float]]:
    """Every pair of parts whose intersection volume exceeds 1e-6 mm^3."""
    names = list(parts)
    clashes = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if not _bbox_overlap(parts[a], parts[b]):
                continue
            v = (parts[a] & parts[b]).volume
            if v > 1e-6:
                clashes.append((a, b, v))
    return clashes


def measured_eyelets(crate: Part, lay: Layout) -> list[tuple[float, float]]:
    """(x, z) of each eyelet bore axis, read back from the crate's cylindrical faces."""
    axes = {}
    for face in crate.faces().filter_by(GeomType.CYLINDER):
        if abs(face.radius - EYELET_BORE / 2) > 1e-6:
            continue
        axis = face.axis_of_rotation
        if abs(abs(axis.direction.Y) - 1) > 1e-6:
            continue
        axes[round(axis.position.X, 3)] = (axis.position.X, axis.position.Z)
    return [axes[k] for k in sorted(axes)]


def eyelet_offsets(lay: Layout, parts: dict[str, Part]) -> list[tuple[float, float]]:
    """(dx, dz) of each measured eyelet axis from its spool's measured centre."""
    eyelets = measured_eyelets(parts["crate"], lay)
    if len(eyelets) != lay.spec.count:
        raise ValueError(f"found {len(eyelets)} eyelet bores, expected {lay.spec.count}")
    offsets = []
    for i, (ex, ez) in enumerate(eyelets):
        centre = parts[f"spool{i}"].bounding_box().center()
        offsets.append((ex - centre.X, ez - centre.Z))
    return offsets


def _check_assembly(lay: Layout, parts: dict[str, Part]) -> bool:
    clashes = interferences(parts)
    print(f"  pairwise interference ({len(parts)} solids): {len(clashes)} clashes")
    for a, b, v in clashes:
        print(f"    CLASH {a} & {b}: {v:.4f} mm^3")
    inside = {k: p for k, p in parts.items() if k != "crate"}
    top = max(p.bounding_box().max.Z for p in inside.values())
    print(f"  highest internal point {top:.2f} mm, seat {lay.seat:.2f} mm")
    upper = Pos(0, 0, lay.size.h * HEIGHT_UNIT) * make_box(BoxSize(lay.size.nx, lay.size.ny, 3))
    cap = Pos(0, 0, lay.size.h * HEIGHT_UNIT) * make_cap(lay.size.nx, lay.size.ny)
    stack = max((upper & p).volume for p in parts.values())
    stack = max(stack, max((cap & p).volume for p in parts.values()))
    print(
        f"  box h3 / cap stacked at z={lay.size.h * HEIGHT_UNIT:.0f}: max intersection {stack:.6f}"
    )
    offsets = eyelet_offsets(lay, parts)
    worst = max(max(abs(dx), abs(dz)) for dx, dz in offsets)
    print(
        "  eyelet axis - spool centre (dx, dz): "
        + ", ".join(f"({dx:+.3f}, {dz:+.3f})" for dx, dz in offsets)
    )
    return not clashes and top < lay.seat and stack < 1e-6 and worst <= EYELET_TOLERANCE


def verify(spec: SpoolSpec = DEFAULT_SPOOLS) -> bool:
    """Print validity, interference, stacking and eyelet checks plus a broken-placement test."""
    lay = plan(spec)
    print(f"wirespool: {spec}")
    print(f"  crate {_tag(lay)}, axle z={lay.axle_z:.2f}, spool centre z={lay.spool_z:.2f}")
    cav_w = lay.size.cavity[0]
    print(f"  axle span needed {_frame_span(spec) + 2 * CLEARANCE:.1f} mm of {cav_w:.1f} mm cavity")
    ok = True
    for name, part in (
        ("crate", make_crate(lay)),
        ("cradle-frame", make_cradle_frame(lay)),
        ("axle", make_axle(lay)),
        ("washer", make_washer(spec)),
    ):
        bb = part.bounding_box()
        dims = f"{bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f}"
        print(f"  {name:13s} valid={part.is_valid}  {dims}")
        ok &= part.is_valid
    gap = _label_gap(lay)
    print(f"  eyelet flare to label recess: {gap:.1f} mm (label kept: {gap >= LABEL_MIN_GAP})")
    feet_gap = lay.spool_z - EYELET_BORE / 2 - EYELET_ROUND - FOOT_HEIGHT
    print(f"  eyelet flare above the feet: {feet_gap:.1f} mm")
    parts = assemble(lay)
    ok &= _check_assembly(lay, parts)
    print("  self-test: spool 2 shifted +1.0 mm in X")
    caught = not _check_assembly(lay, assemble(lay, shift_spool=(2, 1.0)))
    print(f"  self-test {'caught the misplacement' if caught else 'MISSED the misplacement'}")
    ok &= caught
    narrow = _max_width(BoxSize(3, 2, lay.size.h), spec)
    print(f"  a 3x2 dispenser fits {spec.count} spools up to {narrow:.1f} mm wide")
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return ok


def _max_width(size: BoxSize, spec: SpoolSpec) -> float:
    """Widest spool for which ``spec.count`` spools still fit across ``size``."""
    cav_w = size.cavity[0]
    fixed = (spec.count - 1) * _between(spec) + 2 * (END_GAP + UPRIGHT_T + CLEARANCE)
    return (cav_w - fixed) / spec.count


if __name__ == "__main__":
    build()
    verify()
