# Building the library

How `stakee-build` verifies and generates the files in `models/`, and how to run the tests and linters.

Source: [`stakee/build.py`](../stakee/build.py), [`stakee/export.py`](../stakee/export.py), [`stakee/docs.py`](../stakee/docs.py).

## Commands

```bash
uv run stakee-build
uv run stakee-build --only crates,kit
uv run stakee-build --docs-only
```

| Option | Effect |
| --- | --- |
| none | Verifies and builds every family, then rewrites the README pages. |
| `--only A,B` | Verifies and builds only these families (comma-separated module names), then rewrites the README pages of all families. Families always run in catalogue order. |
| `--docs-only` | Skips verify and build; only rewrites `models/index.json`, `models/README.md` and `models/<family>/README.md`. Cannot be combined with `--only`. |

An unknown family name stops the build with exit status 1:

```text
--only 'foo': no family named ['foo']; known: crates, dividers, inserts, baglib, drawers, pocket, kit, magtray, esd, wirespool, wallrail, calibration
```

## Verify, then build

For each selected family, in the order of [`stakee/families.py`](../stakee/families.py):

1. Import `stakee.modules.<family>`. It must have callable `verify()` and `build()`, or the build stops.
2. Run `verify()`. It must return `True`. Anything else stops the build, and this family exports nothing. Families earlier in the run are already written.
3. Delete the family's `stl/`, `step/`, `preview/` and `manifest.json`, so the folder lists only what the generator exports now.
4. Run `build()`. It calls `save()` once per part. If `build()` raises, the build stops with the error and the family's folder is left partly written: fix the error and rebuild, or restore it with `git checkout -- models/<family>`.

`verify()` prints one line per check. For example, the crates family:

```text
  [PASS] BoxSize(nx=2, ny=2, h=3) + box: 0.000000 mm3 at 7h, 16.58 mm3 lowered 0.05 mm
  [PASS] BoxSize(nx=2, ny=2, h=3) + cap: 0.000000 mm3 at 7h, 18.08 mm3 lowered 0.05 mm
```

## What `save()` writes

`save(module, part, info)` in `export.py` refuses a slug that is not lowercase letters, digits, `.` and `-`, and a solid that is not valid, then writes (and raises if a writer reports failure):

| File | Content |
| --- | --- |
| `models/<family>/stl/<slug>.stl` | Mesh for slicing, 0.02 mm linear and 0.15 rad angular tolerance |
| `models/<family>/step/<slug>.step` | Exact solid for CAD; the header timestamp is pinned so an unchanged part exports byte for byte the same |
| `models/<family>/preview/<slug>.svg` | Hidden-line line art, front-right-top view, white background |
| `models/<family>/manifest.json` | The part's `PartInfo`, keyed by slug |

## Manifest fields

Each entry of `manifest.json` is a `PartInfo` from `export.py`:

| Field | Type | Meaning |
| --- | --- | --- |
| `slug` | str | File stem, unique within the family: lowercase letters, digits, `.`, `-` |
| `title` | str | Short human name |
| `blurb` | str | One or two sentences: what it is and why you want it |
| `material` | str | Recommended filament, e.g. `"PETG"` or `"PLA + TPU"` |
| `print_notes` | str | Orientation, supports, infill, inserts (magnets, NFC…) |
| `color` | str | Suggested filament colour (hex), the default colour in the site's 3D viewer; default `"#d9d4c7"` |
| `footprint` | str | e.g. `"2x2x6"` in grid units, or `""` for parts that are not boxes |
| `size_mm` | [x, y, z] | Bounding box in mm, rounded to 0.1 mm; filled in by `save()` |
| `files` | object | Repository-relative paths under the keys `stl`, `step` and `svg`; filled in by `save()` |

Example from `models/crates/manifest.json`:

```json
"cap-2x2": {
  "slug": "cap-2x2",
  "title": "Cap 2x2",
  "blurb": "Lid that seats into any crate's stacking lip; recessed label on top.",
  "material": "PETG",
  "print_notes": "Upside down (plate on the bed), no supports.",
  "color": "#f2a03d",
  "footprint": "2x2",
  "size_mm": [83.5, 83.5, 7.2],
  "files": {
    "stl": "models/crates/stl/cap-2x2.stl",
    "step": "models/crates/step/cap-2x2.step",
    "svg": "models/crates/preview/cap-2x2.svg"
  }
}
```

## Generated pages

After building, `write_docs()` in `docs.py` rewrites these files for every family that has a manifest:

| File | Made from |
| --- | --- |
| `models/README.md` | Catalogue: title and summary from `families.py`, the first part's preview, the part count |
| `models/<family>/README.md` | Title and summary from `families.py`; parts table and grouped print notes from `manifest.json`; "How it works" from the module docstring |
| `models/index.json` | `{"families": [...]}`: `module`, `title`, `summary`, `description` (the module docstring), `manifest` path and `parts` count, for the docs site |

In docstrings, RST-style ``` ``literals`` ``` become Markdown `` `literals` ``.

These files start with a "Generated" comment. Do not edit them by hand: change the module docstring, `families.py` or the `PartInfo` in the module, then run:

```bash
uv run stakee-build --docs-only
```

## When to rebuild

| You changed | Run |
| --- | --- |
| A module docstring, `families.py` titles or summaries | `uv run stakee-build --docs-only` |
| One family's geometry or `PartInfo` | `uv run stakee-build --only <family>` |
| `stakee/core.py` | `uv run stakee-build` (every family uses it) |

Commit the regenerated files in `models/` with the change that caused them.

## Tests and lint

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

`tests/` mirrors the package: `test_cli.py` runs the `stakee` CLI in-process into a temporary folder, `test_export.py`, `test_build.py` and `test_docs.py` cover exporting, the build command and the generated pages. Ruff uses a 100-character line length and the rule sets `E`, `F`, `I`, `B`, `UP` and `SIM` (see `pyproject.toml`).
