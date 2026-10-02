"""Tests for the generated wiki pages and the build command's family selection."""

import json

import pytest

from stakee import docs, export
from stakee.build import parse_only
from stakee.families import FAMILIES, MODULES, family


def fake_part(module: str, slug: str, notes: str = "Upright, no supports.") -> dict:
    return {
        "slug": slug,
        "title": f"Part {slug}",
        "blurb": "Holds | things.",
        "material": "PETG",
        "print_notes": notes,
        "color": "#ffffff",
        "footprint": "",
        "assembly": None,
        "size_mm": [41.5, 41.5, 25.0],
        "files": {
            "stl": f"models/{module}/stl/{slug}.stl",
            "step": f"models/{module}/step/{slug}.step",
            "svg": f"models/{module}/preview/{slug}.svg",
        },
    }


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "MODELS", tmp_path)
    monkeypatch.setattr(docs, "MODELS", tmp_path)
    return tmp_path


def write_manifest(models_dir, module: str, parts: list[dict]) -> None:
    folder = models_dir / module
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({p["slug"]: p for p in parts}))


def test_every_family_has_a_module_docstring():
    for item in FAMILIES:
        assert docs.module_docstring(item.module).strip()


def test_family_lookup_names_known_families_on_typo():
    assert family("crates").title == "Crates"
    with pytest.raises(KeyError, match="known: crates"):
        family("crate")


def test_family_page_links_files_relative_to_the_family_folder():
    item = family("crates")
    page = docs.family_page(item, [fake_part("crates", "a")])

    assert "[STL](stl/a.stl) · [STEP](step/a.step)" in page
    assert '<img src="preview/a.svg"' in page
    assert "41.5 × 41.5 × 25" in page
    assert "Holds \\| things." in page  # a pipe would split the table cell
    assert "uv run stakee-build --only crates" in page


def test_print_notes_group_parts_that_share_a_note():
    parts = [
        fake_part("crates", "a"),
        fake_part("crates", "b"),
        fake_part("crates", "c", notes="On its side."),
    ]
    notes = docs._print_notes(parts)

    assert notes == [
        "- **Part a, Part b**: Upright, no supports.",
        "- **Part c**: On its side.",
    ]


def test_write_docs_skips_unbuilt_families_and_writes_index(models_dir):
    write_manifest(models_dir, "kit", [fake_part("kit", "clip")])
    write_manifest(models_dir, "crates", [fake_part("crates", "a"), fake_part("crates", "b")])

    written = docs.write_docs()

    assert {p.relative_to(models_dir).as_posix() for p in written} == {
        "index.json",
        "README.md",
        "crates/README.md",
        "kit/README.md",
    }
    index = json.loads((models_dir / "index.json").read_text())
    assert [(f["module"], f["parts"]) for f in index["families"]] == [("crates", 2), ("kit", 1)]
    catalogue = (models_dir / "README.md").read_text()
    assert catalogue.index("crates/README.md") < catalogue.index("kit/README.md")


def test_write_docs_without_manifests_explains_how_to_build(models_dir):
    with pytest.raises(SystemExit, match="run `uv run stakee-build` first"):
        docs.write_docs()


def test_rst_literals_become_markdown_code():
    assert docs._md("seats at ``7 * h`` on ``BoxSize``") == "seats at `7 * h` on `BoxSize`"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, list(MODULES)),
        ("kit,crates", ["crates", "kit"]),
        (" kit , kit ", ["kit"]),
    ],
)
def test_parse_only_keeps_catalogue_order(text, expected):
    assert parse_only(text) == expected


@pytest.mark.parametrize("text", ["crate", "crates,nope", ",", ""])
def test_parse_only_rejects_unknown_or_empty(text):
    with pytest.raises(SystemExit, match="known: crates"):
        parse_only(text)


def test_save_is_byte_for_byte_repeatable(models_dir):
    from stakee.core import make_cap

    def export_once() -> list[bytes]:
        info = export.save("crates", make_cap(1, 1), export.PartInfo("cap", "Cap", "b", "PLA", "n"))
        assert info.files["step"] == "models/crates/step/cap.step"
        folder = models_dir / "crates"
        return [(folder / name).read_bytes() for name in ("step/cap.step", "manifest.json")]

    first = export_once()
    assert b"1970-01-01T00:00:00" in first[0]
    assert export_once() == first
