"""Command-line generator: print-ready Stakee crates, caps, dividers and label tiles.

Usage::

    stakee box 3x2x6 --dividers 2x3 --label ESP32
    stakee cap 2x2 --label TOOLS
    stakee list

Every part is written as STL (slicer) and STEP (CAD) into ``--out`` (default
``./out/<name>/``) with deterministic file names. ``--json`` prints a machine-readable
summary instead of the human one. Bad input exits with status 2 and a one-line reason.
"""

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from build123d import Align, Box, FontStyle, Part, Pos, Text, extrude

from stakee.core import (
    DIVIDER_THICKNESS,
    GRID,
    HEIGHT_UNIT,
    LABEL_DEPTH,
    LABEL_HEIGHT,
    LABEL_MIN_HEIGHT_UNITS,
    LIP_CLEARANCE,
    LIP_CLEARANCE_MAX,
    LIP_CLEARANCE_MIN,
    BoxSize,
    divider_slot_positions,
    label_width,
    make_box,
    make_cap,
)
from stakee.export import write_step, write_stl
from stakee.modules.dividers import make_rail, plate_height

MAX_UNITS = 8  # 336 mm: already beyond most print beds
MAX_HEIGHT = 40  # 280 mm
MIN_HEIGHT = 2

TILE_CLEARANCE = 0.1  # per side, against the label recess
TILE_TEXT_HEIGHT = 0.4  # embossed above the tile, two 0.2 mm layers for a filament swap
TILE_TEXT_MARGIN = 1.0
FONT_SIZE = 7.0
MIN_FONT_SIZE = 3.5  # below this, 0.4 mm nozzles smear the strokes

CAP_NOTES = "Plate on the bed (upside down), no supports."

SIZE_RE = re.compile(r"^(\d+)x(\d+)x(\d+)$")
FOOTPRINT_RE = re.compile(r"^(\d+)x(\d+)$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class CliError(Exception):
    """Bad user input; the message is printed as-is and the CLI exits with status 2."""


@dataclass
class OutPart:
    """One distinct part to export and how many copies to print."""

    slug: str
    title: str
    part: Part
    count: int
    print_notes: str


# --- Parsing -----------------------------------------------------------------------------


def _check_footprint(text: str, nx: int, ny: int) -> None:
    if nx < 1 or ny < 1:
        raise CliError(f"{text}: footprint must be >= 1 unit per side")
    if nx > MAX_UNITS or ny > MAX_UNITS:
        raise CliError(f"{text}: footprint must be <= {MAX_UNITS} units per side")


def parse_box_size(text: str) -> BoxSize:
    """Parse ``NXxNYxH`` (grid units, 7 mm height units) into a validated BoxSize."""
    match = SIZE_RE.match(text.strip().lower())
    if not match:
        raise CliError(f"{text}: expected NXxNYxH, e.g. 3x2x6 (42 mm units, 7 mm height units)")
    nx, ny, h = (int(group) for group in match.groups())
    _check_footprint(text, nx, ny)
    if h < MIN_HEIGHT:
        raise CliError(f"{text}: height must be >= {MIN_HEIGHT} units (use `stakee cap` for lids)")
    if h > MAX_HEIGHT:
        raise CliError(f"{text}: height must be <= {MAX_HEIGHT} units")
    return BoxSize(nx, ny, h)


def parse_footprint(text: str) -> tuple[int, int]:
    """Parse ``NXxNY`` (grid units) into a validated footprint."""
    match = FOOTPRINT_RE.match(text.strip().lower())
    if not match:
        raise CliError(f"{text}: expected NXxNY, e.g. 2x2 (42 mm units)")
    nx, ny = int(match.group(1)), int(match.group(2))
    _check_footprint(text, nx, ny)
    return nx, ny


def parse_compartments(text: str, size: BoxSize) -> tuple[int, int]:
    """Parse ``--dividers AxB`` and check the crate has enough slots for it."""
    match = FOOTPRINT_RE.match(text.strip().lower())
    if not match:
        raise CliError(f"--dividers {text}: expected AxB, e.g. 2x3 (A across X, B along Y)")
    across, along = int(match.group(1)), int(match.group(2))
    if across < 1 or along < 1:
        raise CliError(f"--dividers {text}: compartment counts must be >= 1")
    for count, units, axis in ((across, size.nx, "X"), (along, size.ny, "Y")):
        if count > 2 * units:
            raise CliError(
                f"--dividers {text}: a {units}-unit side has {2 * units - 1} divider slot(s) "
                f"along {axis} (every 21 mm), so at most {2 * units} compartments; got {count}"
            )
    return across, along


def parse_lip_clearance(value: float) -> float:
    if not LIP_CLEARANCE_MIN <= value < LIP_CLEARANCE_MAX:
        raise CliError(
            f"--lip-clearance {value}: must be >= {LIP_CLEARANCE_MIN} and < {LIP_CLEARANCE_MAX} mm"
        )
    return value


def check_name(name: str) -> str:
    if not NAME_RE.match(name):
        raise CliError(f"--name {name!r}: use letters, digits, '.', '_' or '-' only")
    return name


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "label"


# --- Dividers ----------------------------------------------------------------------------


def _nearest_slot(ideal: Fraction, units: int) -> int:
    """Round a fractional slot index to the nearest slot, ties away from the center."""
    if ideal >= units:
        return math.floor(ideal + Fraction(1, 2))
    return math.ceil(ideal - Fraction(1, 2))


def rail_positions(units: int, compartments: int) -> list[float]:
    """Slot centers (mm) for ``compartments - 1`` rails spread as evenly as the slots allow."""
    slots = divider_slot_positions(units)
    indices = [
        _nearest_slot(Fraction(i * 2 * units, compartments), units) for i in range(1, compartments)
    ]
    return [slots[k - 1] for k in indices]


def compartment_sizes(span: float, rails: list[float]) -> list[float]:
    """Clear width of each compartment between the cavity walls and the rail faces (approx)."""
    edges = [-span / 2, *rails, span / 2]
    sizes = []
    for i in range(len(edges) - 1):
        clear = edges[i + 1] - edges[i]
        clear -= DIVIDER_THICKNESS / 2 * ((i > 0) + (i < len(edges) - 2))
        sizes.append(round(clear, 1))
    return sizes


def divider_parts(size: BoxSize, across: int, along: int) -> list[OutPart]:
    """Rails for an ``across`` x ``along`` grid: across-1 Y rails, along-1 X rails."""
    tag = f"{size.nx}x{size.ny}x{size.h}"
    notes = "Flat on the bed, no supports, 100% infill; slide the ends into the wall slots."
    parts = []
    if along > 1:
        parts.append(
            OutPart(f"rail-x-{tag}", f"X rail {tag}", make_rail(size, True), along - 1, notes)
        )
    if across > 1:
        parts.append(
            OutPart(f"rail-y-{tag}", f"Y rail {tag}", make_rail(size, False), across - 1, notes)
        )
    return parts


def divider_summary(size: BoxSize, across: int, along: int) -> dict:
    cav_w, cav_d, _ = size.cavity
    y_rails_x = rail_positions(size.nx, across)
    x_rails_y = rail_positions(size.ny, along)
    return {
        "across_x": across,
        "along_y": along,
        "y_rails_at_x_mm": y_rails_x,
        "x_rails_at_y_mm": x_rails_y,
        "widths_mm": compartment_sizes(cav_w, y_rails_x),
        "depths_mm": compartment_sizes(cav_d, x_rails_y),
        "rail_height_mm": round(plate_height(size), 2),
    }


# --- Label tile --------------------------------------------------------------------------


def _centered_text(text: str, font_size: float):
    sketch = Text(text, font_size=font_size, font_style=FontStyle.BOLD)
    center = sketch.bounding_box().center()
    return Pos(-center.X, -center.Y) * sketch


def fit_text(text: str, avail_w: float, avail_h: float):
    """Largest font (<= FONT_SIZE) whose text fits ``avail_w`` x ``avail_h``, and its sketch."""
    font_size = FONT_SIZE
    sketch = _centered_text(text, font_size)
    bbox = sketch.bounding_box().size
    scale = min(1.0, avail_w / bbox.X, avail_h / bbox.Y)
    if scale < 1.0:
        font_size = math.floor(FONT_SIZE * scale * 10) / 10
        sketch = _centered_text(text, font_size)
    if font_size < MIN_FONT_SIZE:
        raise CliError(
            f"--label {text!r}: needs a {font_size:.1f} mm font to fit the {avail_w:.1f} mm "
            f"label area; minimum is {MIN_FONT_SIZE} mm. Shorten the text or use a wider box."
        )
    return sketch, font_size


def make_front_label_tile(text: str, width: float) -> tuple[Part, dict]:
    """Press-fit tile for the core label recess of a ``width`` mm part, text embossed on top."""
    if not text.strip():
        raise CliError("--label: text must not be empty")
    tile_w = label_width(width) - 2 * TILE_CLEARANCE
    tile_h = LABEL_HEIGHT - 2 * TILE_CLEARANCE
    sketch, font_size = fit_text(
        text.strip(), tile_w - 2 * TILE_TEXT_MARGIN, tile_h - 2 * TILE_TEXT_MARGIN
    )
    tile = Box(tile_w, tile_h, LABEL_DEPTH, align=(Align.CENTER, Align.CENTER, Align.MIN))
    tile += Pos(0, 0, LABEL_DEPTH - 0.01) * extrude(sketch, amount=TILE_TEXT_HEIGHT + 0.01)
    info = {
        "text": text.strip(),
        "font_size_mm": font_size,
        "tile_mm": [round(tile_w, 2), round(tile_h, 2), LABEL_DEPTH],
        "text_height_mm": TILE_TEXT_HEIGHT,
        "filament_swap_at_z_mm": LABEL_DEPTH,
    }
    return tile, info


def label_part(text: str, width: float, count: int) -> tuple[OutPart, dict]:
    tile, info = make_front_label_tile(text, width)
    notes = (
        f"Flat, text up; swap filament at z = {LABEL_DEPTH} mm. Press into the label recess "
        "(0.1 mm clearance per side), a dab of glue if loose."
    )
    slug = f"label-{slugify(text)}"
    return OutPart(slug, f"Label tile '{text.strip()}'", tile, count, notes), info


# --- Export ------------------------------------------------------------------------------


def write_part(out_dir: Path, item: OutPart) -> dict:
    """Export one part as STL + STEP; returns its summary entry."""
    if not item.part.is_valid:
        raise RuntimeError(f"{item.slug}: generated solid is not valid; please report this")
    stem = out_dir / item.slug
    write_stl(item.part, stem.with_suffix(".stl"))
    write_step(item.part, stem.with_suffix(".step"))
    bbox = item.part.bounding_box().size
    return {
        "slug": item.slug,
        "title": item.title,
        "count": item.count,
        "size_mm": [round(bbox.X, 2), round(bbox.Y, 2), round(bbox.Z, 2)],
        "print_notes": item.print_notes,
        "stl": str(stem.with_suffix(".stl")),
        "step": str(stem.with_suffix(".step")),
    }


def write_parts(out_dir: Path, items: list[OutPart]) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return [write_part(out_dir, item) for item in items]


def resolve_out(args: argparse.Namespace, default_name: str) -> tuple[str, Path]:
    name = check_name(args.name) if args.name else default_name
    out_dir = Path(args.out).expanduser().resolve() if args.out else Path.cwd() / "out" / name
    return name, out_dir


# --- Commands ----------------------------------------------------------------------------


def _box_default_name(size: BoxSize, args: argparse.Namespace) -> str:
    name = f"box-{size.nx}x{size.ny}x{size.h}"
    if args.dividers:
        name += f"-d{args.dividers.strip().lower()}"
    if args.label:
        name += f"-{slugify(args.label)}"
    return name


def _box_extras(size: BoxSize, args: argparse.Namespace, summary: dict) -> list[OutPart]:
    """Cap, dividers and label tile requested next to the crate."""
    items = []
    if args.cap:
        tag = f"{size.nx}x{size.ny}"
        items.append(OutPart(f"cap-{tag}", f"Cap {tag}", make_cap(size.nx, size.ny), 1, CAP_NOTES))
    if args.dividers:
        across, along = parse_compartments(args.dividers, size)
        summary["compartments"] = divider_summary(size, across, along)
        items.extend(divider_parts(size, across, along))
    if args.label:
        if size.h < LABEL_MIN_HEIGHT_UNITS:
            raise CliError(
                f"--label: a {size.h}-unit box has no front label recess; "
                f"use height >= {LABEL_MIN_HEIGHT_UNITS}"
            )
        tile, summary["label"] = label_part(args.label, size.width, 2 if args.cap else 1)
        items.append(tile)
    return items


def cmd_box(args: argparse.Namespace) -> dict:
    size = parse_box_size(args.size)
    clearance = parse_lip_clearance(args.lip_clearance)
    tag = f"{size.nx}x{size.ny}x{size.h}"
    cav_w, cav_d, cav_h = size.cavity
    summary: dict = {
        "command": "box",
        "size": tag,
        "outer_mm": [size.width, size.depth, size.lip_top],
        "stack_pitch_mm": size.h * HEIGHT_UNIT,
        "cavity_mm": [round(cav_w, 2), round(cav_d, 2), round(cav_h, 2)],
    }
    name, out_dir = resolve_out(args, _box_default_name(size, args))
    extras = _box_extras(size, args, summary)
    crate = make_box(
        size,
        magnets=not args.no_magnets,
        clip_sockets=not args.no_sockets,
        lip_clearance=clearance,
    )
    notes = "Upright on its feet, no supports, 0.2 mm layers."
    if not args.no_magnets:
        notes += " Glue 6x2 mm magnets into the pockets under the feet."
    items = [OutPart(f"box-{tag}", f"Box {tag}", crate, 1, notes), *extras]
    summary |= {"name": name, "out_dir": str(out_dir), "parts": write_parts(out_dir, items)}
    return summary


def cmd_cap(args: argparse.Namespace) -> dict:
    nx, ny = parse_footprint(args.size)
    tag = f"{nx}x{ny}"
    width = BoxSize(nx, ny, MIN_HEIGHT).width
    items = [OutPart(f"cap-{tag}", f"Cap {tag}", make_cap(nx, ny), 1, CAP_NOTES)]
    summary: dict = {"command": "cap", "size": tag}
    if args.label:
        tile, summary["label"] = label_part(args.label, width, 1)
        items.append(tile)
    default_name = f"cap-{tag}" + (f"-{slugify(args.label)}" if args.label else "")
    name, out_dir = resolve_out(args, default_name)
    summary |= {"name": name, "out_dir": str(out_dir), "parts": write_parts(out_dir, items)}
    return summary


def cmd_list(_args: argparse.Namespace) -> dict:
    return {
        "command": "list",
        "grid_mm": GRID,
        "height_unit_mm": HEIGHT_UNIT,
        "footprint_units": [1, MAX_UNITS],
        "height_units": [MIN_HEIGHT, MAX_HEIGHT],
        "examples": {
            f"{nx}x{ny}x{h}": BoxSize(nx, ny, h).cavity
            for nx, ny, h in ((1, 1, 3), (2, 1, 3), (2, 2, 3), (2, 2, 6), (3, 2, 6), (4, 2, 6))
        },
        "options": OPTION_HELP,
        "dividers_max": "AxB with A <= 2*NX and B <= 2*NY (slots every 21 mm)",
        "label_min_box_height": LABEL_MIN_HEIGHT_UNITS,
    }


OPTION_HELP = {
    "--dividers AxB": "A compartments across X, B along Y: exports X/Y rails, prints counts",
    "--label TEXT": "press-fit tile for the front label recess, text embossed 0.4 mm",
    "--cap": "also export a lid for the same footprint",
    "--no-magnets": "omit the 6.5x2.4 mm magnet pockets under the feet",
    "--no-sockets": "omit the stack-clip sockets on the side walls",
    "--lip-clearance MM": f"foot/lip play, default {LIP_CLEARANCE} (tune for your printer)",
    "--name NAME": "output folder name and summary name (default derived from the options)",
    "--out DIR": "output folder (default ./out/<name>/)",
    "--json": "print a machine-readable summary on stdout",
}


# --- Output ------------------------------------------------------------------------------


def render_list(summary: dict) -> str:
    lines = [
        f"Sizes: NXxNYxH, NX/NY 1..{MAX_UNITS} x {GRID:.0f} mm, "
        f"H {MIN_HEIGHT}..{MAX_HEIGHT} x {HEIGHT_UNIT:.0f} mm (stack pitch).",
        "Cavity (W x D x H mm) for common sizes:",
    ]
    for tag, (w, d, h) in summary["examples"].items():
        lines.append(f"  {tag:<7} {w:6.1f} x {d:6.1f} x {h:5.1f}")
    lines.append("Commands: stakee box NXxNYxH [opts] | stakee cap NXxNY [--label T] | stakee list")
    lines.append("Options:")
    lines.extend(f"  {flag:<20} {text}" for flag, text in OPTION_HELP.items())
    lines.append(f"Dividers: {summary['dividers_max']}.")
    lines.append(f"Labels need box height >= {LABEL_MIN_HEIGHT_UNITS}.")
    return "\n".join(lines)


def render_parts(summary: dict) -> str:
    lines = [f"stakee {summary['command']} {summary['size']} -> {summary['out_dir']}"]
    if "cavity_mm" in summary:
        w, d, h = summary["cavity_mm"]
        lines.append(f"Cavity: {w} x {d} x {h} mm")
    if "compartments" in summary:
        comp = summary["compartments"]
        lines.append(
            f"Compartments: {comp['across_x']} x {comp['along_y']}, widths {comp['widths_mm']} "
            f"mm, depths {comp['depths_mm']} mm"
        )
    if "label" in summary:
        lines.append(f"Label: font {summary['label']['font_size_mm']} mm")
    lines.append("Print:")
    lines.extend(f"  {p['count']}x {p['slug']}  ({p['print_notes']})" for p in summary["parts"])
    lines.append("Files:")
    for part in summary["parts"]:
        lines.extend((f"  {part['stl']}", f"  {part['step']}"))
    return "\n".join(lines)


# --- Entry point -------------------------------------------------------------------------


def _common(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--name", help="output folder name (default derived from the options)")
    sub.add_argument("--out", help="output folder (default ./out/<name>/)")
    sub.add_argument("--json", action="store_true", help="machine-readable summary on stdout")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stakee", description=__doc__.split("\n")[0])
    subs = parser.add_subparsers(dest="command", required=True)
    box = subs.add_parser("box", help="crate (+ dividers, label tile, cap)")
    box.add_argument("size", help="NXxNYxH, e.g. 3x2x6")
    box.add_argument("--dividers", metavar="AxB", help="A compartments across X, B along Y")
    box.add_argument("--label", metavar="TEXT", help="press-fit label tile for the front recess")
    box.add_argument("--no-magnets", action="store_true", help="no magnet pockets")
    box.add_argument("--no-sockets", action="store_true", help="no stack-clip sockets")
    box.add_argument("--cap", action="store_true", help="also export a matching cap")
    box.add_argument("--lip-clearance", type=float, default=LIP_CLEARANCE, metavar="MM")
    _common(box)
    box.set_defaults(handler=cmd_box)
    cap = subs.add_parser("cap", help="lid for an NXxNY footprint")
    cap.add_argument("size", help="NXxNY, e.g. 2x2")
    cap.add_argument("--label", metavar="TEXT", help="press-fit label tile for the top recess")
    _common(cap)
    cap.set_defaults(handler=cmd_cap)
    lst = subs.add_parser("list", help="sizes and options")
    lst.add_argument("--json", action="store_true", help="machine-readable output")
    lst.set_defaults(handler=cmd_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; returns the process exit status."""
    args = build_parser().parse_args(argv)
    try:
        summary = args.handler(args)
    except CliError as err:
        print(f"stakee {args.command}: error: {err}", file=sys.stderr)
        if args.json:
            print(json.dumps({"ok": False, "error": str(err)}))
        return 2
    if args.json:
        print(json.dumps({"ok": True, **summary}, indent=2))
    elif args.command == "list":
        print(render_list(summary))
    else:
        print(render_parts(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
