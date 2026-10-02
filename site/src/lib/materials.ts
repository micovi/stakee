const FILAMENTS = ['PLA', 'PETG', 'ASA', 'TPU', 'ABS'] as const;

export const OTHER_MATERIAL = 'Other';
export const ESD_MATERIAL = 'ESD';

/**
 * Filament tags for a free-text manifest `material`, for the catalogue filter.
 *
 * Only the first sentence outside parentheses counts: asides like "PETG (PLA is too
 * brittle)" or "Plain PLA/PETG does nothing here" name filaments that are *not* recommended.
 * Static-dissipative material is tagged `ESD`; text naming no filament is tagged `Other`.
 */
export function materialTags(material: string): string[] {
  const firstSentence = material.replace(/\([^)]*\)/g, ' ').split(/\.\s/)[0] ?? '';
  const tags: string[] = [];
  if (/ESD|dissipative/i.test(firstSentence)) {
    tags.push(ESD_MATERIAL);
  }
  for (const filament of FILAMENTS) {
    if (new RegExp(`\\b${filament}\\b(?!-ESD)`).test(firstSentence)) {
      tags.push(filament);
    }
  }
  return tags.length > 0 ? tags : [OTHER_MATERIAL];
}
