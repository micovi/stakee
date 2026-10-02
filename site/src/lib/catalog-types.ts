/** Shapes of the files `scripts/sync.ts` writes to `src/generated/`. */

export type Size = { x: number; y: number; z: number };

export type PartFiles = {
  /** Repo-relative paths; `stl` and `svg` are also served by the site at the same path. */
  stl: string;
  step: string;
  svg: string;
};

export type Part = {
  /** `<module>/<slug>`: slugs are only unique within a family. */
  id: string;
  slug: string;
  module: string;
  family: string;
  /** Position in the catalogue (family order, then manifest order). */
  order: number;
  title: string;
  blurb: string;
  material: string;
  /** Filament tags derived from `material`, see `materialTags`. */
  materials: string[];
  printNotes: string;
  color: string;
  footprint: string;
  size: Size;
  files: PartFiles;
};

export type Family = {
  module: string;
  title: string;
  summary: string;
  /** Markdown, from the family module docstring. */
  description: string;
  parts: string[];
};

export type Catalog = {
  families: Family[];
  parts: Part[];
};

export type DocEntry = {
  slug: string;
  title: string;
};
