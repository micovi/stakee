"""Line-art previews: hidden-line projections of the real geometry as small SVG files.

Each preview is drawn from the same solid the STL comes from, so a picture can never
disagree with the part. The SVG carries a white background so it reads the same on
GitHub's light and dark themes and on the docs site.
"""

import re
import tempfile
from pathlib import Path

from build123d import Compound, ExportSVG, Part, Unit

# Front-right-top, the view assembly instructions use. Z is up, the front face is -Y.
ISO_DIRECTION = (1.0, -1.35, 1.05)
STROKE = "#141414"
STYLE = "path,line{stroke-width:1.15px;vector-effect:non-scaling-stroke}"


def _visible_edges(shapes: list[Part], direction: tuple[float, float, float]):
    compound = Compound(shapes)
    box = compound.bounding_box()
    c = box.center()
    center = (c.X, c.Y, c.Z)
    norm = sum(d * d for d in direction) ** 0.5
    reach = box.diagonal * 4
    origin = tuple(center[i] + direction[i] / norm * reach for i in range(3))
    visible, _hidden = compound.project_to_viewport(origin, viewport_up=(0, 0, 1), look_at=center)
    return visible


def _svg_paths(edges) -> tuple[str, str]:
    """(inner path markup, viewBox) of ExportSVG output for ``edges``."""
    exporter = ExportSVG(unit=Unit.MM)
    exporter.add_layer("l")
    exporter.add_shape(edges, layer="l")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "f.svg"
        exporter.write(str(path))
        text = path.read_text()
    inner = re.search(r'<g fill="none"[^>]*>(.*?)</g>\s*</g>', text, re.S)
    box = re.search(r'viewBox="([^"]+)"', text)
    if not inner or not box:
        raise ValueError("unexpected ExportSVG output: no layer group or viewBox")
    return re.sub(r"\s+", " ", inner.group(1)).strip(), box.group(1)


def figure_svg(shapes: list[Part], direction: tuple[float, float, float] = ISO_DIRECTION) -> str:
    """Render positioned solids as one isometric line drawing (visible edges only)."""
    if not shapes:
        raise ValueError("figure_svg needs at least one shape")
    paths, view_box = _svg_paths(_visible_edges(shapes, direction))
    x0, y0, w, h = (float(v) for v in view_box.split())
    pad = max(w, h) * 0.04
    x, y, w, h = x0 - pad, y0 - pad, w + 2 * pad, h + 2 * pad
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x:.2f} {y:.2f} {w:.2f} {h:.2f}" '
        f'fill="none" stroke="{STROKE}" stroke-linecap="round" stroke-linejoin="round">'
        f"<style>{STYLE}</style>"
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="#fff" '
        f'stroke="none"/>'
        f'<g transform="scale(1,-1)">{paths}</g></svg>'
    )


def write_figure(path: Path, shapes: list[Part]) -> Path:
    """Write ``figure_svg(shapes)`` to ``path``, creating parent folders."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(figure_svg(shapes))
    return path
