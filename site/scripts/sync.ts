/**
 * Prebuild step: pull the generated model library and the hand-written docs into the site.
 *
 * - `../models/<family>/{stl,preview}/*` -> `public/models/...` (served at the same path)
 * - `../models/index.json` + manifests -> `src/generated/catalog.json`
 * - `../docs/*.md` -> `src/content/docs/docs/<slug>.md` + `src/generated/docs.json`
 *   (fails on any broken link)
 *
 * Everything written here is gitignored and rebuilt from scratch on every run. Only
 * `public/models/` is cleared, so hand-written files in `public/` (the favicon) stay.
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { Catalog, Family, Part } from '~/lib/catalog-types';
import { syncDocs } from '~/lib/docs-sync';
import { materialTags } from '~/lib/materials';
import { SITE_BASE } from '~/lib/repo';

const SITE = resolve(import.meta.dir, '..');
const REPO = resolve(SITE, '..');
const PUBLIC_MODELS = join(SITE, 'public', 'models');
const DOCS_OUT = join(SITE, 'src', 'content', 'docs', 'docs');
const GENERATED = join(SITE, 'src', 'generated');

type IndexFamily = {
  module: string;
  title: string;
  summary: string;
  description: string;
  manifest: string;
};

type ManifestPart = {
  slug: string;
  title: string;
  blurb: string;
  material: string;
  print_notes: string;
  color: string;
  footprint: string;
  size_mm: [number, number, number];
  files: { stl: string; step: string; svg: string };
};

function readJson(path: string, what: string): unknown {
  if (!existsSync(path)) {
    throw new Error(
      `sync: ${what} not found at ${path}. Generate the model library from the repo root ` +
        'with `uv run stakee-build`, then rerun.',
    );
  }
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    throw new Error(`sync: ${what} at ${path} is not valid JSON: ${String(error)}`);
  }
}

function requireFields(value: unknown, fields: readonly string[], where: string): void {
  if (typeof value !== 'object' || value === null) {
    throw new Error(`sync: ${where} is not an object`);
  }
  const missing = fields.filter((field) => !(field in value));
  if (missing.length > 0) {
    throw new Error(`sync: ${where} is missing ${missing.join(', ')}`);
  }
}

function readFamilies(): IndexFamily[] {
  const index = readJson(join(REPO, 'models', 'index.json'), 'models/index.json');
  requireFields(index, ['families'], 'models/index.json');
  const families = (index as { families: unknown }).families;
  if (!Array.isArray(families) || families.length === 0) {
    throw new Error('sync: models/index.json has no families');
  }
  families.forEach((family, i) => {
    requireFields(
      family,
      ['module', 'title', 'summary', 'description', 'manifest'],
      `models/index.json families[${i}]`,
    );
  });
  return families as IndexFamily[];
}

const PART_FIELDS = [
  'slug',
  'title',
  'blurb',
  'material',
  'print_notes',
  'color',
  'footprint',
  'size_mm',
  'files',
];

function readManifest(family: IndexFamily): ManifestPart[] {
  const manifest = readJson(join(REPO, family.manifest), family.manifest);
  requireFields(manifest, [], family.manifest);
  return Object.entries(manifest as Record<string, unknown>).map(([slug, part]) => {
    requireFields(part, PART_FIELDS, `${family.manifest} "${slug}"`);
    return part as ManifestPart;
  });
}

function copyRepoFile(repoPath: string): void {
  const source = join(REPO, repoPath);
  if (!existsSync(source)) {
    throw new Error(
      `sync: ${repoPath} is listed in a manifest but missing; rerun \`uv run stakee-build\``,
    );
  }
  const target = join(SITE, 'public', repoPath);
  mkdirSync(resolve(target, '..'), { recursive: true });
  copyFileSync(source, target);
}

function buildCatalog(): Catalog {
  const families: Family[] = [];
  const parts: Part[] = [];
  for (const family of readFamilies()) {
    const manifest = readManifest(family);
    for (const part of manifest) {
      copyRepoFile(part.files.stl);
      copyRepoFile(part.files.svg);
      const [x, y, z] = part.size_mm;
      parts.push({
        id: `${family.module}/${part.slug}`,
        slug: part.slug,
        module: family.module,
        family: family.title,
        order: parts.length,
        title: part.title,
        blurb: part.blurb,
        material: part.material,
        materials: materialTags(part.material),
        printNotes: part.print_notes,
        color: part.color,
        footprint: part.footprint,
        size: { x, y, z },
        files: part.files,
      });
    }
    families.push({
      module: family.module,
      title: family.title,
      summary: family.summary,
      description: family.description,
      parts: manifest.map((part) => part.slug),
    });
  }
  return { families, parts };
}

function main(): void {
  for (const dir of [PUBLIC_MODELS, DOCS_OUT, GENERATED]) {
    rmSync(dir, { recursive: true, force: true });
    mkdirSync(dir, { recursive: true });
  }
  const catalog = buildCatalog();
  writeFileSync(join(GENERATED, 'catalog.json'), `${JSON.stringify(catalog, null, 2)}\n`);
  const docs = syncDocs({
    docsDir: join(REPO, 'docs'),
    outDir: DOCS_OUT,
    base: SITE_BASE,
    repoPathExists: (repoPath) => existsSync(join(REPO, repoPath)),
  });
  writeFileSync(join(GENERATED, 'docs.json'), `${JSON.stringify(docs, null, 2)}\n`);
  console.log(
    `sync: ${catalog.parts.length} parts in ${catalog.families.length} families, ${docs.length} docs`,
  );
}

main();
