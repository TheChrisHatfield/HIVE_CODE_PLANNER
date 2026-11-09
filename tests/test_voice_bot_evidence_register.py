"""T002 — evidence register must record G0–G6 with dates and non-empty tests."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "specs" / "Voice_Bot" / "evidence-register.md"

GATE_IDS = tuple(f"G{i}" for i in range(7))
ALLOWED_RESULTS = {"pass", "partial", "blocked", "fail"}


def _table_rows(text: str) -> list[list[str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("| G")]
    rows: list[list[str]] = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if cells and cells[0].startswith("G") and len(cells) >= 7:
            rows.append(cells)
    return rows


def test_evidence_register_covers_all_gates() -> None:
    body = REGISTER.read_text(encoding="utf-8")
    rows = _table_rows(body)
    found = {r[0] for r in rows}
    assert found == set(GATE_IDS), f"missing gates: {set(GATE_IDS) - found}"


def test_evidence_register_g0_pass_and_results_valid() -> None:
    body = REGISTER.read_text(encoding="utf-8")
    by_id = {r[0]: r for r in _table_rows(body)}
    g0 = by_id["G0"]
    assert "1.3.0" in g0[2], "G0 must pin hive-planner version"
    assert g0[4].strip("*") == "pass"
    assert g0[5] == "2026-11-09"
    for gid in GATE_IDS:
        row = by_id[gid]
        assert len(row) >= 7
        result = row[4].strip().strip("*").lower()
        assert result in ALLOWED_RESULTS, f"{gid} invalid result: {row[4]}"
        assert row[3], f"{gid} missing test method"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[5]), f"{gid} missing ISO date"
