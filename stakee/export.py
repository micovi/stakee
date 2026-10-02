"""Write a part as STL (print), STEP (remix in CAD) and SVG line art (preview) + manifest entry.

Layout of one model family::

    models/<module>/
        manifest.json          every part's metadata, keyed by slug
        stl/<slug>.stl
        step/<slug>.step
        preview/<slug>.svg

``ROOT`` is the repository checkout this package lives in: the library is built from a clone
(``uv sync`` installs it editable), not from an installed wheel.
"""

import itertools
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
# OpenCascade stamps STEP files with the export time and numbers assembly links with a
# per-process counter; both are pinned so an unchanged part exports byte for byte the same.
STEP_TIMESTAMP = "1970-01-01T00:00:00"
STEP_LINK_ID = re.compile(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\('\d+'")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


@dataclass
class PartInfo:
    """Metadata shown in the catalogue next to a part.

    Attributes:
        slug: file stem, unique within its module: lowercase letters, digits, '.', '-'.
        title: short human name.
        blurb: one or two sentences: what it is and why a hacker wants it.
        material: recommended filament, e.g. "PETG" or "PLA + TPU".
        print_notes: orientation, supports, infill, inserts (magnets, NFC...).
        color: suggested filament colour (hex), the default in the site's 3D viewer.
        footprint: e.g. "2x2x6" (grid units) or "" for non-box parts.
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
    size_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    files: dict[str, str] = field(default_factory=dict)


def stable_step(text: str) -> str:
    """Renumber assembly links 1, 2, 3... in file order (OCC numbers them per process)."""
    counter = itertools.count(1)
    return STEP_LINK_ID.sub(lambda _: f"NEXT_ASSEMBLY_USAGE_OCCURRENCE('{next(counter)}'", text)


def write_stl(part: Part, path: Path) -> None:
    """Binary STL at the library's mesh tolerance; raises if the writer reports failure."""
    if not export_stl(
        part, str(path), tolerance=STL_TOLERANCE, angular_tolerance=STL_ANGULAR_TOLERANCE
    ):
        raise OSError(f"STL export to {path} failed")


def write_step(part: Part, path: Path) -> None:
    """STEP export that is byte-stable across runs; raises if the writer reports failure."""
    if not export_step(part, str(path), timestamp=STEP_TIMESTAMP):
        raise OSError(f"STEP export to {path} failed")
    path.write_text(stable_step(path.read_text()))


def manifest_path(module: str) -> Path:
    """``models/<module>/manifest.json``."""
    return MODELS / module / "manifest.json"


def read_manifest(module: str) -> dict[str, dict]:
    """Parts of one family as written by ``save``, keyed by slug ({} if never built)."""
    path = manifest_path(module)
    return json.loads(path.read_text()) if path.exists() else {}


def save(module: str, part: Part, info: PartInfo) -> PartInfo:
    """Export one part into models/<module>/ and record it in its manifest.json.

    Raises:
        ValueError: the slug is not a safe file stem or the solid is invalid.
        OSError: a file could not be written.
    """
    if not SLUG_RE.match(info.slug):
        raise ValueError(f"{module}/{info.slug!r}: slug must match {SLUG_RE.pattern}")
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
    write_stl(part, files["stl"])
    write_step(part, files["step"])
    write_figure(files["svg"], part)

    size = part.bounding_box().size
    info.size_mm = (round(size.X, 1), round(size.Y, 1), round(size.Z, 1))
    info.files = {
        kind: (Path("models") / path.relative_to(MODELS)).as_posix() for kind, path in files.items()
    }
    manifest = read_manifest(module)
    manifest[info.slug] = asdict(info)
    manifest_path(module).write_text(json.dumps(manifest, indent=2) + "\n")
    return info
