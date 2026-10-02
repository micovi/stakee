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
  pages or GitHub URLs. Links must be relative to `docs/` and point at files that exist; any
  broken link fails the sync.

`public/models/`, `src/generated/` and `src/content/docs/docs/` are generated and gitignored.
If `models/index.json` is missing, run `uv run stakee-build` from the repo root first.

The configurator's formulas live in `src/lib/geometry.ts`, ported from `stakee/core.py` and
`stakee/cli.py`. `src/lib/geometry.test.ts` checks them against `src/lib/geometry.fixture.json`,
which the Python test `tests/test_site_fixture.py` computes from the generator and fails on
drift. After a change to the Python formulas, regenerate it from the repo root with
`STAKEE_UPDATE_FIXTURES=1 uv run pytest tests/test_site_fixture.py`, then fix `geometry.ts`
until `bun run test` passes.

`.github/workflows/site.yml` checks, tests and builds every pull request; pushes to `main`
also deploy to GitHub Pages.
