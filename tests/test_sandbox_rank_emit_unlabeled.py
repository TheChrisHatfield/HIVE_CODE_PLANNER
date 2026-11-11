from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_emit_unlabeled.py"
    spec = importlib.util.spec_from_file_location("sandbox_rank_emit_unlabeled", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_empty_rank_log_is_not_a_skip_stamp(tmp_path: Path) -> None:
    emit = _load()
    destination = tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl"
    destination.parent.mkdir(parents=True)
    destination.write_text("", encoding="utf-8")
    assert emit.should_skip_existing_log(destination) is False
    destination.write_text("{}\n", encoding="utf-8")
    assert emit.should_skip_existing_log(destination) is True


def test_write_rank_log_refuses_empty_rows(tmp_path: Path) -> None:
    emit = _load()
    destination = tmp_path / "rank-rows.jsonl"
    assert emit.write_rank_log(destination, []) is False
    assert not destination.is_file()
    assert emit.write_rank_log(destination, [{"file": "a.py", "outcome": "unlabeled"}]) is True
    assert destination.read_text(encoding="utf-8") == '{"file": "a.py", "outcome": "unlabeled"}\n'
