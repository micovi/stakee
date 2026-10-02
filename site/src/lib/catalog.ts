import catalogJson from '~/generated/catalog.json';
import type { Catalog, Family, Part, Size } from '~/lib/catalog-types';
import { sitePath } from '~/lib/repo';

export const catalog: Catalog = catalogJson;

export function partsOf(family: Family): Part[] {
  return catalog.parts.filter((part) => part.module === family.module);
}

/** `125.5 × 83.5 × 46 mm`. */
export function formatSize(size: Size): string {
  const mm = (value: number): string => String(Number(value.toFixed(1)));
  return `${mm(size.x)} × ${mm(size.y)} × ${mm(size.z)} mm`;
}

/** Site URL of a repo file the sync step copied into `public/` (STL, SVG preview). */
export function assetUrl(repoPath: string): string {
  return sitePath(import.meta.env.BASE_URL, repoPath);
}

export function familyUrl(module: string): string {
  return sitePath(import.meta.env.BASE_URL, `models/${module}/`);
}

/** All filament tags in use, most common first. */
export function materialOptions(): string[] {
  const counts = new Map<string, number>();
  for (const part of catalog.parts) {
    for (const tag of part.materials) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([tag]) => tag);
}
