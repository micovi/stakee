# CLI reference

The `stakee` command generates print-ready crates, caps, divider rails and label tiles as STL and STEP files.

Source: [`stakee/cli.py`](../stakee/cli.py). Run it with `uv run stakee` from the repository.

```bash
uv run stakee box NXxNYxH [options]
uv run stakee cap NXxNY [options]
uv run stakee list [--json]
```

## Sizes

| Value | Meaning | Range |
| --- | --- | --- |
| `NX`, `NY` | Footprint in 42 mm grid units, `NX` along X (width), `NY` along Y (depth) | 1 to 8 (`MAX_UNITS`) |
| `H` | Height in 7 mm units; this is also the stack pitch | 2 to 40 (`MIN_HEIGHT`, `MAX_HEIGHT`) |

Sizes are case-insensitive and surrounding spaces are ignored: `3x2x6`, `3X2X6` and `" 3x2x6 "` are the same. Outer dimensions and cavities are explained in [The system](system.md#outer-size-and-cavity).

## `stakee box`

```bash
uv run stakee box NXxNYxH [--dividers AxB] [--label TEXT] [--cap] [--no-magnets] [--no-sockets] [--lip-clearance MM] [--name NAME] [--out DIR] [--json]
```

Exports one crate, plus the optional cap, divider rails and label tile.

| Option | Default | Effect |
| --- | --- | --- |
| `--dividers AxB` | none | `A` compartments across X, `B` along Y. Exports the rails, prints the compartment sizes. |
| `--label TEXT` | none | Press-fit tile for the front label recess, text embossed 0.4 mm. Needs `H` ≥ 3. |
| `--cap` | off | Also exports a cap for the same footprint. |
| `--no-magnets` | off | Omits the 6.5 × 2.4 mm magnet pockets under the feet. |
| `--no-sockets` | off | Omits the stack-clip sockets on the side walls. |
| `--lip-clearance MM` | `0.25` | Horizontal play between an upper crate's feet and this crate's lip, 0.15 to under 1.0. |
| `--name NAME` | derived | Name of the output folder under `./out/`. |
| `--out DIR` | `./out/<name>/` | Output folder. |
| `--json` | off | Prints a JSON summary on stdout instead of the text summary. |

Every crate gets divider slots; there is no option to turn them off.

### `--dividers AxB`

- `A` and `B` must be ≥ 1.
- A side that is `n` units long has `2n - 1` divider slots (every 21 mm), so `A` ≤ 2·`NX` and `B` ≤ 2·`NY`.
- `A - 1` Y rails (`rail-y-…`) split the crate across X. `B - 1` X rails (`rail-x-…`) split it along Y. A rail file is exported once, with the number of copies to print in `count`.
- Rails go into the slots closest to an even split. When the ideal position falls halfway between two slots, the rail takes the one farther from the center.
- Rails are as tall as the cavity minus 2 mm.
- `widths_mm` and `depths_mm` in the summary are approximate clear sizes between the walls and the rail faces.
- `--dividers 1x1` exports no rails.

Example: `2x2x3 --dividers 2x3` puts one Y rail at x = 0 and two X rails at y = −21 and y = 21. The compartments are 39.1 mm wide and 18.1, 40.8 and 18.1 mm deep.

### `--label TEXT`

- Leading and trailing spaces are removed. The text must not be empty.
- The crate must be at least 3 units tall (`LABEL_MIN_HEIGHT_UNITS`); lower crates have no front label recess.
- The tile is the label recess minus 0.1 mm per side: 11.8 mm tall, 0.6 mm thick, with 0.4 mm of embossed text. Swap filament at z = 0.6 mm for coloured text.
- The text is bold and keeps 1 mm of margin on every side. The font is 7 mm (`FONT_SIZE`). If the text does not fit, the font is scaled down to fit and rounded down to 0.1 mm. Below 3.5 mm (`MIN_FONT_SIZE`) the command fails.

| Crate width | Tile | Text area |
| --- | --- | --- |
| 1 unit | 25.3 × 11.8 mm | 23.3 × 9.8 mm |
| 2 units or more | 59.8 × 11.8 mm | 57.8 × 9.8 mm |

With `--cap`, the tile `count` is 2: one for the crate front, one for the recess on top of the cap.

### `--lip-clearance MM`

The clearance is cut into this crate's lip, so it sets the fit of whatever stacks on this crate. The feet are not changed. Pick the value with the [calibration coupons](printing.md#calibration).

Accepted values: 0.15 mm up to, but not including, 1.0 mm (`LIP_CLEARANCE_MIN` and `LIP_CLEARANCE_MAX` in [`core.py`](../stakee/core.py)). Below 0.15 mm the cavity wall, not the lip, sets the play. Anything else is a usage error (exit status 2):

```text
stakee box: error: --lip-clearance 0.1: must be >= 0.15 and < 1.0 mm
```

### `--name` and `--out`

- `--name` must start with a letter or digit and contain only letters, digits, `.`, `_` and `-`.
- `--name` sets the folder name and the `name` field of the summary. It does not change the part file names.
- `--out` is expanded (`~`) and made absolute. The folder is created if needed. Existing files with the same names are overwritten.
- When `--out` is given, `--name` only changes the `name` field.

Default names:

| Command | Default name |
| --- | --- |
| `box` | `box-<NX>x<NY>x<H>`, then `-d<AxB>` with `--dividers`, then `-<label>` with `--label` |
| `cap` | `cap-<NX>x<NY>`, then `-<label>` with `--label` |

`<label>` is the text in lower case, with every run of characters other than `a-z` and `0-9` replaced by `-` and leading or trailing `-` removed (`label` if nothing is left). Example: `uv run stakee box 2x2x6 --dividers 2x2 --label ESP32 --cap` writes to `./out/box-2x2x6-d2x2-esp32/`.

## `stakee cap`

```bash
uv run stakee cap NXxNY [--label TEXT] [--name NAME] [--out DIR] [--json]
```

Exports a cap for any crate with an `NX` × `NY` footprint. With `--label`, also exports a label tile for the recess on top of the cap (`count` 1). `--label`, `--name`, `--out` and `--json` behave as for `box`.

## `stakee list`

```bash
uv run stakee list
uv run stakee list --json
```

Prints the size ranges, the cavity of six common sizes and the options. It writes no files.

```text
Sizes: NXxNYxH, NX/NY 1..8 x 42 mm, H 2..40 x 7 mm (stack pitch).
Cavity (W x D x H mm) for common sizes:
  1x1x3     37.5 x   37.5 x  15.5
  2x1x3     79.5 x   37.5 x  15.5
  2x2x3     79.5 x   79.5 x  15.5
  2x2x6     79.5 x   79.5 x  36.5
  3x2x6    121.5 x   79.5 x  36.5
  4x2x6    163.5 x   79.5 x  36.5
Commands: stakee box NXxNYxH [opts] | stakee cap NXxNY [--label T] | stakee list
Options:
  --dividers AxB       A compartments across X, B along Y: exports X/Y rails, prints counts
  --label TEXT         press-fit tile for the front label recess, text embossed 0.4 mm
  --cap                also export a lid for the same footprint
  --no-magnets         omit the 6.5x2.4 mm magnet pockets under the feet
  --no-sockets         omit the stack-clip sockets on the side walls
  --lip-clearance MM   foot/lip play, default 0.25 (tune for your printer)
  --name NAME          output folder name and summary name (default derived from the options)
  --out DIR            output folder (default ./out/<name>/)
  --json               print a machine-readable summary on stdout
Dividers: AxB with A <= 2*NX and B <= 2*NY (slots every 21 mm).
Labels need box height >= 3.
```

`--json` prints the same data (arrays shown on one line here):

```json
{
  "ok": true,
  "command": "list",
  "grid_mm": 42.0,
  "height_unit_mm": 7.0,
  "footprint_units": [1, 8],
  "height_units": [2, 40],
  "examples": {
    "1x1x3": [37.5, 37.5, 15.5],
    "2x1x3": [79.5, 37.5, 15.5],
    "2x2x3": [79.5, 79.5, 15.5],
    "2x2x6": [79.5, 79.5, 36.5],
    "3x2x6": [121.5, 79.5, 36.5],
    "4x2x6": [163.5, 79.5, 36.5]
  },
  "options": {
    "--dividers AxB": "A compartments across X, B along Y: exports X/Y rails, prints counts",
    "--label TEXT": "press-fit tile for the front label recess, text embossed 0.4 mm",
    "--cap": "also export a lid for the same footprint",
    "--no-magnets": "omit the 6.5x2.4 mm magnet pockets under the feet",
    "--no-sockets": "omit the stack-clip sockets on the side walls",
    "--lip-clearance MM": "foot/lip play, default 0.25 (tune for your printer)",
    "--name NAME": "output folder name and summary name (default derived from the options)",
    "--out DIR": "output folder (default ./out/<name>/)",
    "--json": "print a machine-readable summary on stdout"
  },
  "dividers_max": "AxB with A <= 2*NX and B <= 2*NY (slots every 21 mm)",
  "label_min_box_height": 3
}
```

## Output files

Each part is written as `<slug>.stl` and `<slug>.step` in the output folder. STL is tessellated with 0.02 mm linear and 0.15 rad angular tolerance.

| Part | Slug | Count |
| --- | --- | --- |
| Crate | `box-<NX>x<NY>x<H>` | 1 |
| Cap (`--cap`, or `stakee cap`) | `cap-<NX>x<NY>` | 1 |
| X rail (`--dividers`, `B` > 1) | `rail-x-<NX>x<NY>x<H>` | `B - 1` |
| Y rail (`--dividers`, `A` > 1) | `rail-y-<NX>x<NY>x<H>` | `A - 1` |
| Label tile (`--label`) | `label-<label>` | 1, or 2 with `box --cap` |

The text summary lists the count, slug and print notes of each part, then the file paths:

```text
stakee box 2x2x3 -> /path/to/out
Cavity: 79.5 x 79.5 x 15.5 mm
Compartments: 2 x 3, widths [39.1, 39.1] mm, depths [18.1, 40.8, 18.1] mm
Label: font 7.0 mm
Print:
  1x box-2x2x3  (Upright on its feet, no supports, 0.2 mm layers. Glue 6x2 mm magnets into the pockets under the feet.)
  1x cap-2x2  (Plate on the bed (upside down), no supports.)
  2x rail-x-2x2x3  (Flat on the bed, no supports, 100% infill; slide the ends into the wall slots.)
  1x rail-y-2x2x3  (Flat on the bed, no supports, 100% infill; slide the ends into the wall slots.)
  2x label-esp32  (Flat, text up; swap filament at z = 0.6 mm. Press into the label recess (0.1 mm clearance per side), a dab of glue if loose.)
Files:
  /path/to/out/box-2x2x3.stl
  /path/to/out/box-2x2x3.step
  ...
```

## JSON output

With `--json`, the command prints one JSON object on stdout. This is the real output of:

```bash
uv run stakee box 2x2x3 --dividers 2x3 --label ESP32 --cap --out /path/to/out --json
```

```json
{
  "ok": true,
  "command": "box",
  "size": "2x2x3",
  "outer_mm": [83.5, 83.5, 25.0],
  "stack_pitch_mm": 21.0,
  "cavity_mm": [79.5, 79.5, 15.5],
  "compartments": {
    "across_x": 2,
    "along_y": 3,
    "y_rails_at_x_mm": [0.0],
    "x_rails_at_y_mm": [-21.0, 21.0],
    "widths_mm": [39.1, 39.1],
    "depths_mm": [18.1, 40.8, 18.1],
    "rail_height_mm": 13.5
  },
  "label": {
    "text": "ESP32",
    "font_size_mm": 7.0,
    "tile_mm": [59.8, 11.8, 0.6],
    "text_height_mm": 0.4,
    "filament_swap_at_z_mm": 0.6
  },
  "name": "box-2x2x3-d2x3-esp32",
  "out_dir": "/path/to/out",
  "parts": [
    {
      "slug": "box-2x2x3",
      "title": "Box 2x2x3",
      "count": 1,
      "size_mm": [83.5, 83.5, 25.0],
      "print_notes": "Upright on its feet, no supports, 0.2 mm layers. Glue 6x2 mm magnets into the pockets under the feet.",
      "stl": "/path/to/out/box-2x2x3.stl",
      "step": "/path/to/out/box-2x2x3.step"
    },
    {
      "slug": "cap-2x2",
      "title": "Cap 2x2",
      "count": 1,
      "size_mm": [83.5, 83.5, 7.15],
      "print_notes": "Plate on the bed (upside down), no supports.",
      "stl": "/path/to/out/cap-2x2.stl",
      "step": "/path/to/out/cap-2x2.step"
    },
    {
      "slug": "rail-x-2x2x3",
      "title": "X rail 2x2x3",
      "count": 2,
      "size_mm": [80.7, 1.5, 13.5],
      "print_notes": "Flat on the bed, no supports, 100% infill; slide the ends into the wall slots.",
      "stl": "/path/to/out/rail-x-2x2x3.stl",
      "step": "/path/to/out/rail-x-2x2x3.step"
    },
    {
      "slug": "rail-y-2x2x3",
      "title": "Y rail 2x2x3",
      "count": 1,
      "size_mm": [80.7, 1.5, 13.5],
      "print_notes": "Flat on the bed, no supports, 100% infill; slide the ends into the wall slots.",
      "stl": "/path/to/out/rail-y-2x2x3.stl",
      "step": "/path/to/out/rail-y-2x2x3.step"
    },
    {
      "slug": "label-esp32",
      "title": "Label tile 'ESP32'",
      "count": 2,
      "size_mm": [59.8, 11.8, 1.0],
      "print_notes": "Flat, text up; swap filament at z = 0.6 mm. Press into the label recess (0.1 mm clearance per side), a dab of glue if loose.",
      "stl": "/path/to/out/label-esp32.stl",
      "step": "/path/to/out/label-esp32.step"
    }
  ]
}
```

| Field | Commands | Meaning |
| --- | --- | --- |
| `ok` | all | `true` on success, `false` on bad input |
| `command`, `size` | `box`, `cap` | The command and the size as `NXxNYxH` or `NXxNY` |
| `outer_mm` | `box` | Outer width, depth and height (to the lip top), mm |
| `stack_pitch_mm` | `box` | `7 × H`: where the next part seats, mm |
| `cavity_mm` | `box` | Usable interior width, depth and height, mm |
| `compartments` | `box --dividers` | Rail positions, compartment sizes and rail height, mm |
| `label` | `--label` | Text, font size, tile size, embossed text height and filament swap height, mm |
| `name`, `out_dir` | `box`, `cap` | Output name and absolute output folder |
| `parts` | `box`, `cap` | One entry per distinct part: slug, title, copies to print, bounding box (mm), print notes, absolute STL and STEP paths |

Paths are absolute; `/path/to/out` above stands for the folder given with `--out`. Arrays are shown on one line; the CLI prints one value per line.

## Exit status and errors

| Status | When | Output |
| --- | --- | --- |
| 0 | Success | Text summary, or the JSON object with `--json` |
| 2 | Bad input | One line on stderr. With `--json`, also `{"ok": false, "error": "..."}` on stdout |
| 2 | Unknown option, missing argument, non-numeric `--lip-clearance` | argparse usage and error on stderr, no JSON |
| 1 | Unexpected error | Python traceback (please report it) |

Bad input is rejected before any file is written. Real error messages:

```text
stakee box: error: 2x2: expected NXxNYxH, e.g. 3x2x6 (42 mm units, 7 mm height units)
stakee box: error: 9x1x3: footprint must be <= 8 units per side
stakee box: error: 0x1x3: footprint must be >= 1 unit per side
stakee box: error: 2x2x1: height must be >= 2 units (use `stakee cap` for lids)
stakee box: error: 2x2x41: height must be <= 40 units
stakee box: error: --dividers 5x1: a 2-unit side has 3 divider slot(s) along X (every 21 mm), so at most 4 compartments; got 5
stakee box: error: --dividers 0x2: compartment counts must be >= 1
stakee box: error: --dividers 2: expected AxB, e.g. 2x3 (A across X, B along Y)
stakee box: error: --label: a 2-unit box has no front label recess; use height >= 3
stakee box: error: --label 'RASPBERRY PI': needs a 3.1 mm font to fit the 23.3 mm label area; minimum is 3.5 mm. Shorten the text or use a wider box.
stakee box: error: --label: text must not be empty
stakee box: error: --lip-clearance 1.5: must be >= 0.15 and < 1.0 mm
stakee box: error: --name 'bad name': use letters, digits, '.', '_' or '-' only
stakee cap: error: 2x2x3: expected NXxNY, e.g. 2x2 (42 mm units)
stakee cap: error: 9x9: footprint must be <= 8 units per side
```

With `--json`:

```text
stakee box: error: --dividers 5x1: a 2-unit side has 3 divider slot(s) along X (every 21 mm), so at most 4 compartments; got 5
{"ok": false, "error": "--dividers 5x1: a 2-unit side has 3 divider slot(s) along X (every 21 mm), so at most 4 compartments; got 5"}
```

The first line goes to stderr, the JSON to stdout.
