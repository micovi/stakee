"""End-to-end tests for the `stakee` CLI, run in-process into a temporary folder."""

import json
from pathlib import Path

import pytest

from stakee.cli import main, rail_positions
from stakee.core import divider_slot_positions


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def assert_part_files(part: dict) -> None:
    for key in ("stl", "step"):
        path = Path(part[key])
        assert path.is_file(), f"missing {path}"
        assert path.stat().st_size > 0, f"empty {path}"


def test_small_box_writes_non_empty_stl_and_step(capsys, tmp_path):
    code, out, err = run(capsys, "box", "1x1x2", "--out", str(tmp_path))

    assert code == 0, err
    assert sorted(p.name for p in tmp_path.iterdir()) == ["box-1x1x2.step", "box-1x1x2.stl"]
    assert (tmp_path / "box-1x1x2.stl").stat().st_size > 1000
    assert out.rstrip().endswith(str(tmp_path / "box-1x1x2.step"))


def test_box_with_dividers_label_and_cap_json_summary(capsys, tmp_path):
    code, out, err = run(
        capsys,
        "box", "2x2x3", "--dividers", "2x3", "--label", "ESP32", "--cap", "--json",
        "--out", str(tmp_path),
    )  # fmt: skip

    assert code == 0, err
    summary = json.loads(out)
    assert summary["ok"] is True
    assert summary["cavity_mm"] == [79.5, 79.5, 15.5]
    counts = {part["slug"]: part["count"] for part in summary["parts"]}
    assert counts == {
        "box-2x2x3": 1,
        "cap-2x2": 1,
        "rail-x-2x2x3": 2,
        "rail-y-2x2x3": 1,
        "label-esp32": 2,
    }
    for part in summary["parts"]:
        assert_part_files(part)
    compartments = summary["compartments"]
    assert compartments["y_rails_at_x_mm"] == [0.0]
    assert compartments["x_rails_at_y_mm"] == [-21.0, 21.0]
    assert summary["label"]["tile_mm"] == [59.8, 11.8, 0.6]


def test_file_names_are_deterministic(capsys, tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    for folder in (first, second):
        code, _, err = run(capsys, "cap", "1x1", "--label", "M3", "--out", str(folder))
        assert code == 0, err
    names = sorted(p.name for p in first.iterdir())
    assert names == sorted(p.name for p in second.iterdir())
    assert names == ["cap-1x1.step", "cap-1x1.stl", "label-m3.step", "label-m3.stl"]


def test_list_json_describes_sizes_and_options(capsys):
    code, out, _ = run(capsys, "list", "--json")

    assert code == 0
    summary = json.loads(out)
    assert "--dividers AxB" in summary["options"]
    assert summary["examples"]["2x2x3"] == [79.5, 79.5, 15.5]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["box", "2x2"], "2x2: expected NXxNYxH"),
        (["box", "0x1x3"], "0x1x3: footprint must be >= 1 unit per side"),
        (["box", "3x2x0"], "3x2x0: height must be >= 2 units"),
        (["box", "9x1x3"], "footprint must be <= 8 units"),
        (["box", "1x1x2", "--dividers", "5x1"], "at most 2 compartments; got 5"),
        (["box", "1x1x2", "--dividers", "0x2"], "compartment counts must be >= 1"),
        (["box", "1x1x2", "--label", "X"], "has no front label recess"),
        (["box", "1x1x3", "--label", "RASPBERRY PI PICO W"], "Shorten the text"),
        (["box", "1x1x3", "--label", "   "], "text must not be empty"),
        (["box", "1x1x2", "--lip-clearance", "2"], "must be between 0.0 and 1.0 mm"),
        (["box", "1x1x2", "--name", "../evil"], "use letters, digits"),
        (["cap", "2x2x3"], "2x2x3: expected NXxNY"),
    ],
)
def test_bad_input_exits_non_zero_with_reason(capsys, tmp_path, argv, message):
    code, _, err = run(capsys, *argv, "--out", str(tmp_path / "out"))

    assert code == 2
    assert message in err
    assert not (tmp_path / "out").exists()


def test_bad_input_with_json_prints_error_object(capsys, tmp_path):
    code, out, _ = run(capsys, "box", "1x1x0", "--json", "--out", str(tmp_path))

    assert code == 2
    error = json.loads(out)
    assert error["ok"] is False
    assert error["error"].startswith("1x1x0: height must be >= 2 units")


@pytest.mark.parametrize(
    ("units", "compartments", "expected"),
    [(1, 1, []), (1, 2, [0.0]), (3, 2, [0.0]), (2, 3, [-21.0, 21.0]), (3, 4, [-42.0, 0.0, 42.0])],
)
def test_rail_positions_spread_evenly(units, compartments, expected):
    assert rail_positions(units, compartments) == expected


@pytest.mark.parametrize("units", range(1, 9))
def test_rail_positions_are_distinct_real_slots_and_symmetric(units):
    slots = divider_slot_positions(units)
    for compartments in range(1, 2 * units + 1):
        rails = rail_positions(units, compartments)
        assert len(rails) == compartments - 1
        assert len(set(rails)) == len(rails)
        assert all(rail in slots for rail in rails)
        assert sorted(-rail for rail in rails) == rails


def test_default_output_folder_is_out_in_the_working_directory(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    code, out, err = run(capsys, "cap", "1x1", "--json")

    assert code == 0, err
    assert json.loads(out)["out_dir"] == str(tmp_path / "out" / "cap-1x1")
    assert (tmp_path / "out" / "cap-1x1" / "cap-1x1.stl").is_file()
