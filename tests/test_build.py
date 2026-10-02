"""Tests for `stakee-build`: family selection, clearing and the verify-then-build gate."""

import sys
import types

import pytest

from stakee import build
from stakee.families import MODULES


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, list(MODULES)),
        ("kit,crates", ["crates", "kit"]),
        (" kit , kit ", ["kit"]),
    ],
)
def test_parse_only_keeps_catalogue_order(text, expected):
    assert build.parse_only(text) == expected


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("crate", "no family named \\['crate'\\]"),
        ("crates,nope", "no family named \\['nope'\\]"),
        (",", "name at least one family"),
        ("", "name at least one family"),
    ],
)
def test_parse_only_rejects_unknown_or_empty(text, message):
    with pytest.raises(SystemExit, match=message):
        build.parse_only(text)


def test_only_and_docs_only_are_exclusive(capsys):
    with pytest.raises(SystemExit):
        build.main(["--only", "crates", "--docs-only"])
    assert "not allowed with argument" in capsys.readouterr().err


def populate(folder) -> None:
    for name in build.GENERATED_DIRS:
        (folder / name).mkdir(parents=True)
        (folder / name / "old.txt").write_text("x")
    (folder / "manifest.json").write_text("{}")
    (folder / "README.md").write_text("# keep")


def test_clear_family_removes_only_generated_files(models_dir):
    populate(models_dir / "kit")
    (models_dir / "crates").mkdir()
    (models_dir / "crates" / "manifest.json").write_text("{}")

    build.clear_family("kit")

    assert sorted(p.name for p in (models_dir / "kit").iterdir()) == ["README.md"]
    assert (models_dir / "crates" / "manifest.json").exists()


@pytest.fixture
def fake_family(monkeypatch):
    module = types.ModuleType("stakee.modules.fake")
    monkeypatch.setitem(sys.modules, "stakee.modules.fake", module)
    return module


def test_failed_verify_exports_nothing_and_keeps_old_files(models_dir, fake_family):
    populate(models_dir / "fake")
    fake_family.verify = lambda: False
    fake_family.build = lambda: pytest.fail("build() ran after a failed verify()")

    with pytest.raises(SystemExit, match="fake: verify\\(\\) failed, nothing exported"):
        build.build_family("fake")
    assert (models_dir / "fake" / "stl" / "old.txt").exists()


def test_family_without_verify_is_refused(fake_family):
    fake_family.build = lambda: None

    with pytest.raises(SystemExit, match="fake: needs verify\\(\\) and build\\(\\)"):
        build.build_family("fake")


def test_build_clears_stale_parts_before_exporting(models_dir, fake_family):
    populate(models_dir / "fake")
    fake_family.verify = lambda: True
    fake_family.build = lambda: (models_dir / "fake" / "manifest.json").write_text('{"new": 1}')

    build.build_family("fake")

    assert not (models_dir / "fake" / "stl").exists()
    assert (models_dir / "fake" / "manifest.json").read_text() == '{"new": 1}'


def test_build_failure_says_how_to_restore(models_dir, fake_family):
    fake_family.verify = lambda: True

    def broken() -> None:
        raise ValueError("solid is not valid")

    fake_family.build = broken
    with pytest.raises(SystemExit, match="git checkout -- models/fake"):
        build.build_family("fake")
