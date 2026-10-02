"""Tests for the generated wiki pages: models/README.md, models/<family>/README.md, index.json."""

import json

import pytest

from stakee import docs, export
from stakee.families import FAMILIES, family


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


def test_module_docstrings_render_as_plain_markdown():
    """A docstring line starting with '>' or '#' would turn into a quote or heading."""
    for item in FAMILIES:
        for line in docs.module_docstring(item.module).splitlines():
            assert not line.lstrip().startswith((">", "#")), f"{item.module}: {line!r}"


def test_module_without_docstring_is_refused(tmp_path, monkeypatch):
    (tmp_path / "stakee" / "modules").mkdir(parents=True)
    (tmp_path / "stakee" / "modules" / "bare.py").write_text("X = 1\n")
    monkeypatch.setattr(docs, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="bare.py: module has no docstring"):
        docs.module_docstring("bare")


def test_catalogue_links_previews_inside_the_family_folder():
    page = docs.catalogue_page([(family("kit"), [fake_part("kit", "clip")])])

    assert '<img src="kit/preview/clip.svg" width="120" alt="Part clip">' in page
    assert "[**Carry kit**](kit/README.md)" in page


def test_alt_text_is_html_escaped():
    part = fake_part("crates", "a") | {"title": 'Cap "deep" <2x2>'}
    page = docs.family_page(family("crates"), [part])

    assert 'alt="Cap &quot;deep&quot; &lt;2x2&gt;"' in page


def test_every_committed_manifest_lists_existing_files():
    for item in FAMILIES:
        parts = export.read_manifest(item.module)
        assert parts, f"models/{item.module}/manifest.json is missing or empty"
        for part in parts.values():
            for path in part["files"].values():
                assert (export.ROOT / path).is_file(), f"{item.module}: {path} missing"
