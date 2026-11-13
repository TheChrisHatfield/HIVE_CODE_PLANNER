from __future__ import annotations

import importlib.util
from pathlib import Path


def _mod():
    path = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_hard_negatives.py"
    spec = importlib.util.spec_from_file_location("sandbox_rank_hard_negatives_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_csharp_hard_negative_uses_csharp_signals(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    path = root / "src" / "Unused.cs"
    path.parent.mkdir(parents=True)
    path.write_text(
        "public class A {\n  public void Bar() { Foo(); }\n  public void Foo() { }\n}\n",
        encoding="utf-8",
    )
    mod = _mod()
    signals = mod._signals_for(path, root, path.read_text(encoding="utf-8"), set(), {}, set())
    assert signals.wiring_hop == 1
