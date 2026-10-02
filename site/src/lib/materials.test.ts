import { expect, test } from 'vitest';
import { materialTags } from '~/lib/materials';

test.each([
  ['PLA or PETG', ['PLA', 'PETG']],
  ['PETG (PLA is too brittle for the hooks and detent finger)', ['PETG']],
  ['PLA (rails) · PETG (hook plates and bridges, the hooks flex better)', ['PLA', 'PETG']],
  ['PETG or ASA (it lives next to the iron); never rest the hot tip on any print', ['PETG', 'ASA']],
  ['PETG (TPU 95A for a softer, rattle-free rack)', ['PETG']],
  [
    'Static-dissipative filament (PETG-ESD / ABS-ESD sold as 1e6-1e9 ohm). Conductive PLA also ' +
      'works. Plain PLA/PETG is an insulator and does nothing here.',
    ['ESD'],
  ],
  ['PETG-ESD', ['ESD']],
  ['The filament you will print the crates in', ['Other']],
  ['', ['Other']],
])('%s', (material, tags) => {
  expect(materialTags(material)).toEqual(tags);
});
