from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

SRC = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "continuous-thought-machines"
    / "data"
    / "custom_datasets.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("ctm_custom_datasets", SRC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _paint(rows: list[str]) -> np.ndarray:
    colors = {"R": [1, 0, 0], "G": [0, 1, 0], "B": [0, 0, 1], ".": [0, 0, 0]}
    height, width = len(rows), len(rows[0])
    maze = np.zeros((height, width, 3), dtype=np.float32)
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            maze[y, x] = colors[cell]
    return maze


def _solve(maze: np.ndarray, route_length: int = 10) -> np.ndarray:
    holder = type("Holder", (), {"maze_route_length": route_length})()
    return _module().MazeImageFolder.get_solution(holder, maze)


def test_dead_end_returns_gathered_steps_not_placeholder_fours() -> None:
    path = _solve(_paint(["R.", ".G"]))
    assert path.dtype == np.int64
    assert path.size == 0
    assert 4 not in path.tolist()


def test_short_route_is_not_padded_with_placeholder_fours() -> None:
    path = _solve(_paint(["RBBG"]), route_length=10)
    assert path.tolist() == [3, 3, 3]


def test_upward_dead_end_does_not_hide_the_rightward_route() -> None:
    # Greedy Up-first walked into the spur at (0,0) and never reached G.
    path = _solve(_paint(["B..", "RBG"]))
    assert path.tolist() == [3, 3]
