"""U2 / T033-S1 — the `voice` extra declares the pinned faster-whisper STT stack.

The pin lives in docs/specs/Voice_Bot/evidence-register.md (row T033-S1). This test
keeps the extra and the register in step. It does not change STT_PROVIDER (still None).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from hive_planner.voice_bot import VOICE_EXTRA_NAME, VOICE_STACK_PYPI

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
REGISTER = ROOT / "docs" / "specs" / "Voice_Bot" / "evidence-register.md"

PINNED = ("faster-whisper==1.2.1", "ctranslate2==4.9.0")


def test_voice_extra_pins_faster_whisper_stack():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    voice = data["project"]["optional-dependencies"][VOICE_EXTRA_NAME]
    for spec in PINNED:
        assert spec in voice, f"{spec} missing from [project.optional-dependencies].voice"


def test_voice_extra_pins_match_evidence_register_row():
    text = REGISTER.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| T033-S1 |"))
    assert "`faster-whisper` **1.2.1**" in row
    assert "`ctranslate2` **4.9.0**" in row
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    voice = data["project"]["optional-dependencies"][VOICE_EXTRA_NAME]
    versions = {re.split(r"[=<>]", s)[0]: s.split("==")[1] for s in voice if "==" in s}
    assert versions["faster-whisper"] == "1.2.1"
    assert versions["ctranslate2"] == "4.9.0"


def test_runtime_install_list_is_unchanged_and_stt_stays_typed():
    # Adding STT to the extra must not add it to the runtime pip check (that would
    # make ensure-runtime report a missing module on every host without the model).
    assert VOICE_STACK_PYPI == ("moshi", "pipecat-ai")
    from hive_planner.voice_stt import STT_PIN_PROVIDER

    assert STT_PIN_PROVIDER == "faster-whisper"
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == []
