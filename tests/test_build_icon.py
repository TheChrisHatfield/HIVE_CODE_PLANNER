from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assets" / "build_icon.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_icon", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_canvas_margin_scales_and_keeps_1024_design():
    icon = _load()
    assert icon.canvas_margin(1024) == 96
    assert icon.canvas_margin(64) == 6.0


def test_canvas_margin_rejects_non_positive_size():
    icon = _load()
    with pytest.raises(ValueError, match=">= 1"):
        icon.canvas_margin(0)


def test_ring_hexes_stay_inside_64px_canvas():
    icon = _load()
    size = 64
    usable = size - 2 * icon.canvas_margin(size)
    hex_radius = usable * 0.145
    for hx, hy in icon.ring_hex_centers(size):
        for x, y in icon.hexagon_points(hx, hy, hex_radius):
            assert 0 <= x <= size
            assert 0 <= y <= size
    img = icon.draw_icon(size)
    assert img.size == (size, size)
    assert img.getbbox() is not None
