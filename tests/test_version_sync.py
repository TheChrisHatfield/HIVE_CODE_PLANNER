from __future__ import annotations

import re
from pathlib import Path


def test_package_version_matches_pyproject() -> None:
    from hive_planner import __version__

    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "version not found in pyproject.toml"
    assert __version__ == match.group(1)
