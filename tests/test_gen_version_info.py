from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_gen_version_info():
    path = Path(__file__).resolve().parents[1] / "packaging" / "gen_version_info.py"
    spec = importlib.util.spec_from_file_location("gen_version_info", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_version_tuple_parses_pre_release_segments() -> None:
    mod = _load_gen_version_info()
    assert mod._version_tuple("1.4.0-beta1") == (1, 4, 0, 0)
    assert mod._version_tuple("2.0.0rc1") == (2, 0, 0, 0)
