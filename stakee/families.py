"""The model families: one generator module in ``stakee/modules`` and one folder in ``models``."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Family:
    """One model family.

    Attributes:
        module: module name in ``stakee.modules`` and folder name in ``models/``.
        title: human name.
        summary: one sentence: what it is and why you would print it.
    """

    module: str
    title: str
    summary: str


FAMILIES: tuple[Family, ...] = (
    Family(
        "crates",
        "Crates",
        "Stackable crates and caps from 1x1 to 3x2 grid units: the base every other part fits.",
    ),
    Family(
        "dividers",
        "Dividers",
        "Interlocking X/Y rails, hook-on plates and bridges that split a crate; all print flat.",
    ),
    Family(
        "inserts",
        "Inserts",
        "Drop-in trays that turn a crate into a kit: dev-board dock, solder station, parts grid.",
    ),
    Family(
        "baglib",
        "Bag Library",
        "A tall crate that files distributor zip bags upright like a card index, with tab cards.",
    ),
    Family(
        "drawers",
        "Drawer cabinet",
        "Stackable sleeves with an open front and the drawers that slide into them.",
    ),
    Family(
        "pocket",
        "Pocket box",
        "A small hinged, latched box to carry around that still stacks like a crate.",
    ),
    Family(
        "kit",
        "Carry kit",
        "Stack clip, tote handle cap, NFC label cap and tool-rack cap for a grab-and-go stack.",
    ),
    Family(
        "magtray",
        "Magnetic tray",
        "A stackable screw tray with hidden magnets and one numbered compartment per step.",
    ),
    Family(
        "esd",
        "ESD crates",
        "Crates with a ground point (banana socket or snap stud) for dissipative filament.",
    ),
    Family(
        "wirespool",
        "Wire dispenser",
        "A crate with a lift-out axle and one eyelet per spool for hookup wire.",
    ),
    Family(
        "wallrail",
        "Wall rail",
        "A French cleat and shelves that hang crates on the wall above the bench.",
    ),
    Family(
        "calibration",
        "Calibration",
        "Small test prints that pick the lip clearance and divider fit for your printer.",
    ),
)

MODULES: tuple[str, ...] = tuple(family.module for family in FAMILIES)


def family(module: str) -> Family:
    """The family for ``module``; raises KeyError listing the known names."""
    for item in FAMILIES:
        if item.module == module:
            return item
    raise KeyError(f"unknown family {module!r}; known: {', '.join(MODULES)}")
