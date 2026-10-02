"""Write a part as STL (print), STEP (remix in CAD) and SVG line art (preview) + manifest entry.

Layout of one model family::

    models/<module>/
        manifest.json          every part's metadata, keyed by slug
        stl/<slug>.stl
        step/<slug>.step
        preview/<slug>.svg
"""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from build123d import Part, export_step, export_stl

from stakee.preview import write_figure

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

STL_TOLERANCE = 0.02
STL_ANGULAR_TOLERANCE = 0.15

# OpenCascade stamps every STEP file with the export time and a per-process counter, so an
# unchanged part would show up as a diff after every rebuild. Both are pinned on export.
STEP_VOLATILE = (
    (re.compile(r"(FILE_NAME\('[^']*',)'[^']*'"), r"\1'1970-01-01T00:00:00'"),
    (re.compile(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\('\d+'"), "NEXT_ASSEMBLY_USAGE_OCCURRENCE('1'"),
)


@dataclass
class PartInfo:
    """Metadata shown in the catalogue next to a part.

    Attributes:
        slug: file stem, unique within its module.
        title: short human name.
        blurb: one or two sentences: what it is and why a hacker wants it.
        material: recommended filament, e.g. "PETG" or "PLA + TPU".
        print_notes: orientation, supports, infill, inserts (magnets, NFC...).
        color: preview hex color.
        footprint: e.g. "2x2x6" (grid units) or "" for non-box parts.
        assembly: where the part sits in its crate, (x, y, z) in mm, if it is an insert.
        size_mm: bounding box (X, Y, Z) in mm, filled in on export.
        files: repo-relative paths of the exported files, filled in on export.
    """

    slug: str
    title: str
    blurb: str
    material: str
    print_notes: str
    color: str = "#d9d4c7"
    footprint: str = ""
    assembly: tuple[float, float, float] | None = None
    size_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    files: dict[str, str] = field(default_factory=dict)


def write_step(part: Part, path: Path) -> None:
    """STEP export with the volatile header fields pinned (see ``STEP_VOLATILE``)."""
    export_step(part, str(path))
    text = path.read_text()
    for pattern, replacement in STEP_VOLATILE:
        text = pattern.sub(replacement, text, count=1)
    path.write_text(text)


def manifest_path(module: str) -> Path:
    return MODELS / module / "manifest.json"


def read_manifest(module: str) -> dict[str, dict]:
    """Parts of one family as written by ``save``, keyed by slug ({} if never built)."""
    path = manifest_path(module)
    return json.loads(path.read_text()) if path.exists() else {}


def save(module: str, part: Part, info: PartInfo) -> PartInfo:
    """Export one part into models/<module>/ and record it in its manifest.json."""
    if not part.is_valid:
        raise ValueError(f"{module}/{info.slug}: solid is not valid, refusing to export")
    folder = MODELS / module
    files = {
        "stl": folder / "stl" / f"{info.slug}.stl",
        "step": folder / "step" / f"{info.slug}.step",
        "svg": folder / "preview" / f"{info.slug}.svg",
    }
    for path in files.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    export_stl(
        part,
        str(files["stl"]),
        tolerance=STL_TOLERANCE,
        angular_tolerance=STL_ANGULAR_TOLERANCE,
    )
    write_step(part, files["step"])
    write_figure(files["svg"], [part])

    size = part.bounding_box().size
    info.size_mm = (round(size.X, 1), round(size.Y, 1), round(size.Z, 1))
    info.files = {
        kind: (Path("models") / path.relative_to(MODELS)).as_posix() for kind, path in files.items()
    }
    manifest = read_manifest(module)
    manifest[info.slug] = asdict(info)
    manifest_path(module).write_text(json.dumps(manifest, indent=2) + "\n")
    return info
