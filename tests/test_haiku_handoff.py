from __future__ import annotations

import importlib.util
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts" / "haiku_handoff.py"

TEMPLATE = """\
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: read-only=<READY|NOT> full-agent=<READY|NOT>
G0–G6: <one-liners if changed>
Done this chat: <1–3 bullets>
Open next: <exactly one micro-task>
Do not redo: <commands that passed>
Files changed: <paths>
Blocked: <or none>
First action: <one line>
"""

FILLED = """\
CONTINUE Voice_Bot
Last chat: 2026-11-13
Budget left: unknown
Verdict: read-only=READY full-agent=NOT
G0–G6: unchanged
Done this chat:
- added the snapshot contract test
- pytest 54 passed
Open next: Item 17 write the live-write nonce check
Do not redo: pytest tests/test_voice_bot_contracts.py
Files changed: tests/test_voice_bot_contracts.py
Blocked: none
First action: open evidence-register.md G6 row
"""


def _mod():
    spec = importlib.util.spec_from_file_location("haiku_handoff_script", SRC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_continue_uses_the_last_block_not_the_template() -> None:
    cont = _mod().parse_continue(TEMPLATE + "\n" + FILLED)
    assert cont["Last chat"] == "2026-11-13"
    assert cont["Open next"] == "Item 17 write the live-write nonce check"
    assert cont["First action"] == "open evidence-register.md G6 row"


def test_parse_continue_keeps_multiline_done_this_chat() -> None:
    cont = _mod().parse_continue(FILLED)
    assert "added the snapshot contract test" in cont["Done this chat"]
    assert "pytest 54 passed" in cont["Done this chat"]
