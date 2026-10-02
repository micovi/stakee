# Stakee site

The docs site at <https://micovi.github.io/stakee/>: Astro + Starlight, built with Bun.
It is generated from the repo's `models/` (model library) and `docs/` (hand-written docs);
no Python is needed to build it.

```sh
bun install
bun run dev       # local dev server at http://localhost:4321/stakee/
bun run build     # static site in dist/
bun run preview   # serve dist/
bun run check     # astro check + biome + tsc, zero warnings expected
bun run test      # vitest
```

`dev`, `build` and `check` first run `bun run sync` (`scripts/sync.ts`), which:

- copies `../models/<family>/stl/*.stl` and `../models/<family>/preview/*.svg` to
  `public/models/` (STEP files stay on GitHub and are linked from the family pages);
- writes `src/generated/catalog.json` from `../models/index.json` and the family manifests;
- converts `../docs/*.md` into Starlight pages in `src/content/docs/docs/`: the `# H1` becomes
  the title, the first paragraph the description, and repo-relative links are rewritten to site
  pages or GitHub URLs. Set `STAKEE_DOCS_DIR` to read docs from another folder.

`public/models/`, `src/generated/` and `src/content/docs/docs/` are generated and gitignored.
If `models/index.json` is missing, run `uv run stakee-build` from the repo root first.

The configurator's formulas live in `src/lib/geometry.ts`, ported from `stakee/core.py` and
`stakee/cli.py`; `src/lib/geometry.test.ts` pins them to numbers printed by the Python CLI.
Pushes to `main` deploy through `.github/workflows/site.yml`.
