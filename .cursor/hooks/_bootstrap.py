"""Bootstrap src/ on sys.path for Cursor hooks without editable install."""
from __future__ import annotations

import sys
from pathlib import Path


def bootstrap_hive_planner() -> Path:
    hooks_dir = Path(__file__).resolve().parent
    repo_root = hooks_dir.parents[1]
    src = repo_root / "src"
    if src.is_dir():
        src_str = str(src)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)
    return repo_root
