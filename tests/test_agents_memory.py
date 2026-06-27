from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.agents_memory import (
    AgentsMemoryError,
    EDITABLE_SECTION,
    ingest_agents_candidates,
    lint_agents_md,
    normalize_candidates_text,
    propose_agents_memory,
    run_agents_memory,
)
from hive_planner.config import RepoPaths


def _minimal_agents(extra: str = "") -> str:
    return f"""# AGENTS.md

## Repository root

`{extra}root`

## Planning Rosetta Stone

- hook `planning.rosetta`

## Startup read order

1. rosetta

## Delta model

- Holistic / Macro / Micro

## Active feature

**feature-x**

## Durable Workspace Facts

- Existing durable fact one.
"""


def test_lint_missing_section_errors(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    agents = paths.root / "AGENTS.md"
    agents.write_text("# AGENTS.md\n\n## Repository root\n\nroot\n", encoding="utf-8")
    report = lint_agents_md(paths)
    assert not report.ok
    assert any("Missing required section" in i.message for i in report.issues)


def test_lint_duplicate_bullets_warns(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    text = _minimal_agents()
    text = text.replace(
        "- Existing durable fact one.",
        "- Existing durable fact one.\n- Existing durable fact one.",
    )
    (paths.root / "AGENTS.md").write_text(text, encoding="utf-8")
    report = lint_agents_md(paths)
    assert any("Duplicate bullet" in i.message for i in report.issues)


def test_lint_long_bullet_warns(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    long_bullet = "- " + ("x" * 250)
    text = _minimal_agents() + f"\n{long_bullet}\n"
    (paths.root / "AGENTS.md").write_text(text, encoding="utf-8")
    report = lint_agents_md(paths)
    assert any("exceeds" in i.message for i in report.issues)


def test_lint_ok_on_repo_agents() -> None:
    repo = Path(__file__).resolve().parents[1]
    paths = RepoPaths(root=repo)
    report = lint_agents_md(paths)
    assert report.ok


def test_propose_writes_file_without_modifying_agents(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    agents = paths.root / "AGENTS.md"
    original = _minimal_agents("tmp-")
    agents.write_text(original, encoding="utf-8")

    candidates = paths.root / "candidates.md"
    candidates.write_text("- New durable fact for pytest validation.\n", encoding="utf-8")

    out = propose_agents_memory(paths, candidates)
    assert out.exists()
    assert agents.read_text(encoding="utf-8") == original
    proposal = out.read_text(encoding="utf-8")
    assert EDITABLE_SECTION in proposal
    assert "New durable fact" in proposal


def test_apply_merges_operational_candidates(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    agents = paths.root / "AGENTS.md"
    agents.write_text(_minimal_agents(), encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- New durable fact from guarded apply.\n", encoding="utf-8")

    result = run_agents_memory(paths, candidates, apply=True)
    assert result.applied
    updated = agents.read_text(encoding="utf-8")
    assert "New durable fact from guarded apply." in updated
    assert "Existing durable fact one." in updated
    assert lint_agents_md(paths).ok


def test_apply_rejects_behavioral_candidate(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- API must validate all request payloads.\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="All candidate"):
        run_agents_memory(paths, candidates, apply=True)


def test_apply_rolls_back_on_lint_failure(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    broken = _minimal_agents().replace("## Planning Rosetta Stone", "## Missing Rosetta")
    (paths.root / "AGENTS.md").write_text(broken, encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- Valid operational candidate bullet.\n", encoding="utf-8")
    original = (paths.root / "AGENTS.md").read_text(encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="Apply rolled back"):
        run_agents_memory(paths, candidates, apply=True)
    assert (paths.root / "AGENTS.md").read_text(encoding="utf-8") == original


def test_propose_rejects_duplicate_candidate(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- Existing durable fact one.\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="All candidate"):
        propose_agents_memory(paths, candidates)


def test_ingest_normalizes_transcript_export(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    source = paths.root / "export.txt"
    source.write_text(
        "user: remember this\n"
        "- Run ci-check before handoff\n"
        "assistant: noted\n"
        "- API must return 404 # behavioral\n",
        encoding="utf-8",
    )
    out = ingest_agents_candidates(paths, source)
    text = out.read_text(encoding="utf-8")
    assert "# operational" in text
    assert "# behavioral" in text
    assert "Run ci-check" in text
    assert "API must return 404" in text
    assert "# behavioral" not in text.split("# behavioral", 1)[-1].splitlines()[0] if "# behavioral" in text else True
    assert "user:" not in text
    behavioral_section = text.split("# behavioral", 1)[-1]
    assert "API must return 404" in behavioral_section
    assert "Run ci-check" not in behavioral_section


def test_apply_inserts_editable_section_after_active_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    agents_text = """# AGENTS.md

## Repository root

root

## Planning Rosetta Stone

r

## Startup read order

r

## Delta model

r

## Active feature

**feature-x**
"""
    agents = paths.root / "AGENTS.md"
    agents.write_text(agents_text, encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- New durable fact.\n", encoding="utf-8")
    run_agents_memory(paths, candidates, apply=True)
    updated = agents.read_text(encoding="utf-8")
    active_idx = updated.index("## Active feature")
    facts_idx = updated.index("## Durable Workspace Facts")
    assert active_idx < facts_idx
    assert updated.index("## Delta model") < facts_idx


def test_normalize_candidates_requires_bullets() -> None:
    with pytest.raises(AgentsMemoryError, match="No candidate bullets"):
        normalize_candidates_text("user: hello\nassistant: hi\n")
