from __future__ import annotations

import io
import json
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import pytest

from hive_planner.cartridge_promote import CartridgePromoteResult, HANDOFF_INCOMPLETE_MSG
from hive_planner.config import RepoPaths


def test_emit_cli_warns_when_promote_handoff_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    (root / "context-library" / "sources").mkdir(parents=True)

    def fake_emit(_paths, _feature, **kwargs):
        return {}, []

    def fake_promote(_paths, _feature, **kwargs):
        return CartridgePromoteResult(feature="x", ok=False, promotions={"micro": "skipped (not draft)"})

    monkeypatch.setattr("hive_planner.emitter.emit_cartridge", fake_emit)
    monkeypatch.setattr("hive_planner.cartridge_promote.promote_cartridge_drafts", fake_promote)

    from hive_planner.cli import main

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        code = main(["--root", str(root), "emit", "--feature", "x-feature", "--promote"])

    assert code != 0
    assert HANDOFF_INCOMPLETE_MSG.split("—")[0].strip() in stderr.getvalue()
