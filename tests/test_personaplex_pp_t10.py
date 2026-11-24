"""PP-T10 parent: child artifacts exist. SC-PP6 is not claimed passed."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_pp_t10_child_artifacts_present():
    assert (_ROOT / "scripts" / "personaplex_q8_local.py").is_file()
    assert (_ROOT / "scripts" / "personaplex_sc_pp6_judge.py").is_file()
    assert (
        _ROOT
        / "code-improvements"
        / "personaplex-migrate"
        / "moshi"
        / "moshi"
        / "utils"
        / "quantize.py"
    ).is_file()
    assert (_ROOT / "docs" / "specs" / "PersonaPlex_migrate" / "q8-quantize-diff-pp-t10a.md").is_file()
    assert (_ROOT / "docs" / "specs" / "PersonaPlex_migrate" / "pp-t10d-graphs-record.md").is_file()
    record = (_ROOT / "docs" / "specs" / "PersonaPlex_migrate" / "pp-t10e-sc-pp6-record.md").read_text(
        encoding="utf-8"
    )
    assert "fail closed" in record.lower() or "**fail closed**" in record.lower()
    assert "not a pass" in record.lower() or "not an SC-PP6 pass" in record.lower()


def test_pp_t10_rollup_does_not_claim_sc_pp6():
    text = (_ROOT / "docs" / "specs" / "PersonaPlex_migrate" / "pp-t10-rollup.md").read_text(
        encoding="utf-8"
    )
    assert "not passed" in text.lower()
    assert "PP-T8" in text
