"""The base range: plain stackable crates and caps in the sizes people actually print.

Exported sizes: crates 1x1x3, 2x1x3, 2x2x3, 2x2x6 and 3x2x6; caps 1x1, 2x1, 2x2 and 3x2.
Any other size from 1x1x2 to 8x8x40 comes from the CLI, e.g. ``uv run stakee box 4x2x6``.

Size: a crate of ``nx x ny x h`` units is ``42 * n - 0.5`` mm per side and ``7 * h + 4`` mm
tall to the top of its stacking lip. The usable cavity is ``42 * n - 4.5`` mm per side and
``7 * h - 5.5`` mm deep, measured from the floor to the stacking seat.

Stacking: the Gridfinity-profile feet of an upper crate drop into the lip of the crate below
and seat on its 45 deg chamfers, so the upper crate stands at exactly ``z = 7 * h`` of the
lower one, with a 0.75 mm shadow gap between the bodies. ``verify()`` checks this for every
exported size: a box and a cap placed at ``7 * h`` overlap the crate by zero volume, and
collide with it when lowered 0.05 mm (they seat on the chamfers, they do not hover).

Caps (``make_cap``): one hollow foot plus a 2.4 mm top plate, 7.15 mm tall. A cap seats in
the lip of any crate with the same footprint. Its top is flat, so it ends the stack.

Features of every crate (all from ``make_box`` in ``stakee/core.py``):

- Magnet pockets: four per grid cell under the feet, 6.5 mm wide and 2.4 mm deep, 13 mm
  from the cell center on both axes, for optional 6x2 mm disc magnets.
- Divider slots: 1.6 mm wide and 0.8 mm deep, every 21 mm on all four inner walls. They run
  from the floor up through the lip, so a plate drops straight in. They take the 1.2 mm
  plates and 1.5 mm thick ends of the ``dividers`` family.
- Label recess: on the front (-Y) face, ``min(width - 16, 60)`` mm wide, 12 mm tall and
  0.6 mm deep, its top 1.5 mm below the stacking seat. Crates under 3 units tall have none.
  Caps carry the same recess on top.
- Clip sockets: eight L-shaped bayonet pockets on the side (+/-X) faces, 12 mm in from the
  front and back faces. Each side has two centered 2 mm below the lip top and two centered
  6.5 mm above the bottom. The ``kit`` stack clip locks two stacked crates together through them.
"""

from build123d import Part, Pos

from stakee.core import HEIGHT_UNIT, BoxSize, make_box, make_cap
from stakee.export import PartInfo, save

MODULE = "crates"

SIZES = (BoxSize(1, 1, 3), BoxSize(2, 1, 3), BoxSize(2, 2, 3), BoxSize(2, 2, 6), BoxSize(3, 2, 6))
CAPS = ((1, 1), (2, 1), (2, 2), (3, 2))
SETTLE = 0.05  # mm an upper part is lowered to prove it rests on the chamfers


def _overlap(a: Part, b: Part) -> float:
    common = a & b
    return common.volume if common else 0.0


def verify() -> bool:
    """Each size: valid; a box and a cap of the same footprint stack on it at exactly 7*h
    with zero interference, and collide when lowered SETTLE mm (they seat, not hover)."""
    ok = True
    for size in SIZES:
        box = make_box(size)
        pitch = size.h * HEIGHT_UNIT
        for name, upper in (
            ("box", make_box(BoxSize(size.nx, size.ny, 2))),
            ("cap", make_cap(size.nx, size.ny)),
        ):
            clear = _overlap(box, Pos(0, 0, pitch) * upper)
            seated = _overlap(box, Pos(0, 0, pitch - SETTLE) * upper)
            passed = box.is_valid and clear < 1e-6 and seated > 0
            ok &= passed
            print(
                f"  [{'PASS' if passed else 'FAIL'}] {size} + {name}: "
                f"{clear:.6f} mm3 at 7h, {seated:.2f} mm3 lowered {SETTLE} mm"
            )
    return ok


def build() -> None:
    for size in SIZES:
        tag = f"{size.nx}x{size.ny}x{size.h}"
        cav_w, cav_d, cav_h = size.cavity
        save(
            MODULE,
            make_box(size),
            PartInfo(
                slug=f"crate-{tag}",
                title=f"Crate {tag}",
                blurb=(
                    f"Stackable crate, usable cavity {cav_w:g}x{cav_d:g}x{cav_h:g} mm. "
                    "Divider slots every 21 mm, front label recess, clip sockets on the sides."
                ),
                material="PLA or PETG",
                print_notes="Upright, no supports, 3 walls, 15% infill. Optional 6x2 mm magnets.",
                color="#e8e3d6",
                footprint=tag,
            ),
        )
    for nx, ny in CAPS:
        save(
            MODULE,
            make_cap(nx, ny),
            PartInfo(
                slug=f"cap-{nx}x{ny}",
                title=f"Cap {nx}x{ny}",
                blurb="Lid that seats into any crate's stacking lip; recessed label on top.",
                material="PETG",
                print_notes="Upside down (plate on the bed), no supports.",
                color="#f2a03d",
                footprint=f"{nx}x{ny}",
            ),
        )


if __name__ == "__main__":
    if not verify():
        raise SystemExit("crate verification failed; nothing exported")
    build()
