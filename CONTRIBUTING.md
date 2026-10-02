# Contributing

Thanks for helping. This page covers setup, the checks to run and the rules for pull requests.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone https://github.com/micovi/stakee.git
cd stakee
uv sync
```

uv installs Python 3.13 and the pinned dependencies, including `pytest` and `ruff`.

Optional: install the git hooks with [prek](https://github.com/j178/prek) so ruff runs on every commit:

```bash
prek install
```

## Checks

Run these before you open a pull request:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

If you changed geometry, the family's `verify()` must pass as part of the rebuild:

```bash
uv run stakee-build --only <family>
```

## Pull requests

- One logical change per pull request.
- When you change geometry, regenerate the models and commit them in the same pull request:
  - one family: `uv run stakee-build --only <family>`
  - `stakee/core.py`: `uv run stakee-build` (every family depends on it)
  - only docstrings or `stakee/families.py`: `uv run stakee-build --docs-only`
- Never hand-edit generated files: `models/README.md`, `models/index.json`, `models/<family>/README.md`, `manifest.json`, and the files under `stl/`, `step/` and `preview/`. Change the generator and rebuild instead.
- State every number from the code or a measured print. Do not document features that are not implemented.
- Describe what the change does in plain words.

## More

- [Building the library](docs/build.md): how `stakee-build` works.
- [Adding a family](docs/adding-a-family.md): a new generator module, step by step.
- [The system](docs/system.md): the geometry contract every part follows.

## License

No license has been chosen yet; see the [README](README.md#license).
