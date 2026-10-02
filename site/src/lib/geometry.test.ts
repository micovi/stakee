import { describe, expect, test } from 'vitest';
import {
  boxCommand,
  cavity,
  compartmentSizes,
  DEFAULT_OPTIONS,
  outerSize,
  railPositions,
  validate,
} from '~/lib/geometry';

// Expected numbers below were printed by the Python generator on 2026-10-02:
//   uv run stakee list --json                     -> "examples" (cavity W, D, H)
//   uv run stakee box 3x2x6 --dividers 3x3 --json -> outer_mm, cavity_mm, compartments
//   uv run stakee box 4x1x2 --dividers 3x2 --json -> outer_mm, cavity_mm, compartments
//   uv run stakee box 3x2x2 --dividers 4x1 --json -> outer_mm, cavity_mm, compartments
//   error strings: `uv run stakee box ... --json` -> "error"
// If core.py or cli.py change, re-run those commands and update both this file and geometry.ts.

const LIST_EXAMPLES: [string, [number, number, number]][] = [
  ['1x1x3', [37.5, 37.5, 15.5]],
  ['2x1x3', [79.5, 37.5, 15.5]],
  ['2x2x3', [79.5, 79.5, 15.5]],
  ['2x2x6', [79.5, 79.5, 36.5]],
  ['3x2x6', [121.5, 79.5, 36.5]],
  ['4x2x6', [163.5, 79.5, 36.5]],
];

function parseTag(tag: string): [number, number, number] {
  const [nx = 0, ny = 0, h = 0] = tag.split('x').map(Number);
  return [nx, ny, h];
}

describe('cavity', () => {
  test.each(LIST_EXAMPLES)('%s matches `stakee list`', (tag, expected) => {
    const c = cavity(...parseTag(tag));
    expect([c.x, c.y, c.z]).toEqual(expected);
  });
});

describe('box summary', () => {
  test('3x2x6 with 3x3 dividers', () => {
    const outer = outerSize(3, 2, 6);
    const inner = cavity(3, 2, 6);
    expect([outer.x, outer.y, outer.z]).toEqual([125.5, 83.5, 46.0]);
    expect([inner.x, inner.y, inner.z]).toEqual([121.5, 79.5, 36.5]);
    const yRails = railPositions(3, 3);
    const xRails = railPositions(2, 3);
    expect(yRails).toEqual([-21.0, 21.0]);
    expect(xRails).toEqual([-21.0, 21.0]);
    expect(compartmentSizes(inner.x, yRails)).toEqual([39.1, 40.8, 39.1]);
    expect(compartmentSizes(inner.y, xRails)).toEqual([18.1, 40.8, 18.1]);
  });

  test('4x1x2 with 3x2 dividers', () => {
    const outer = outerSize(4, 1, 2);
    const inner = cavity(4, 1, 2);
    expect([outer.x, outer.y, outer.z]).toEqual([167.5, 41.5, 18.0]);
    expect([inner.x, inner.y, inner.z]).toEqual([163.5, 37.5, 8.5]);
    const yRails = railPositions(4, 3);
    const xRails = railPositions(1, 2);
    expect(yRails).toEqual([-21.0, 21.0]);
    expect(xRails).toEqual([0.0]);
    expect(compartmentSizes(inner.x, yRails)).toEqual([60.1, 40.8, 60.1]);
    expect(compartmentSizes(inner.y, xRails)).toEqual([18.1, 18.1]);
  });

  test('3x2x2 with 4x1 dividers rounds slot ties away from the center', () => {
    const outer = outerSize(3, 2, 2);
    const inner = cavity(3, 2, 2);
    expect([outer.x, outer.y, outer.z]).toEqual([125.5, 83.5, 18.0]);
    expect([inner.x, inner.y, inner.z]).toEqual([121.5, 79.5, 8.5]);
    const yRails = railPositions(3, 4);
    expect(yRails).toEqual([-42.0, 0.0, 42.0]);
    expect(compartmentSizes(inner.x, yRails)).toEqual([18.1, 40.8, 40.8, 18.1]);
    expect(compartmentSizes(inner.y, railPositions(2, 1))).toEqual([79.5]);
  });

  test('one compartment is the whole cavity', () => {
    expect(railPositions(2, 1)).toEqual([]);
    expect(compartmentSizes(79.5, [])).toEqual([79.5]);
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
      "uv run stakee box 3x2x6 --dividers 2x3 --label 'Bob'\\''s ESP32' --cap --no-magnets " +
        '--no-sockets --lip-clearance 0.3',
    );
  });

  test('simple labels are not quoted', () => {
    expect(boxCommand({ ...DEFAULT_OPTIONS, label: ' ESP32 ' })).toBe(
      'uv run stakee box 2x2x3 --label ESP32',
    );
  });
});
