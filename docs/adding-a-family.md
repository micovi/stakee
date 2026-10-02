# Adding a family

A family is one generator module in `stakee/modules/` and one folder in `models/`; this page walks through adding one.

The example adds `partsbin`, a 2x2x6 crate with fixed inner walls. The code below passes `ruff check` and its `verify()` passes.

## 1. Write the module

Create `stakee/modules/<name>.py`. The build needs four things:

| Item | Role |
| --- | --- |
| Module docstring | Becomes the "How it works" section of `models/<name>/README.md` and the `description` in `models/index.json`. Required: the docs build fails without it. |
| `MODULE` | The family name, the same as the file name. Passed to `save()`. |
| `verify() -> bool` | Checks the geometry before anything is exported. Prints one `[PASS]` or `[FAIL]` line per check. Must return `True`, or the build stops. |
| `build() -> None` | Makes each part and calls `save(MODULE, part, PartInfo(...))`. |

```python
"""Parts bin: a deep crate with a fixed 2x2 grid of walls for loose components.

Built on ``make_box`` from ``stakee/core.py``, so it keeps the feet, the stacking lip, the
magnet pockets and the clip sockets, and stacks at exactly ``7 * h`` like any crate.

The walls stand on the floor and stop below the stacking seat
(``size.lip_top - SEAT_DEPTH``), so a crate or cap still seats on top.

Print upright on the feet, no supports.
"""

from build123d import Align, Box, Part, Pos

from stakee.core import FLOOR_Z, HEIGHT_UNIT, SEAT_DEPTH, BoxSize, make_box, make_cap
from stakee.export import PartInfo, save

MODULE = "partsbin"

SIZE = BoxSize(2, 2, 6)
WALL_THICKNESS = 1.2
SETTLE = 0.05  # mm a cap is lowered to prove it rests on the lip


def make_parts_bin(size: BoxSize) -> Part:
    """A crate with one X wall and one Y wall through the center."""
    cav_w, cav_d, _ = size.cavity
    height = size.lip_top - SEAT_DEPTH - FLOOR_Z - 1.0
    bottom = (Align.CENTER, Align.CENTER, Align.MIN)
    walls = Pos(0, 0, FLOOR_Z) * Box(cav_w, WALL_THICKNESS, height, align=bottom)
    walls += Pos(0, 0, FLOOR_Z) * Box(WALL_THICKNESS, cav_d, height, align=bottom)
    return make_box(size) + walls


def _overlap(a: Part, b: Part) -> float:
    common = a & b
    return common.volume if common else 0.0


def verify() -> bool:
    """The bin is valid, and a cap seats on it at exactly 7 * h."""
    part = make_parts_bin(SIZE)
    pitch = SIZE.h * HEIGHT_UNIT
    cap = make_cap(SIZE.nx, SIZE.ny)
    clear = _overlap(part, Pos(0, 0, pitch) * cap)
    seated = _overlap(part, Pos(0, 0, pitch - SETTLE) * cap)
    checks = (
        ("valid", part.is_valid, ""),
        ("cap clear at 7h", clear < 1e-6, f"{clear:.6f} mm3"),
        ("cap seated", seated > 0, f"{seated:.2f} mm3 lowered {SETTLE} mm"),
    )
    ok = True
    for name, passed, detail in checks:
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name} {detail}")
    return ok


def build() -> None:
    tag = f"{SIZE.nx}x{SIZE.ny}x{SIZE.h}"
    save(
        MODULE,
        make_parts_bin(SIZE),
        PartInfo(
            slug=f"parts-bin-{tag}",
            title=f"Parts bin {tag}",
            blurb="Crate with four fixed compartments for loose components.",
            material="PLA or PETG",
            print_notes="Upright, no supports, 3 walls, 15% infill. Optional 6x2 mm magnets.",
            footprint=tag,
        ),
    )
```

Guidelines:

- Build on [`stakee/core.py`](../stakee/core.py) (`BoxSize`, `make_box`, `make_cap`, `feet`, `lip_pocket`, the slot, socket and label helpers) so the part keeps the contract. See [The system](system.md).
- Keep the coordinate convention: centered on XY, lowest point at z = 0, front face -Y.
- Check in `verify()` what matters for the part: valid solids, seating at `7 × h`, clearances. See [`stakee/modules/crates.py`](../stakee/modules/crates.py) and [`stakee/modules/calibration.py`](../stakee/modules/calibration.py) for examples.
- `save()` refuses a solid that is not valid. Slugs must be unique within the family; a second `save()` with the same slug replaces the first entry.
- `PartInfo` needs `slug`, `title`, `blurb`, `material` and `print_notes`; the family page shows all of them. `size_mm` and `files` are filled in by `save()`. The fields are listed in [Building the library](build.md#manifest-fields).
- Docstrings use RST-style ``` ``double backticks`` ``` for code; the docs build turns them into Markdown code.

## 2. Register the family

Add a `Family` to `FAMILIES` in [`stakee/families.py`](../stakee/families.py). Its position in the tuple is its position in the catalogue and the build order.

```python
FAMILIES: tuple[Family, ...] = (
    # ... the existing families ...
    Family(
        "partsbin",
        "Parts bin",
        "A crate with four fixed compartments for loose components.",
    ),
)
```

| Field | Use |
| --- | --- |
| `module` | Module name in `stakee/modules/` and folder name in `models/` |
| `title` | Page title and catalogue name |
| `summary` | One sentence: what it is and why you would print it. Shown under the title and in the catalogue. |

## 3. Build it

```bash
uv run stakee-build --only partsbin
```

This runs `verify()`, then `build()`, and writes:

- `models/partsbin/stl/`, `step/`, `preview/` and `manifest.json`
- `models/partsbin/README.md`
- the updated `models/README.md` and `models/index.json`

Open `models/partsbin/README.md` and check the parts table, the print notes and the "How it works" section.

## 4. Check and commit

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Commit the module, `stakee/families.py` and the generated files together:

```bash
git add stakee/modules/partsbin.py stakee/families.py models/partsbin models/README.md models/index.json
git commit -m "Add parts bin family"
```

Do not edit the generated files in `models/` by hand. To change the page, change the docstring, `families.py` or the `PartInfo`, and rebuild ([Building the library](build.md#generated-pages)).
