"""The base range: plain stackable crates and caps in the sizes people actually print."""

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
                    f"Stackable crate, usable cavity {cav_w:.0f}x{cav_d:.0f}x{cav_h:.0f} mm. "
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
