"""T012 / T013 / T015 / T025 — recorded answers, hybrid fallback, G6 edits latch."""

from __future__ import annotations

import json
from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    STT_PROVIDER,
    edits_enabled,
    g6_register_pass,
    hybrid_speech_path,
    native_chat_path,
    voice_bot_config_path,
)

# T012/T028 answers on pinned Cursor 2026.11.05. Native APIs are fail; ACP fallback has run (G2).
G1_ANSWERS = {
    "G1a": "fail",  # no public submit API into the open Composer tab
    "G1b": "fail",  # no targeting API for the active native conversation
    "G1c": "fail",  # native progress/context is not readable from this process
    "G1d": "fail",  # native voice provider is not replaceable via a documented API
}


def test_g1_native_chat_is_fail_and_acp_fallback_is_the_coding_session():
    assert set(G1_ANSWERS) == {"G1a", "G1b", "G1c", "G1d"}
    assert all(value == "fail" for value in G1_ANSWERS.values())
    assert native_chat_path() == "labeled_acp_fallback"


def test_g1_register_is_pass_via_labeled_acp():
    register = Path(__file__).resolve().parents[1] / "docs" / "specs" / "Voice_Bot" / "evidence-register.md"
    body = register.read_text(encoding="utf-8")
    g1 = next(line for line in body.splitlines() if line.startswith("| G1 |"))
    assert "**pass**" in g1
    assert "blocked" not in g1
    for key, value in G1_ANSWERS.items():
        row = next(line for line in body.splitlines() if line.startswith(f"| {key} |"))
        assert row.split("|")[4].strip() == value


def test_hybrid_speech_path_is_typed_until_stt_is_pinned():
    assert STT_PROVIDER is None
    assert hybrid_speech_path() == "typed_instruction"


def test_edits_stay_off_until_g6_closes():
    assert edits_enabled() is False


def _write_g6_register(root: Path, result: str) -> None:
    spec = root / "docs" / "specs" / "Voice_Bot"
    spec.mkdir(parents=True)
    (spec / "evidence-register.md").write_text(
        "| Claim ID | Component | Pinned | Test | Result | Date | Notes |\n"
        "|---|---|---|---|---|---|---|\n"
        f"| G6 | permissions | x | t | **{result}** | 2026-11-10 | fixture |\n",
        encoding="utf-8",
    )


def test_edits_latch_requires_register_pass_and_config_true(tmp_path: Path):
    paths = RepoPaths(root=tmp_path)
    _write_g6_register(tmp_path, "pass")
    assert g6_register_pass(paths) is True
    assert edits_enabled(paths) is False
    cfg = voice_bot_config_path(paths)
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"edits_enabled": True}), encoding="utf-8")
    assert edits_enabled(paths) is True


def test_edits_latch_stays_off_when_g6_is_not_pass(tmp_path: Path):
    paths = RepoPaths(root=tmp_path)
    _write_g6_register(tmp_path, "partial")
    cfg = voice_bot_config_path(paths)
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"edits_enabled": True}), encoding="utf-8")
    assert g6_register_pass(paths) is False
    assert edits_enabled(paths) is False


def test_fixture_gate_tests_do_not_enable_production_edits():
    from hive_planner.config import RepoPaths as HivePaths
    import hive_planner.voice_bot as vb

    hive = HivePaths(root=Path(__file__).resolve().parents[1])
    cfg = vb.load_voice_bot_config(hive)
    assert cfg.edits_enabled is False
    assert vb.edits_enabled(hive) is False

