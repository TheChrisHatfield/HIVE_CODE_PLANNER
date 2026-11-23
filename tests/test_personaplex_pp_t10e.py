"""PP-T10e: SC-PP6 text-token judge. A gap note is not a pass."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "personaplex_sc_pp6_judge.py"


def _load():
    spec = importlib.util.spec_from_file_location("personaplex_sc_pp6_judge", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ok(**overrides):
    base = dict(
        prompt_id="p1",
        wav_id="w1",
        bf16_offline_text="Hello there friend how are you",
        q8_offline_text="Hello there friend how are you today",
        q8_live_text="Hello there friend this is the live turn",
        same_prompt=True,
        same_wav=True,
    )
    base.update(overrides)
    return base


def test_pp_t10e_pass_requires_intelligible_offline_and_live():
    mod = _load()
    assert mod.sc_pp6_quality_holds(**_ok()) is True


def test_pp_t10e_gap_note_is_not_a_pass():
    mod = _load()
    assert mod.sc_pp6_quality_holds(**_ok(gap_note_only=True)) is False


def test_pp_t10e_q8_unintelligible_vs_bf16_fails():
    mod = _load()
    assert mod.sc_pp6_quality_holds(**_ok(q8_offline_text="???")) is False


def test_pp_t10e_live_garbles_while_offline_clean_fails():
    mod = _load()
    assert mod.sc_pp6_quality_holds(**_ok(q8_live_text="...")) is False


def test_pp_t10e_missing_live_fails():
    mod = _load()
    assert mod.sc_pp6_quality_holds(**_ok(q8_live_text=None)) is False
    assert mod.sc_pp6_quality_holds(**_ok(q8_live_text="")) is False


def test_pp_t10e_refuses_moshika_and_rag_exporter_and_offload():
    mod = _load()
    assert mod.sc_pp6_quality_holds(**_ok(used_moshika_rag_weights=True)) is False
    assert mod.sc_pp6_quality_holds(**_ok(used_moshi_rag_q8_local=True)) is False
    assert mod.sc_pp6_quality_holds(**_ok(cpu_offload=True)) is False


def test_pp_t10e_different_prompt_or_wav_fails():
    mod = _load()
    assert mod.sc_pp6_quality_holds(**_ok(same_prompt=False)) is False
    assert mod.sc_pp6_quality_holds(**_ok(same_wav=False)) is False


def test_pp_t10e_verdict_from_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = _load()
    path = tmp_path / "record.json"
    path.write_text(json.dumps({"gap_note_only": True, "prompt_id": "p", "wav_id": "w"}), encoding="utf-8")
    assert mod.verdict_from_record(path)["holds"] is False
    monkeypatch.setattr("sys.argv", ["personaplex_sc_pp6_judge", "--record", str(path)])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 2
