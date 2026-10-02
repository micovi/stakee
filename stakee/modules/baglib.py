"""Bag Library: file distributor zip bags upright like a card index, labels facing up and out.

A tall crate sized from ``BoxSize.cavity`` so a bag stands on its short edge and still clears
a cap, a thumb window in the front wall below the label/seat band, slot-keyed index cards with
staggered embossed tabs, and a sliding follower that props up a half-empty row.
"""

from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    Box,
    Cylinder,
    FontStyle,
    Part,
    Plane,
    Polygon,
    Pos,
    Rot,
    Text,
    extrude,
    fillet,
)

from stakee.core import (
    DIVIDER_SLOT_DEPTH,
    DIVIDER_THICKNESS,
    FLOOR_Z,
    HEIGHT_UNIT,
    LABEL_HEIGHT,
    WALL,
    BoxSize,
    divider_slot_positions,
    label_z,
    make_box,
    make_cap,
)
from stakee.export import PartInfo, save

MODULE = "baglib"

BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)

BAG_SIDE_MARGIN = 4.0  # min clearance per side between a bag edge and the inner wall
TAB_REVEAL = 10.0  # min height of index tab left visible above the bag tops

CARD_SLOT_CLEARANCE = 0.2  # card edge to the bottom of the 0.8 mm wall slot
CARD_TOP_CLEARANCE = 0.6  # tab top stays this far below the seat plane 7 * h
TAB_HEIGHT = 16.0
TAB_GAP = 1.0  # between neighbouring tab positions
TAB_SIDE_MARGIN = 2.0  # tabs stay inside the cavity, clear of the wall slots
TAB_RADIUS = 3.0
TAB_FONT = 7.0
TEXT_EMBOSS = 0.4
CATEGORIES = ("RES", "CAP", "IC", "MCU", "CONN", "LED", "PWR", "MISC")

WINDOW_WIDTH = 30.0
WINDOW_BOTTOM = 30.0  # local z; keeps a solid band at the floor to hold bag bottoms in
WINDOW_LABEL_GAP = 3.0  # solid wall between the window top and the label recess

FOLLOWER_HEIGHT = 70.0
FOLLOWER_BASE = 45.0
FOLLOWER_SKIN = 3.0  # front plate, base plate and rib thickness
FOLLOWER_SIDE_CLEARANCE = 0.5


@dataclass(frozen=True)
class Shelf:
    """One Bag Library variant: the bag it files (width x height as filed) and crate depth."""

    tag: str
    bag_w: float
    bag_h: float
    ny: int

    @property
    def size(self) -> BoxSize:
        nx = 1
        while BoxSize(nx, self.ny, 2).cavity[0] < self.bag_w + 2 * BAG_SIDE_MARGIN:
            nx += 1
        h = 2
        while BoxSize(nx, self.ny, h).cavity[2] < self.bag_h + TAB_REVEAL:
            h += 1
        return BoxSize(nx, self.ny, h)


SHELVES = (
    Shelf("70x100", bag_w=70.0, bag_h=100.0, ny=4),
    Shelf("100x150", bag_w=150.0, bag_h=100.0, ny=3),
)


def window_top(size: BoxSize) -> float:
    """Local z of the thumb window top: below the label recess and the stacking seat band."""
    label_bottom = label_z(size) - LABEL_HEIGHT / 2
    return label_bottom - WINDOW_LABEL_GAP


def _front_window(size: BoxSize) -> Part:
    radius = WINDOW_WIDTH / 2
    top = window_top(size)
    y = -size.depth / 2 + WALL / 2
    straight = top - WINDOW_BOTTOM - WINDOW_WIDTH
    cut = Pos(0, y, (top + WINDOW_BOTTOM) / 2) * Box(WINDOW_WIDTH, WALL + 2, straight)
    for z in (WINDOW_BOTTOM + radius, top - radius):
        cut += Pos(0, y, z) * Rot(90, 0, 0) * Cylinder(radius, WALL + 2)
    return cut


def make_crate(size: BoxSize) -> Part:
    """A core box with a stadium thumb window in the front wall.

    The window stops below the label recess, so the wall band and lip that the upper box
    seats on are untouched.

    Args:
        size: crate size; the window needs ``window_top(size) > WINDOW_BOTTOM + WINDOW_WIDTH``.
    """
    if window_top(size) <= WINDOW_BOTTOM + WINDOW_WIDTH:
        raise ValueError(f"crate h={size.h} too short for the thumb window; use h >= 9")
    return make_box(size) - _front_window(size)


def card_width(size: BoxSize) -> float:
    """Card width that keys 0.6 mm into the core wall slots on both sides."""
    return size.cavity[0] + 2 * (DIVIDER_SLOT_DEPTH - CARD_SLOT_CLEARANCE)


def _tab_text(label: str, max_width: float):
    text = Text(label, font_size=TAB_FONT, font_style=FontStyle.BOLD)
    width = text.bounding_box().size.X
    if width > max_width:
        text = Text(label, font_size=TAB_FONT * max_width / width, font_style=FontStyle.BOLD)
    return text


def make_card(size: BoxSize, index: int) -> Part:
    """Index divider card for ``CATEGORIES[index]``, standing on the floor at local z = 0.

    The card plane is XZ, front face (-Y) carries the embossed tab text. Tabs step through
    ``nx + 1`` positions left to right so consecutive cards never hide each other.

    Args:
        size: crate the card is for.
        index: category index; also picks the tab position.
    """
    cav_w, _, cav_h = size.cavity
    total_h = cav_h - CARD_TOP_CLEARANCE
    body_h = total_h - TAB_HEIGHT
    positions = size.nx + 1
    pitch = (cav_w - 2 * TAB_SIDE_MARGIN) / positions
    tab_w = pitch - TAB_GAP
    tab_x = -cav_w / 2 + TAB_SIDE_MARGIN + pitch * (index % positions + 0.5)

    card = Box(card_width(size), DIVIDER_THICKNESS, body_h, align=BOTTOM)
    card += Pos(tab_x, 0, body_h - 1) * Box(tab_w, DIVIDER_THICKNESS, TAB_HEIGHT + 1, align=BOTTOM)
    tab_corners = card.edges().filter_by(Axis.Y).group_by(Axis.Z)[-1]
    card = fillet(tab_corners, TAB_RADIUS)

    text = _tab_text(CATEGORIES[index], tab_w - 3.0)
    text_z = total_h - TAB_HEIGHT / 2 + 1.0
    face_y = -DIVIDER_THICKNESS / 2 + 0.01
    card += extrude(Pos(tab_x, face_y, text_z) * (Plane.XZ * text), amount=TEXT_EMBOSS + 0.01)
    return card


def make_follower(size: BoxSize) -> Part:
    """Ribbed L-wedge that slides on the floor behind the last bag and props the row upright.

    Front plate faces -Y. Printed as modelled (base on the bed), every wall is vertical.

    Args:
        size: crate the follower is for; width = cavity width - 2 * clearance.
    """
    width = size.cavity[0] - 2 * FOLLOWER_SIDE_CLEARANCE
    front = Box(width, FOLLOWER_SKIN, FOLLOWER_HEIGHT, align=(Align.CENTER, Align.MIN, Align.MIN))
    base = Box(width, FOLLOWER_BASE, FOLLOWER_SKIN, align=(Align.CENTER, Align.MIN, Align.MIN))
    rib_profile = Plane.YZ * Polygon(
        (0, 0), (FOLLOWER_BASE, 0), (FOLLOWER_SKIN, FOLLOWER_HEIGHT), (0, FOLLOWER_HEIGHT)
    )
    rib = extrude(rib_profile, amount=FOLLOWER_SKIN / 2, both=True)
    follower = front + base
    ribs = size.nx + 1
    span = width - FOLLOWER_SKIN
    for i in range(ribs):
        follower += Pos(-span / 2 + span * i / (ribs - 1), 0, 0) * rib
    return Pos(0, -FOLLOWER_BASE / 2, 0) * follower


def _lay_flat(card: Part) -> Part:
    flat = Rot(-90, 0, 0) * card
    box = flat.bounding_box()
    return Pos(-box.center().X, -box.center().Y, -box.min.Z) * flat


def _crate_info(shelf: Shelf, size: BoxSize, tag: str) -> PartInfo:
    cav_w, cav_d, cav_h = size.cavity
    return PartInfo(
        slug=f"crate-{tag}",
        title=f"Bag Library crate {tag}",
        blurb=(
            f"Files {shelf.bag_w:.0f}x{shelf.bag_h:.0f} mm component bags upright like a card "
            f"index (cavity {cav_w:.0f}x{cav_d:.0f}x{cav_h:.0f} mm, still cappable and "
            "stackable). Thumb window in front, index cards key into the side-wall slots."
        ),
        material="PETG (PETG-ESD if you also keep unbagged ICs in it)",
        print_notes=(
            "Upright, no supports (window arch bridges fine), 3 walls, 15% infill. "
            "Optional 6x2 mm magnets."
        ),
        color="#7fb3a6",
        footprint=tag,
    )


def _save_shelf(shelf: Shelf) -> None:
    size = shelf.size
    tag = f"{size.nx}x{size.ny}x{size.h}"
    save(MODULE, make_crate(size), _crate_info(shelf, size, tag))
    save(
        MODULE,
        make_cap(size.nx, size.ny),
        PartInfo(
            slug=f"cap-{size.nx}x{size.ny}",
            title=f"Cap {size.nx}x{size.ny}",
            blurb="Lid for the Bag Library crate; seats in the stacking lip, label on top.",
            material="PETG",
            print_notes="Upside down (plate on the bed), no supports.",
            color="#f2a03d",
            footprint=f"{size.nx}x{size.ny}",
        ),
    )
    for index, label in enumerate(CATEGORIES):
        save(
            MODULE,
            _lay_flat(make_card(size, index)),
            PartInfo(
                slug=f"card-{size.nx}x-{label.lower()}",
                title=f"Index card {label} ({size.nx}-wide)",
                blurb=(
                    f"Divider card with an embossed {label} tab; drops into any side-wall slot "
                    f"of the {tag} crate. Tabs are staggered across {size.nx + 1} positions."
                ),
                material="PLA or PETG (contrasting colour swap at the text layer)",
                print_notes=(
                    "Flat, text up, no supports, 100% infill. Pause/colour change at "
                    f"{DIVIDER_THICKNESS:.1f} mm makes the text pop."
                ),
                color="#e8d44d",
            ),
        )
    save(
        MODULE,
        make_follower(size),
        PartInfo(
            slug=f"follower-{size.nx}x",
            title=f"Bag follower ({size.nx}-wide)",
            blurb=(
                "Ribbed wedge that slides behind the last bag so a half-empty row stays upright; "
                "lift it out by the top of the front plate."
            ),
            material="PETG",
            print_notes=(
                "As modelled (base plate on the bed), no supports, 20% infill. Drop a few "
                "washers between the ribs if it needs more weight."
            ),
            color="#c45b4a",
        ),
    )


def build() -> None:
    """Export every Bag Library part into models/baglib/."""
    for shelf in SHELVES:
        _save_shelf(shelf)


def _overlap(a: Part, b: Part) -> float:
    common = a & b
    return sum(solid.volume for solid in common.solids())


def _verify_shelf(shelf: Shelf) -> list[tuple[str, bool, str]]:
    size = shelf.size
    seat = size.h * HEIGHT_UNIT
    crate = make_crate(size)
    cap = Pos(0, 0, seat) * make_cap(size.nx, size.ny)
    upper = make_box(BoxSize(size.nx, size.ny, 3))
    slots = divider_slot_positions(size.ny)
    bag_y = (slots[0] + slots[1]) / 2
    bag = Pos(0, bag_y, FLOOR_Z + 0.05) * Box(shelf.bag_w, 0.3, shelf.bag_h, align=BOTTOM)
    follower = Pos(0, slots[-1] - FOLLOWER_BASE / 2, FLOOR_Z) * make_follower(size)
    band = Pos(0, 0, window_top(size) + 0.5) * Box(500, 500, 100, align=BOTTOM)

    results = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((f"{shelf.tag} {name}", ok, detail))

    def no_overlap(name: str, a: Part, b: Part) -> None:
        volume = _overlap(a, b)
        check(name, volume < 1e-3, f"overlap {volume:.4f} mm3")

    check("crate valid", crate.is_valid, f"{size}")
    no_overlap("upper box at 7h", crate, Pos(0, 0, seat) * upper)
    seated = _overlap(crate, Pos(0, 0, seat - 0.3) * upper)
    check("upper box seats (0.3 mm lower collides)", seated > 0, f"overlap {seated:.2f} mm3")
    no_overlap("cap at 7h", crate, cap)
    lip_kept = abs(_overlap(crate, band) - _overlap(make_box(size), band))
    check("wall band + lip above window intact", lip_kept < 1e-3, f"delta {lip_kept:.4f} mm3")
    no_overlap("bag vs crate", crate, bag)
    no_overlap("bag vs cap", cap, bag)
    for index, label in enumerate(CATEGORIES):
        card = make_card(size, index)
        placed = Pos(0, slots[index % len(slots)], FLOOR_Z) * card
        check(f"card {label} valid", card.is_valid)
        no_overlap(f"card {label} vs crate", crate, placed)
        no_overlap(f"card {label} vs cap", cap, placed)
    check("follower valid", follower.is_valid)
    no_overlap("follower vs crate", crate, follower)
    return results


def verify() -> bool:
    """Run fit/stacking checks for every shelf, print them, and return True if all pass."""
    passed = True
    for shelf in SHELVES:
        for name, ok, detail in _verify_shelf(shelf):
            passed &= ok
            print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    return passed


if __name__ == "__main__":
    build()
    if not verify():
        raise SystemExit("baglib verification failed")
