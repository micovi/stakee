"""Calibration coupons: a small, cheap test print that picks the tolerances for YOUR printer.

Parts:
- Lip coupons: 1x1x2 boxes (the shortest box the system allows), one per value in
  CLEARANCES, with the clearance in hundredths of a mm debossed on the front ("25" = 0.25).
  Every optional box feature is off and the floor has a window, to save filament and time.
- Probe: a plain default 1x1x2 box; its feet are the gauge tried in every coupon.
- Slot strip: an L of crate wall with a core divider slot in an X wall and in a Y wall.
- Slot samples: a comb of divider ends (the 1.2 mm plate, then the thick-end candidates)
  printed flat like the real dividers, each finger labelled with its thickness.

Lower limit: a foot's vertical face sits 2.15 mm in from the cell outline and the wall is
2.0 mm thick, so below 0.15 mm of lip clearance the cavity wall, not the lip, sets the play.

Rerun with other values: ``uv run python -m stakee.modules.calibration --clearances 0.2 0.3``.
"""

import argparse

from build123d import (
    Align,
    Box,
    FontStyle,
    Location,
    Part,
    Plane,
    Pos,
    RectangleRounded,
    Rot,
    Text,
    extrude,
)

from stakee.core import (
    DIVIDER_SLOT_DEPTH,
    DIVIDER_SLOT_WIDTH,
    DIVIDER_THICKNESS,
    FOOT_STATIONS,
    HEIGHT_UNIT,
    LIP_CLEARANCE,
    SEAT_DEPTH,
    WALL,
    BoxSize,
    make_box,
)
from stakee.export import PartInfo, save
from stakee.modules.dividers import END_LENGTH, END_THICKNESS, INSERT

MODULE = "calibration"

COUPON = BoxSize(1, 1, 2)
CLEARANCES = (0.15, 0.25, 0.35)
MIN_CLEARANCE = FOOT_STATIONS[1][1] - WALL  # foot vertical face inset minus the wall
MAX_CLEARANCE = 0.99  # the label has two digits
COUPON_COLORS = ("#e05d5d", "#f0c419", "#5dbb63", "#4fb3bf", "#7d8ce0", "#c47ed6")
WINDOW = 26.0  # floor window of a coupon; the feet keep a 4.8 mm ring on the bed
WINDOW_RADIUS = 4.0
DEBOSS = 0.6
MIN_BACKING = 0.8  # material that must remain behind any debossed label
COUPON_FONT = 7.0
COUPON_TEXT_Z = 9.5  # on the full 2 mm front wall: above the foot, below the lip pocket

SLOT_SAMPLES = (DIVIDER_THICKNESS, 1.4, 1.5, 1.55)
STRIP_SIDE = 22.0
STRIP_BASE = 2.0  # stands in for the crate floor; slots start on top of it, as in a crate
STRIP_WALL_HEIGHT = 12.0
SLOT_FROM_CORNER = 11.0  # slot center to the inner corner of the L
FINGER_WIDTH = 8.0  # along the slot when inserted
FINGER_LENGTH = 10.0
FINGER_PITCH = 12.0
HANDLE_DEPTH = 10.0
HANDLE_THICKNESS = 2.4
COMB_FONT = 4.5
PROBE_Z = 1.0  # sample finger height above the strip floor during verification

EPS = 1e-6


def coupon_label(clearance: float) -> str:
    """Debossed coupon mark: the clearance in hundredths of a mm, e.g. 0.25 -> "25"."""
    return f"{round(clearance * 100):02d}"


def check_clearances(clearances: tuple[float, ...]) -> None:
    """Fail fast on clearances the coupon cannot represent or label unambiguously."""
    for c in clearances:
        if not MIN_CLEARANCE - EPS <= c <= MAX_CLEARANCE:
            raise ValueError(
                f"lip clearance {c} outside {MIN_CLEARANCE:.2f}..{MAX_CLEARANCE}: below "
                f"{MIN_CLEARANCE:.2f} the {WALL} mm cavity wall, not the lip, sets the play"
            )
    labels = [coupon_label(c) for c in clearances]
    if len(set(labels)) != len(labels):
        raise ValueError(f"clearances {clearances} share labels {labels}; use 0.01 mm steps")


def _text_prism(label: str, plane: Plane, font: float, top: float, bottom: float) -> Part:
    """Bold text on ``plane``, filled from ``top`` to ``bottom`` along its normal (outward +)."""
    text = plane.offset(top) * Text(label, font_size=font, font_style=FontStyle.BOLD)
    return extrude(text, amount=bottom - top)


def _deboss(label: str, plane: Plane, font: float, depth: float) -> Part:
    return _text_prism(label, plane, font, 0.01, -depth)


def coupon_text_plane(size: BoxSize = COUPON) -> Plane:
    """Front face of a coupon (normal -Y, text upright when seen from the front)."""
    return Plane(origin=(0, -size.depth / 2, COUPON_TEXT_Z), x_dir=(1, 0, 0), z_dir=(0, -1, 0))


def make_coupon(clearance: float, deboss: float = DEBOSS) -> Part:
    """Lip-only 1x1x2 test box: no magnets, slots, sockets or label; windowed floor.

    Args:
        clearance: lip clearance under test, passed to make_box(lip_clearance=...).
        deboss: depth of the front label; must leave MIN_BACKING of the 2 mm wall.
    """
    coupon = make_box(
        COUPON,
        magnets=False,
        dividers=False,
        clip_sockets=False,
        label=False,
        lip_clearance=clearance,
    )
    coupon -= Pos(0, 0, -0.01) * extrude(RectangleRounded(WINDOW, WINDOW, WINDOW_RADIUS), 10)
    return coupon - _deboss(coupon_label(clearance), coupon_text_plane(), COUPON_FONT, deboss)


def make_probe() -> Part:
    """The gauge: a plain default 1x1x2 box, exactly what a real stack puts on a lip."""
    return make_box(COUPON)


def slot_frames() -> list[Location]:
    """Slot mouths of the strip: origin on the floor, -Y into the wall, +Z along the slot."""
    inner = STRIP_SIDE / 2 - WALL
    return [
        Location((-inner + SLOT_FROM_CORNER, inner, STRIP_BASE), (0, 0, 180)),  # back wall
        Location((-inner, inner - SLOT_FROM_CORNER, STRIP_BASE), (0, 0, -90)),  # left wall
    ]


def make_slot_strip() -> Part:
    """Floor plus an L of 2 mm wall with one core divider slot in each leg."""
    half = STRIP_SIDE / 2
    height = STRIP_BASE + STRIP_WALL_HEIGHT
    corner = (Align.MAX, Align.MAX, Align.MIN)
    strip = Box(STRIP_SIDE, STRIP_SIDE, STRIP_BASE, align=(Align.CENTER, Align.CENTER, Align.MIN))
    strip += Pos(half, half, 0) * Box(STRIP_SIDE, WALL, height, align=corner)
    strip += Pos(-half + WALL, half, 0) * Box(WALL, STRIP_SIDE, height, align=corner)
    slot = Pos(0, 0.01, 0) * Box(
        DIVIDER_SLOT_WIDTH,
        DIVIDER_SLOT_DEPTH + 0.01,
        STRIP_WALL_HEIGHT + 1,
        align=(Align.CENTER, Align.MAX, Align.MIN),
    )
    for frame in slot_frames():
        strip -= frame * slot
    return strip


def make_sample_finger(thickness: float) -> Part:
    """One sample, printed flat: a plate with a divider-style thick end along its tip.

    Local frame: tip edge on y = 0, finger runs to +Y, bottom face on z = 0. The plate is
    DIVIDER_THICKNESS thick (or ``thickness`` if thinner); the tip bead is END_LENGTH wide.
    """
    bottom = (Align.CENTER, Align.MIN, Align.MIN)
    plate = min(thickness, DIVIDER_THICKNESS)
    finger = Box(FINGER_WIDTH, FINGER_LENGTH + 0.5, plate, align=bottom)
    if thickness > plate:
        finger += Box(FINGER_WIDTH, END_LENGTH, thickness, align=bottom)
    return finger


def sample_label(thickness: float) -> str:
    """Thickness in mm as printed on the comb, e.g. 1.55 -> "1.55"."""
    return f"{thickness:g}"


COMB_TIP_Y = -(FINGER_LENGTH + HANDLE_DEPTH) / 2  # fingertips; centers the comb on Y


def _comb_label_plane(index: int, count: int) -> Plane:
    x = (index - (count - 1) / 2) * FINGER_PITCH
    return Plane(origin=(x, COMB_TIP_Y + FINGER_LENGTH + HANDLE_DEPTH / 2, HANDLE_THICKNESS))


def make_sample_comb(samples: tuple[float, ...] = SLOT_SAMPLES, deboss: float = DEBOSS) -> Part:
    """Fingers of each sample thickness on a labelled handle, centered on the origin.

    Args:
        samples: thickness of each finger's tip, mm.
        deboss: depth of the thickness labels in the handle top.
    """
    count = len(samples)
    width = count * FINGER_PITCH
    comb = Pos(0, COMB_TIP_Y + FINGER_LENGTH, 0) * Box(
        width, HANDLE_DEPTH, HANDLE_THICKNESS, align=(Align.CENTER, Align.MIN, Align.MIN)
    )
    for i, thickness in enumerate(samples):
        plane = _comb_label_plane(i, count)
        comb += Pos(plane.origin.X, COMB_TIP_Y, 0) * make_sample_finger(thickness)
        comb -= _deboss(sample_label(thickness), plane, COMB_FONT, deboss)
    return comb


def _cm3(part: Part) -> float:
    return part.volume / 1000


def _coupon_info(index: int, clearance: float, volume: float) -> PartInfo:
    mark = coupon_label(clearance)
    return PartInfo(
        slug=f"lip-coupon-{mark}",
        title=f"Lip coupon {clearance:.2f} mm",
        blurb=(
            f"Stacking lip cut with {clearance:.2f} mm clearance (marked {mark}). Set the probe "
            "on each coupon: pick the tightest one the probe drops into by its own weight and "
            "that does not rattle when you shake the pair, and use it as LIP_CLEARANCE in "
            f"core.py (now {LIP_CLEARANCE}). If even the loosest binds, fix elephant foot first; "
            "if the tightest rattles, rerun with smaller values (0.15 mm is the floor)."
        ),
        material="The filament you will print the crates in",
        print_notes=(
            f"Upright, no supports, same nozzle, layer height and elephant-foot compensation as "
            f"the real crates; 2 walls, 15% infill. About {volume:.1f} cm³."
        ),
        color=COUPON_COLORS[index % len(COUPON_COLORS)],
        footprint=f"{COUPON.nx}x{COUPON.ny}x{COUPON.h}",
    )


def build(
    clearances: tuple[float, ...] = CLEARANCES, samples: tuple[float, ...] = SLOT_SAMPLES
) -> None:
    """Verify, then export the coupons, probe, slot strip and sample comb into models/calibration/.

    Args:
        clearances: lip clearances to print one coupon each for, mm.
        samples: divider-end thicknesses to put on the sample comb, mm.
    """
    check_clearances(clearances)
    if not verify(clearances, samples):
        raise SystemExit("calibration verification failed, nothing exported")
    parts: list[tuple[Part, PartInfo]] = []
    for i, c in enumerate(clearances):
        coupon = make_coupon(c)
        parts.append((coupon, _coupon_info(i, c, _cm3(coupon))))
    probe, strip, comb = make_probe(), make_slot_strip(), make_sample_comb(samples)
    parts += [
        (probe, _probe_info(_cm3(probe))),
        (strip, _strip_info(_cm3(strip))),
        (comb, _comb_info(samples, _cm3(comb))),
    ]
    for part, info in parts:
        save(MODULE, part, info)
        size = part.bounding_box().size
        print(
            f"  exported {info.slug:16s} {size.X:5.1f} x {size.Y:5.1f} x {size.Z:5.1f} mm  "
            f"{_cm3(part):5.2f} cm³"
        )


def _probe_info(volume: float) -> PartInfo:
    return PartInfo(
        slug="lip-probe",
        title="Lip probe 1x1x2",
        blurb=(
            "A plain default 1x1x2 crate whose feet are the gauge for the lip coupons. Lower it "
            "onto each coupon by hand, then let go: it should drop the last few mm on its own "
            "and come to rest flat, with a 0.75 mm shadow gap all round."
        ),
        material="The filament you will print the crates in",
        print_notes=(
            "Upright, no supports, exactly the settings of your real crates (the feet are what "
            f"is tested), 2 walls, 15% infill. About {volume:.1f} cm³; keeps working as a crate."
        ),
        color="#8a8f98",
        footprint=f"{COUPON.nx}x{COUPON.ny}x{COUPON.h}",
    )


def _strip_info(volume: float) -> PartInfo:
    return PartInfo(
        slug="slot-strip",
        title="Divider slot strip",
        blurb=(
            f"Two {DIVIDER_SLOT_WIDTH} x {DIVIDER_SLOT_DEPTH} mm divider slots exactly as in "
            "every crate, one in an X wall and one in a Y wall (printers often differ between "
            "axes). Use it with the slot sample comb."
        ),
        material="The filament you will print the crates in",
        print_notes=(
            f"Floor on the bed, no supports, same settings as the crates. About {volume:.1f} cm³."
        ),
        color="#4f8fbf",
    )


def _comb_info(samples: tuple[float, ...], volume: float) -> PartInfo:
    listed = " / ".join(sample_label(t) for t in samples)
    return PartInfo(
        slug="slot-samples",
        title="Divider end samples",
        blurb=(
            f"Divider ends {listed} mm thick. Press each finger's tip edge into both slots of "
            f"the strip: the {DIVIDER_THICKNESS} mm plate must slide freely (if not, your slots "
            "print narrow). Pick the thickest end that goes in by hand in both slots and stays "
            "put when you turn the strip upside down; set END_THICKNESS in "
            f"stakee/modules/dividers.py to it (now {END_THICKNESS})."
        ),
        material="The filament you will print the dividers in",
        print_notes=(
            "Flat, labels up, no supports, 100% infill, same layer height as the dividers: at "
            "0.2 mm layers the slicer rounds 1.5 and 1.55 to whole layers, use 0.1 mm or less "
            f"to see the difference. About {volume:.1f} cm³."
        ),
        color="#c47ed6",
    )


# ------------------------------------------------------------------------------ verification


def _overlap(a: Part, b: Part) -> float:
    common = a & b
    return common.volume if common else 0.0


def measure_lip_play(coupon: Part, probe: Part, clearance: float) -> float:
    """Smallest horizontal gap between the seated probe's vertical foot faces and the lip.

    Probes a thin line through each side wall at mid-height of the overlap of the foot's and
    the pocket's vertical faces; the probe must already sit at z = 7 * h.
    """
    seat = COUPON.lip_top - SEAT_DEPTH
    vertical_bottom, vertical_top = FOOT_STATIONS[1][0], FOOT_STATIONS[2][0]
    z = seat + (vertical_bottom + clearance + vertical_top) / 2
    line = Pos(COUPON.width / 2, 0, z) * Box(COUPON.width, 0.02, 0.02)
    gaps = []
    for k in range(4):
        turn = Rot(0, 0, -90 * k)
        wall = (turn * coupon) & line
        foot = (turn * probe) & line
        gaps.append(wall.bounding_box().min.X - foot.bounding_box().max.X)
    return min(gaps)


def measure_backing(part: Part, label: str, plane: Plane, font: float, depth: float) -> float:
    """Material thickness behind a debossed label: deepest fully solid text-shaped layer."""
    lo, hi = 0.0, 3.0
    for _ in range(12):
        mid = (lo + hi) / 2
        prism = _text_prism(label, plane, font, -depth - 0.001, -depth - mid)
        if _overlap(part, prism) >= prism.volume * (1 - 1e-4):
            lo = mid
        else:
            hi = mid
    return lo


def _place_sample(thickness: float, frame: Location, shift: float = 0.0) -> Part:
    """A finger with its tip INSERT deep in the slot at ``frame``, centered, moved ``shift``."""
    turned = Rot(0, 90, 0) * make_sample_finger(thickness)
    z = PROBE_Z + FINGER_WIDTH / 2
    return frame * Pos(-thickness / 2 + shift, -INSERT, z) * turned


def measure_slot_play(strip: Part, thickness: float, frame: Location) -> float:
    """Sideways travel of a centered sample before it touches the slot wall, mm per side."""
    if _overlap(strip, _place_sample(thickness, frame)) > EPS:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(12):
        mid = (lo + hi) / 2
        if _overlap(strip, _place_sample(thickness, frame, mid)) > EPS:
            hi = mid
        else:
            lo = mid
    return lo


class _Report:
    def __init__(self) -> None:
        self.ok = True

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        self.ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name} {detail}")
        return passed

    def control(self, name: str, passed: bool, detail: str = "") -> None:
        """A deliberately wrong value: the underlying check must fail."""
        self.ok &= not passed
        print(f"  [{'CAUGHT' if not passed else 'MISSED'}] {name} {detail}")


def _verify_coupon(report: _Report, clearance: float, probe: Part) -> None:
    mark = coupon_label(clearance)
    coupon = make_coupon(clearance)
    report.check(f"coupon {mark} valid", coupon.is_valid)
    pitch = COUPON.h * HEIGHT_UNIT
    seated = Pos(0, 0, pitch) * probe
    v_seated = _overlap(coupon, seated)
    v_low = _overlap(coupon, Pos(0, 0, pitch - 0.05) * probe)
    report.check(f"coupon {mark} probe @ z={pitch:.0f} clear", v_seated < EPS, f"{v_seated:.6f}")
    report.check(f"coupon {mark} probe 0.05 lower collides", v_low > EPS, f"{v_low:.4f} mm³")
    play = measure_lip_play(coupon, seated, clearance)
    report.check(
        f"coupon {mark} play on vertical foot faces",
        abs(play - clearance) < 1e-3,
        f"{play:.4f} mm (clearance {clearance})",
    )
    backing = measure_backing(coupon, mark, coupon_text_plane(), COUPON_FONT, DEBOSS)
    report.check(f"coupon {mark} wall behind label", backing >= MIN_BACKING, f"{backing:.3f} mm")


def _verify_slots(report: _Report, samples: tuple[float, ...]) -> None:
    strip = make_slot_strip()
    report.check("slot strip valid", strip.is_valid)
    colliding = []
    for t in samples:
        for axis, frame in zip(("X wall", "Y wall"), slot_frames(), strict=True):
            centered = _overlap(strip, _place_sample(t, frame))
            if centered > EPS:
                colliding.append(f"{sample_label(t)} ({axis})")
            play = measure_slot_play(strip, t, frame)
            expected = max((DIVIDER_SLOT_WIDTH - t) / 2, 0.0)
            report.check(
                f"sample {sample_label(t):4s} in {axis} slot",
                abs(play - expected) < 1e-3,
                f"play {play:.3f}/side (expected {expected:.3f}), centered overlap {centered:.4f}",
            )
    print(f"  samples colliding with the slot nominally: {', '.join(colliding) or 'none'}")
    comb = make_sample_comb(samples)
    report.check("sample comb valid", comb.is_valid)
    for i, t in enumerate(samples):
        plane = _comb_label_plane(i, len(samples))
        backing = measure_backing(comb, sample_label(t), plane, COMB_FONT, DEBOSS)
        report.check(
            f"comb label {sample_label(t)} backing", backing >= MIN_BACKING, f"{backing:.3f} mm"
        )


def _verify_controls(report: _Report) -> None:
    """Deliberately wrong values that the checks above must reject."""
    deep = 1.4
    bad = make_coupon(LIP_CLEARANCE, deboss=deep)
    backing = measure_backing(
        bad, coupon_label(LIP_CLEARANCE), coupon_text_plane(), COUPON_FONT, deep
    )
    report.control(
        f"coupon label debossed {deep} mm", backing >= MIN_BACKING, f"backing {backing:.3f} mm"
    )
    fat = DIVIDER_SLOT_WIDTH + 0.05
    clash = _overlap(make_slot_strip(), _place_sample(fat, slot_frames()[0]))
    report.control(f"{fat:.2f} mm sample fits the slot", clash < EPS, f"overlap {clash:.4f} mm³")
    probe = make_probe()
    coupon = make_coupon(LIP_CLEARANCE)
    play = measure_lip_play(coupon, Pos(0, 0, COUPON.h * HEIGHT_UNIT) * probe, LIP_CLEARANCE)
    report.control("coupon 25 measured as 0.35", abs(play - 0.35) < 1e-3, f"play {play:.4f} mm")


def verify(
    clearances: tuple[float, ...] = CLEARANCES, samples: tuple[float, ...] = SLOT_SAMPLES
) -> bool:
    """Seat the probe on every coupon, measure lip and slot play, check labels; print results.

    Args:
        clearances: lip clearances to check.
        samples: divider-end thicknesses to check against the core slot.
    """
    check_clearances(clearances)
    report = _Report()
    probe = make_probe()
    report.check("probe valid", probe.is_valid)
    for c in clearances:
        _verify_coupon(report, c, probe)
    _verify_slots(report, samples)
    _verify_controls(report)
    print("ALL CHECKS PASSED" if report.ok else "SOME CHECKS FAILED")
    return report.ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clearances", type=float, nargs="+", default=list(CLEARANCES))
    parser.add_argument("--samples", type=float, nargs="+", default=list(SLOT_SAMPLES))
    args = parser.parse_args()
    build(tuple(args.clearances), tuple(args.samples))


if __name__ == "__main__":
    main()
