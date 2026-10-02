"""Rebuild the model library in ``models/`` and its wiki pages.

Usage::

    uv run stakee-build                      # every family
    uv run stakee-build --only crates,kit    # some families
    uv run stakee-build --docs-only          # only rewrite the README pages

Each family's ``verify()`` runs first and must pass; a family that fails exports nothing
and the build stops. A rebuilt family's folder is emptied first, so it lists only what the
generator exports now.
"""

import argparse
import importlib
import shutil

from stakee.docs import write_docs
from stakee.export import MODELS
from stakee.families import MODULES

GENERATED_DIRS = ("stl", "step", "preview")


def parse_only(text: str | None) -> list[str]:
    """Families named by ``--only`` (all when ``text`` is None), in catalogue order."""
    if text is None:
        return list(MODULES)
    selected = [name.strip() for name in text.split(",") if name.strip()]
    unknown = sorted(set(selected) - set(MODULES))
    if unknown or not selected:
        raise SystemExit(f"--only {text!r}: unknown family {unknown}; known: {', '.join(MODULES)}")
    return [name for name in MODULES if name in selected]


def clear_family(module: str) -> None:
    folder = MODELS / module
    for name in GENERATED_DIRS:
        shutil.rmtree(folder / name, ignore_errors=True)
    (folder / "manifest.json").unlink(missing_ok=True)


def build_family(module: str) -> None:
    code = importlib.import_module(f"stakee.modules.{module}")
    if not callable(getattr(code, "verify", None)) or not callable(getattr(code, "build", None)):
        raise SystemExit(f"{module}: needs verify() and build(); every family proves its parts")
    print(f"verifying {module}…", flush=True)
    if code.verify() is not True:
        raise SystemExit(f"{module}: verify() failed, nothing exported (see FAIL lines above)")
    print(f"building {module}…", flush=True)
    clear_family(module)
    code.build()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stakee-build", description=__doc__.split("\n")[0])
    parser.add_argument("--only", metavar="A,B", help="comma-separated families (default: all)")
    parser.add_argument("--docs-only", action="store_true", help="only rewrite README pages")
    args = parser.parse_args(argv)
    if not args.docs_only:
        for module in parse_only(args.only):
            build_family(module)
    for page in write_docs():
        print(f"wrote {page.relative_to(MODELS.parent)}")


if __name__ == "__main__":
    main()
