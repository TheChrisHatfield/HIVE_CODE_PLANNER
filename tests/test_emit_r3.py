from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAN_LOOP = ROOT / "scripts" / "gan-loop"
if str(GAN_LOOP) not in sys.path:
    sys.path.insert(0, str(GAN_LOOP))

LOCK = GAN_LOOP / "round3-proposals.json"


def _load():
    spec = importlib.util.spec_from_file_location("emit_r3", GAN_LOOP / "_emit_r3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_does_not_rewrite_round3_proposals():
    before = LOCK.read_bytes() if LOCK.exists() else None
    _load()
    after = LOCK.read_bytes() if LOCK.exists() else None
    assert after == before


def test_emit_writes_eight_named_sources(tmp_path: Path):
    before = LOCK.read_bytes() if LOCK.exists() else None
    emit_r3 = _load()
    out = tmp_path / "round3-proposals.json"
    written = emit_r3.emit(out)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert [item["name"] for item in payload] == [
        "roman_value.py",
        "tip_split.py",
        "dim_weight.py",
        "compass_name.py",
        "scarf_rows.py",
        "batter_scale.py",
        "letter_post.py",
        "pantry_jar.py",
    ]
    assert all(item["source"] for item in payload)
    after = LOCK.read_bytes() if LOCK.exists() else None
    assert after == before
