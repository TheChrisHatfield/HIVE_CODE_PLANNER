"""Build a square Hive Planner icon with exact geometry."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

BG = (0, 0, 0, 0)  # transparent — Windows icons use alpha, not a solid tile color
GREEN = (16, 185, 129, 255)
INK = (5, 10, 15, 255)
SIZE = 1024
MARGIN = 96


def hexagon_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    """Flat-top regular hexagon."""
    points: list[tuple[float, float]] = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def draw_icon(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)

    usable = size - (MARGIN * 2)
    center = size / 2

    # Ring of 6 hexes around empty center; radius chosen so cluster fits in usable area.
    hex_radius = usable * 0.145
    ring_radius = usable * 0.27

    for i in range(6):
        angle = math.radians(60 * i - 90)
        hx = center + ring_radius * math.cos(angle)
        hy = center + ring_radius * math.sin(angle)
        draw.polygon(hexagon_points(hx, hy, hex_radius), fill=GREEN)

    # Center checklist mark
    mark_w = usable * 0.22
    mark_h = usable * 0.18
    left = center - mark_w / 2
    top = center - mark_h / 2
    row_gap = mark_h / 3
    check_size = mark_h * 0.11
    line_left = left + mark_w * 0.34
    line_right = left + mark_w * 0.92

    for row in range(3):
        y = top + row_gap * (row + 0.55)
        # checkmark
        cx = left + mark_w * 0.14
        draw.line(
            [(cx - check_size * 0.45, y), (cx - check_size * 0.05, y + check_size * 0.55), (cx + check_size * 0.55, y - check_size * 0.45)],
            fill=INK,
            width=max(2, size // 128),
        )
        # line
        end = line_right if row < 2 else left + mark_w * 0.72
        draw.line([(line_left, y), (end, y)], fill=INK, width=max(2, size // 128))

    # warning triangle on third row
    tri_cx = left + mark_w * 0.84
    tri_h = mark_h * 0.12
    tri_w = mark_h * 0.14
    tri_top = top + row_gap * 2.35 - tri_h * 0.35
    draw.polygon(
        [
            (tri_cx, tri_top),
            (tri_cx - tri_w * 0.55, tri_top + tri_h),
            (tri_cx + tri_w * 0.55, tri_top + tri_h),
        ],
        outline=INK,
        width=max(2, size // 160),
    )
    draw.line([(tri_cx, tri_top + tri_h * 0.35), (tri_cx, tri_top + tri_h * 0.62)], fill=INK, width=max(2, size // 180))
    draw.point((tri_cx, tri_top + tri_h * 0.78), fill=INK)

    return img


def main() -> None:
    here = Path(__file__).resolve().parent
    img = draw_icon()
    png_path = here / "HivePlanner.png"
    ico_path = here / "HivePlanner.ico"
    img.save(png_path, format="PNG")
    sizes = [256, 128, 64, 48, 32, 16]
    img.save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Wrote {png_path}")
    print(f"Wrote {ico_path}")


if __name__ == "__main__":
    main()
