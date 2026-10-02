# Getting started

Install the generator, print the calibration coupons, then print your first crate.

## Prerequisites

| What | Why |
| --- | --- |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Installs Python and the dependencies, runs the commands. |
| Python 3.13 | Required by `pyproject.toml`. uv reads `.python-version` and installs it for you. |
| A 3D printer and a slicer | The library ships STL files; any slicer that opens STL works. |

You do not need the Python tools to print the ready-made parts. The STL files in [`models/`](../models/README.md) can be downloaded and sliced directly.

## Install

```bash
git clone https://github.com/micovi/stakee.git
cd stakee
uv sync
```

`uv sync` creates `.venv/` with the pinned dependencies (`build123d`, plus `pytest` and `ruff` for development). Check that it works:

```bash
uv run stakee list
```

## First prints

1. **Calibration coupons.** Print the parts in [Calibration](../models/calibration/README.md) in the filament and with the settings you will use for crates. They tell you the lip clearance and divider fit for your printer. See [Printing: calibration](printing.md#calibration).
2. **A crate and a cap.** Start with [`crate-2x2x3`](../models/crates/README.md) and [`cap-2x2`](../models/crates/README.md). Or generate them with the clearance you picked (0.25 mm is the default):

   ```bash
   uv run stakee box 2x2x3 --cap --lip-clearance 0.25
   ```

3. **A second crate.** Stack it on the first to check the fit. A crate seats in the lip below at exactly `7 × h` mm, with a 0.75 mm gap between the bodies. See [The system](system.md#stacking).

## Where files go

| Source | Location |
| --- | --- |
| Ready-made library | `models/<family>/stl/`, `models/<family>/step/`, `models/<family>/preview/` |
| `stakee box` / `stakee cap` | `./out/<name>/` in the current directory, or the folder given with `--out` |

`out/` is listed in `.gitignore`. File names are fixed per part, for example `box-2x2x3.stl` and `cap-2x2.step`. See [CLI reference](cli.md#output-files).

## Opening the files

| Format | Use | Open with |
| --- | --- | --- |
| STL | Printing | Any slicer (PrusaSlicer, OrcaSlicer, Bambu Studio, Cura). Units are millimetres. |
| STEP | Remixing | Any CAD program that imports STEP (FreeCAD, Fusion, Onshape). The solids are exact, not meshes. |
| SVG | Preview | Any browser. Line art drawn from the same solid as the STL. |

Parts are modelled with Z up and the front face toward -Y. The print notes on each family page say which face goes on the bed.

## Next steps

- [CLI reference](cli.md): all `stakee` options.
- [The system](system.md): the grid, the lip and the other shared features.
- [Printing](printing.md): materials per family, magnets, ESD.
