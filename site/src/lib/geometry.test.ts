import { describe, expect, test } from 'vitest';
import {
  boxCommand,
  cavity,
  compartmentSizes,
  DEFAULT_OPTIONS,
  labelTextWidth,
  labelTileCount,
  outerSize,
  railPositions,
  stackPitch,
  validate,
} from '~/lib/geometry';
import fixture from '~/lib/geometry.fixture.json';

// geometry.fixture.json is computed from stakee/core.py and stakee/cli.py by
// tests/test_site_fixture.py, which fails when the Python side changes without it.
// The error strings below were printed by `uv run stakee box ... --json` ("error").

describe('matches the Python generator (geometry.fixture.json)', () => {
  test.each(fixture.boxes)('box $size', (entry) => {
    const [nx = 0, ny = 0, h = 0] = entry.size;
    const outer = outerSize(nx, ny, h);
    const inner = cavity(nx, ny, h);
    expect([outer.x, outer.y, outer.z]).toEqual(entry.outer_mm);
    expect([inner.x, inner.y, inner.z]).toEqual(entry.cavity_mm);
    expect(stackPitch(h)).toBe(entry.stack_pitch_mm);
    expect(labelTextWidth(outer.x)).toBe(entry.label_text_width_mm);
  });

  test.each(fixture.dividers)('$compartments compartments on $units units', (entry) => {
    expect(cavity(entry.units, entry.units, 3).x).toBe(entry.span_mm);
    const rails = railPositions(entry.units, entry.compartments);
    expect(rails).toEqual(entry.rails_mm);
    expect(compartmentSizes(entry.span_mm, rails)).toEqual(entry.sizes_mm);
  });

  test('covers every footprint size and compartment count', () => {
    expect(new Set(fixture.dividers.map((entry) => entry.units)).size).toBe(8);
    expect(fixture.boxes.length).toBeGreaterThan(0);
  });
});

describe('validate', () => {
  test('defaults are valid', () => {
    expect(validate(DEFAULT_OPTIONS)).toEqual([]);
  });

  test.each([
    [{ h: 2, label: 'X' }, '--label: a 2-unit box has no front label recess; use height >= 3'],
    [
      { nx: 2, ny: 2, h: 4, across: 5 },
      '--dividers 5x1: a 2-unit side has 3 divider slot(s) along X (every 21 mm), ' +
        'so at most 4 compartments; got 5',
    ],
    [{ lipClearance: 1.5 }, '--lip-clearance 1.5: must be >= 0.15 and < 1.0 mm'],
    [{ lipClearance: 1 }, '--lip-clearance 1: must be >= 0.15 and < 1.0 mm'],
    [{ lipClearance: 0.1 }, '--lip-clearance 0.1: must be >= 0.15 and < 1.0 mm'],
    [{ nx: 9, ny: 2, h: 4 }, '9x2x4: footprint must be <= 8 units per side'],
    [{ nx: 2, ny: 2, h: 41 }, '2x2x41: height must be <= 40 units'],
  ])('rejects %o like the CLI', (overrides, message) => {
    expect(validate({ ...DEFAULT_OPTIONS, ...overrides })).toEqual([message]);
  });

  test('dividers fit on both axes up to 2 per unit', () => {
    expect(validate({ ...DEFAULT_OPTIONS, nx: 3, ny: 2, across: 6, along: 4 })).toEqual([]);
    expect(validate({ ...DEFAULT_OPTIONS, nx: 3, ny: 2, across: 6, along: 5 })).toHaveLength(1);
  });

  test('height 1 points at caps', () => {
    expect(validate({ ...DEFAULT_OPTIONS, h: 1 })).toEqual([
      '2x2x1: height must be >= 2 units (use `stakee cap` for lids)',
    ]);
  });

  test('lip clearance below what core.py accepts', () => {
    expect(validate({ ...DEFAULT_OPTIONS, lipClearance: 0.1 })).toHaveLength(1);
    expect(validate({ ...DEFAULT_OPTIONS, lipClearance: 0.15 })).toEqual([]);
  });

  test('fractional sizes are rejected', () => {
    expect(validate({ ...DEFAULT_OPTIONS, nx: 1.5 })).toHaveLength(1);
  });

  test('empty number fields are named, without NaN', () => {
    const errors = validate({ ...DEFAULT_OPTIONS, nx: Number.NaN, along: Number.NaN });
    expect(errors).toEqual(['Enter a number for NX, B']);
    expect(
      validate({ ...DEFAULT_OPTIONS, lipClearance: Number.NaN, label: 'X', h: Number.NaN }),
    ).toEqual(['Enter a number for H, lip clearance']);
  });
});

describe('labelTileCount', () => {
  test('one tile for the crate, a second for the cap', () => {
    expect(labelTileCount(false)).toBe(1);
    expect(labelTileCount(true)).toBe(2);
  });
});

describe('boxCommand', () => {
  test('defaults give the bare command', () => {
    expect(boxCommand(DEFAULT_OPTIONS)).toBe('uv run stakee box 2x2x3');
  });

  test('every option', () => {
    const command = boxCommand({
      nx: 3,
      ny: 2,
      h: 6,
      across: 2,
      along: 3,
      label: "Bob's ESP32",
      cap: true,
      noMagnets: true,
      noSockets: true,
      lipClearance: 0.3,
    });
    expect(command).toBe(
      "uv run stakee box 3x2x6 --dividers 2x3 --label='Bob'\\''s ESP32' --cap --no-magnets " +
        '--no-sockets --lip-clearance 0.3',
    );
  });

  test.each([
    [' ESP32 ', '--label=ESP32'],
    ['-VCC', '--label=-VCC'],
    ['--cap', '--label=--cap'],
    ['GND -VCC', "--label='GND -VCC'"],
    ['$HOME `id`', "--label='$HOME `id`'"],
    ['say "hi"', `--label='say "hi"'`],
    ["it's", "--label='it'\\''s'"],
  ])('label %j is one shell word: %s', (label, flag) => {
    expect(boxCommand({ ...DEFAULT_OPTIONS, label })).toBe(`uv run stakee box 2x2x3 ${flag}`);
  });
});
