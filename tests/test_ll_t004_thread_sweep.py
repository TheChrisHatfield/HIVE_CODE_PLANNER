"""LL-T004 thread-sweep defaults and cold winner (no llama.cpp spawn)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ll_t004_thread_sweep.py"


def _mod():
    spec = importlib.util.spec_from_file_location("ll_t004_thread_sweep_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_cores_uses_detected_host_not_lab_36() -> None:
    sweep = _mod()
    assert sweep.default_cores(["sweep.py"], detected=8) == 8
    assert sweep.default_cores(["sweep.py", "32"], detected=8) == 32
    assert "winner_cold" in _SCRIPT.read_text(encoding="utf-8")
    assert "winner_warm" not in _SCRIPT.read_text(encoding="utf-8")


def test_default_cores_rejects_non_positive_argv() -> None:
    sweep = _mod()
    with pytest.raises(SystemExit):
        sweep.default_cores(["sweep.py", "0"], detected=8)
    with pytest.raises(SystemExit):
        sweep.default_cores(["sweep.py", "nope"], detected=8)


def test_cold_score_keeps_zero_prompt_ms() -> None:
    sweep = _mod()
    row = {"cold": {"prompt_ms": 0.0, "wall_ms": 3100.0}}
    assert sweep.cold_score(row) == 0.0
    missing = {"cold": {"prompt_ms": None, "wall_ms": 3100.0}}
    assert sweep.cold_score(missing) == 3100.0
