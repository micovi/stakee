"""Tests for exporting one part: file layout, manifest entry, stable bytes, refusals."""

import json

import pytest
from build123d import Box

from stakee import export
from stakee.core import make_cap


def info(slug: str = "cap") -> export.PartInfo:
    return export.PartInfo(slug, "Cap", "A lid.", "PLA", "Upside down.")


def test_save_writes_files_and_manifest_entry(models_dir):
    saved = export.save("crates", make_cap(1, 1), info())

    assert saved.files == {
        "stl": "models/crates/stl/cap.stl",
        "step": "models/crates/step/cap.step",
        "svg": "models/crates/preview/cap.svg",
    }
    for path in saved.files.values():
        assert (models_dir / path.removeprefix("models/")).stat().st_size > 0
    manifest = json.loads((models_dir / "crates" / "manifest.json").read_text())
    assert manifest["cap"]["size_mm"] == [41.5, 41.5, 7.2]


def test_save_is_byte_for_byte_repeatable(models_dir):
    def export_once() -> list[bytes]:
        export.save("crates", make_cap(1, 1), info())
        folder = models_dir / "crates"
        return [(folder / name).read_bytes() for name in ("step/cap.step", "manifest.json")]

    first = export_once()
    assert export.STEP_TIMESTAMP.encode() in first[0]
    assert export_once() == first


def test_stable_step_renumbers_every_assembly_link_in_order():
    text = (
        "#9 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('17','=>[0:1:1:2]','',#5,#27,$);\n"
        "#12 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('18','=>[0:1:1:3]','',#5,#28,$);\n"
    )

    assert export.stable_step(text) == (
        "#9 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('1','=>[0:1:1:2]','',#5,#27,$);\n"
        "#12 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('2','=>[0:1:1:3]','',#5,#28,$);\n"
    )


@pytest.mark.parametrize("slug", ["../escape", "Cap", "a/b", "", "-cap"])
def test_save_refuses_unsafe_slugs(models_dir, slug):
    with pytest.raises(ValueError, match="slug must match"):
        export.save("crates", Box(1, 1, 1), info(slug))
    assert not any(models_dir.rglob("*.stl"))


def test_failed_stl_write_raises(models_dir, monkeypatch):
    monkeypatch.setattr(export, "export_stl", lambda *args, **kwargs: False)

    with pytest.raises(OSError, match="STL export to .*cap.stl failed"):
        export.save("crates", make_cap(1, 1), info())
    assert not (models_dir / "crates" / "manifest.json").exists()
