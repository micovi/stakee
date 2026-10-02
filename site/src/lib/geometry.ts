/**
 * Box geometry and CLI rules, ported from the Python generator.
 *
 * Source of truth: `stakee/core.py` (constants, `BoxSize`, `lip_pocket`, `label_width`,
 * `divider_slot_positions`) and `stakee/cli.py` (ranges, `parse_compartments`,
 * `rail_positions`, `compartment_sizes`, the `--label` height rule). Keep the two in step:
 * `geometry.test.ts` pins these formulas to numbers printed by the Python CLI.
 */

// stakee/core.py
export const GRID = 42.0;
export const HEIGHT_UNIT = 7.0;
export const GAP = 0.25;
export const WALL = 2.0;
export const FLOOR_Z = 5.5;
export const LIP_CLEARANCE = 0.25;
export const LIP_ABOVE_NOMINAL = 4.0;
export const SEAT_DEPTH = 4.0;
export const DIVIDER_THICKNESS = 1.2;
export const LABEL_HEIGHT = 12.0;
export const LABEL_MAX_WIDTH = 60.0;
export const LABEL_MIN_HEIGHT_UNITS = 3;
/** `FOOT_STATIONS[1][1] - WALL`: below this the cavity wall, not the lip, sets the play. */
export const LIP_CLEARANCE_MIN = 2.15 - WALL;

// stakee/cli.py
export const MAX_UNITS = 8;
export const MIN_HEIGHT = 2;
export const MAX_HEIGHT = 40;
export const LIP_CLEARANCE_RANGE = [0.0, 1.0] as const;
export const TILE_CLEARANCE = 0.1;
export const TILE_TEXT_MARGIN = 1.0;

export type Vec3 = { x: number; y: number; z: number };

/** Outer width of an `n`-unit side (`BoxSize.width` / `BoxSize.depth`). */
export function outerSpan(units: number): number {
  return units * GRID - 2 * GAP;
}

/** Height of the stacking lip top above the bed (`BoxSize.lip_top`). */
export function lipTop(h: number): number {
  return h * HEIGHT_UNIT + LIP_ABOVE_NOMINAL;
}

/** Outer size (width, depth, lip top) in mm, as `stakee box --json` reports `outer_mm`. */
export function outerSize(nx: number, ny: number, h: number): Vec3 {
  return { x: outerSpan(nx), y: outerSpan(ny), z: lipTop(h) };
}

/** Usable interior below the stacking seat (`BoxSize.cavity`). */
export function cavity(nx: number, ny: number, h: number): Vec3 {
  return {
    x: outerSpan(nx) - 2 * WALL,
    y: outerSpan(ny) - 2 * WALL,
    z: lipTop(h) - SEAT_DEPTH - FLOOR_Z,
  };
}

/** Front label recess width for a part of outer `width` (`label_width`). */
export function labelWidth(width: number): number {
  return Math.min(width - 16.0, LABEL_MAX_WIDTH);
}

/** Width available to the embossed text on a label tile (`make_front_label_tile`). */
export function labelTextWidth(width: number): number {
  return labelWidth(width) - 2 * TILE_CLEARANCE - 2 * TILE_TEXT_MARGIN;
}

/** Divider slot centers along an `n`-unit axis, every 21 mm (`divider_slot_positions`). */
export function dividerSlotPositions(n: number): number[] {
  const slots: number[] = [];
  for (let k = 1; k < 2 * n; k += 1) {
    slots.push((k * GRID) / 2 - (n * GRID) / 2);
  }
  return slots;
}

/**
 * `_nearest_slot` for the exact fraction `num / den`: round to the nearest slot index,
 * ties away from the center (`units`). Integer math keeps it exact like Python's Fraction.
 */
function nearestSlot(num: number, den: number, units: number): number {
  if (num >= units * den) {
    return Math.floor((2 * num + den) / (2 * den));
  }
  return Math.ceil((2 * num - den) / (2 * den));
}

/** Slot centers (mm) of the `compartments - 1` rails along a side (`rail_positions`). */
export function railPositions(units: number, compartments: number): number[] {
  const slots = dividerSlotPositions(units);
  const rails: number[] = [];
  for (let i = 1; i < compartments; i += 1) {
    const slot = slots[nearestSlot(i * 2 * units, compartments, units) - 1];
    if (slot === undefined) {
      throw new RangeError(`no divider slot for rail ${i} of ${compartments} on ${units} units`);
    }
    rails.push(slot);
  }
  return rails;
}

/**
 * Python's `round(value, 1)`. `toFixed` rounds the exact binary value like Python does;
 * they differ only on exact binary ties (e.g. 0.25), which these formulas never produce.
 */
function roundTo(value: number, digits: number): number {
  return Number(value.toFixed(digits));
}

/** Clear width of each compartment between walls and rail faces (`compartment_sizes`). */
export function compartmentSizes(span: number, rails: number[]): number[] {
  const edges = [-span / 2, ...rails, span / 2];
  const sizes: number[] = [];
  for (let i = 0; i < edges.length - 1; i += 1) {
    const left = edges[i] ?? 0;
    const right = edges[i + 1] ?? 0;
    const faces = (i > 0 ? 1 : 0) + (i < edges.length - 2 ? 1 : 0);
    sizes.push(roundTo(right - left - (DIVIDER_THICKNESS / 2) * faces, 1));
  }
  return sizes;
}

export type BoxOptions = {
  nx: number;
  ny: number;
  h: number;
  across: number;
  along: number;
  label: string;
  cap: boolean;
  noMagnets: boolean;
  noSockets: boolean;
  lipClearance: number;
};

export const DEFAULT_OPTIONS: BoxOptions = {
  nx: 2,
  ny: 2,
  h: 3,
  across: 1,
  along: 1,
  label: '',
  cap: false,
  noMagnets: false,
  noSockets: false,
  lipClearance: LIP_CLEARANCE,
};

/** `parse_box_size` / `_check_footprint`, with the CLI's messages. */
function sizeErrors(opts: BoxOptions): string[] {
  const tag = `${opts.nx}x${opts.ny}x${opts.h}`;
  if (![opts.nx, opts.ny, opts.h].every(Number.isInteger)) {
    return [`${tag}: expected NXxNYxH, e.g. 3x2x6 (42 mm units, 7 mm height units)`];
  }
  const errors: string[] = [];
  if (opts.nx < 1 || opts.ny < 1) {
    errors.push(`${tag}: footprint must be >= 1 unit per side`);
  } else if (opts.nx > MAX_UNITS || opts.ny > MAX_UNITS) {
    errors.push(`${tag}: footprint must be <= ${MAX_UNITS} units per side`);
  }
  if (opts.h < MIN_HEIGHT) {
    errors.push(`${tag}: height must be >= ${MIN_HEIGHT} units (use \`stakee cap\` for lids)`);
  } else if (opts.h > MAX_HEIGHT) {
    errors.push(`${tag}: height must be <= ${MAX_HEIGHT} units`);
  }
  return errors;
}

/** `parse_compartments`, with the CLI's messages. */
function compartmentErrors(opts: BoxOptions): string[] {
  const text = `${opts.across}x${opts.along}`;
  if (!Number.isInteger(opts.across) || !Number.isInteger(opts.along)) {
    return [`--dividers ${text}: expected AxB, e.g. 2x3 (A across X, B along Y)`];
  }
  if (opts.across < 1 || opts.along < 1) {
    return [`--dividers ${text}: compartment counts must be >= 1`];
  }
  const errors: string[] = [];
  const sides = [
    [opts.across, opts.nx, 'X'],
    [opts.along, opts.ny, 'Y'],
  ] as const;
  for (const [count, units, axis] of sides) {
    if (count > 2 * units) {
      errors.push(
        `--dividers ${text}: a ${units}-unit side has ${2 * units - 1} divider slot(s) ` +
          `along ${axis} (every 21 mm), so at most ${2 * units} compartments; got ${count}`,
      );
    }
  }
  return errors;
}

function lipClearanceErrors(value: number): string[] {
  const [low, high] = LIP_CLEARANCE_RANGE;
  if (!Number.isFinite(value) || value < low || value > high) {
    return [
      `--lip-clearance ${value}: must be between ${low.toFixed(1)} and ${high.toFixed(1)} mm`,
    ];
  }
  // The CLI range above is wider than what core.py's lip_pocket() accepts.
  if (value < LIP_CLEARANCE_MIN || value >= 1.0) {
    return [
      `lip clearance ${value} mm out of range: below ${LIP_CLEARANCE_MIN.toFixed(2)} mm the ` +
        'cavity wall, not the lip, sets the play; use 0.15-0.99 mm',
    ];
  }
  return [];
}

/** Every rule `stakee box` would reject these options for, as one-line messages. */
export function validate(opts: BoxOptions): string[] {
  const errors = sizeErrors(opts);
  if (errors.length === 0) {
    errors.push(...compartmentErrors(opts));
  }
  errors.push(...lipClearanceErrors(opts.lipClearance));
  if (opts.label.trim() !== '' && Number.isInteger(opts.h) && opts.h < LABEL_MIN_HEIGHT_UNITS) {
    errors.push(
      `--label: a ${opts.h}-unit box has no front label recess; ` +
        `use height >= ${LABEL_MIN_HEIGHT_UNITS}`,
    );
  }
  return errors;
}

/** Quote `text` for a POSIX shell. */
function shellQuote(text: string): string {
  if (/^[A-Za-z0-9._-]+$/.test(text)) {
    return text;
  }
  return `'${text.replaceAll("'", `'\\''`)}'`;
}

/** The `uv run stakee box ...` command for these options (defaults are left out). */
export function boxCommand(opts: BoxOptions): string {
  const parts = ['uv run stakee box', `${opts.nx}x${opts.ny}x${opts.h}`];
  if (opts.across !== 1 || opts.along !== 1) {
    parts.push(`--dividers ${opts.across}x${opts.along}`);
  }
  const label = opts.label.trim();
  if (label !== '') {
    parts.push(`--label ${shellQuote(label)}`);
  }
  if (opts.cap) {
    parts.push('--cap');
  }
  if (opts.noMagnets) {
    parts.push('--no-magnets');
  }
  if (opts.noSockets) {
    parts.push('--no-sockets');
  }
  if (opts.lipClearance !== LIP_CLEARANCE) {
    parts.push(`--lip-clearance ${opts.lipClearance}`);
  }
  return parts.join(' ');
}
