---
title: Downloads
description: Where the STL and STEP files live and how to get all of them at once.
editUrl: https://github.com/micovi/stakee/edit/main/site/src/content/docs/downloads.md
---

Every part has two files:

- **STL** for your slicer. Download it from the part's family page, or from GitHub.
- **STEP** for CAD (Fusion, FreeCAD, Onshape…), if you want to change a part. STEP files are only on GitHub.

Each family page lists its parts with both links, sizes, material and print notes. Start from the [model catalogue](../models/).

## Everything at once

- [Download the repository as a ZIP](https://github.com/micovi/stakee/archive/refs/heads/main.zip), or clone it:

  ```sh
  git clone https://github.com/micovi/stakee.git
  ```

- The files are in `models/<family>/stl/`, `models/<family>/step/` and `models/<family>/preview/` (SVG line drawings).

## Other sizes

Crates, caps, dividers and label tiles can be generated in any size with the `stakee` CLI. The [configurator](../configurator/) builds the command for you.
