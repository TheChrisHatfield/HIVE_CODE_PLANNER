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


def test_lint_duplicate_bullet_reports_absolute_line_number(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    lines = [
        "# AGENTS.md",
        "",
        "## Repository root",
        "",
        "root",
        "",
        "## Planning Rosetta Stone",
        "",
        "- hook `planning.rosetta`",
        "",
        "## Startup read order",
        "",
        "1. rosetta",
        "",
        "## Delta model",
        "",
        "- Holistic / Macro / Micro",
        "",
        "## Active feature",
        "",
        "**feature-x**",
        "",
        "## Durable Workspace Facts",
        "",
        "- Existing durable fact one.",
        "- Existing durable fact one.",
        "",
    ]
    (paths.root / "AGENTS.md").write_text("\n".join(lines), encoding="utf-8")
    report = lint_agents_md(paths)
    duplicate_issues = [i for i in report.issues if "Duplicate bullet" in i.message]
    assert len(duplicate_issues) == 1
    assert duplicate_issues[0].line == 26


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


def test_apply_preserves_preamble_before_first_section(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    agents = paths.root / "AGENTS.md"
    preamble = "<!-- BOOTSTRAP: hive_planner init -->"
    agents.write_text(
        _minimal_agents().replace("# AGENTS.md", f"# AGENTS.md\n{preamble}"),
        encoding="utf-8",
    )
    candidates = paths.root / "candidates.md"
    candidates.write_text("- New durable fact from guarded apply.\n", encoding="utf-8")

    run_agents_memory(paths, candidates, apply=True)
    updated = agents.read_text(encoding="utf-8")
    assert preamble in updated
    assert updated.index(preamble) < updated.index("## Repository root")


def test_propose_rejects_ambiguous_candidate(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- Run ci-check before handoff; API must return 404 when disabled.\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="All candidate"):
        propose_agents_memory(paths, candidates, auto_route=False)


def test_auto_route_splits_oversized_operational_candidate(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    long = (
        "Portable HivePlanner.exe lives under dist/HivePlannerPortable and must be rebuilt "
        "after launcher UI changes. Use scripts/build_portable.ps1, then smoke-test ocr-status "
        "and rosetta-eject --prompt-only before shipping. Close running HivePlanner.exe first "
        "so Windows does not lock the output binary. # operational"
    )
    assert len(long) > 240
    candidates = paths.root / "candidates.md"
    candidates.write_text(f"- {long}\n", encoding="utf-8")
    result = run_agents_memory(paths, candidates, apply=True, skip_wiring_audit=True)
    assert result.applied
    assert len(result.accepted) >= 2
    assert all(len(b) <= 240 for b in result.accepted)
    assert any(d.get("arm") == "split" for d in result.routing)
    agents = (paths.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "HivePlanner.exe" in agents or "build_portable" in agents


def test_split_arm_records_failure_when_all_pieces_duplicate(tmp_path: Path) -> None:
    from hive_planner.agents_memory import _evaluate_candidates, parse_sections
    from hive_planner.memory_routing import load_routing_stats, split_long_bullet

    body = (
        "Portable HivePlanner.exe lives under dist/HivePlannerPortable. "
        "Rebuild with scripts/build_portable.ps1 after UI changes. "
        "Smoke-test ocr-status and status before shipping. "
        "Close the running exe first so Windows does not lock the binary."
    )
    long = f"{body} # operational"
    assert len(long) > 240
    sections = parse_sections(_minimal_agents())
    for piece in split_long_bullet(long, max_chars=240):
        sections.setdefault("Durable Workspace Facts", "")
        sections["Durable Workspace Facts"] += f"\n- {piece}"

    accepted, rejected, _, _ = _evaluate_candidates(
        sections,
        [long],
        paths=RepoPaths(root=tmp_path),
        auto_route=True,
    )
    assert not accepted
    assert rejected
    stats = load_routing_stats(RepoPaths(root=tmp_path))
    assert stats.arm("split").failures > 1.0


def test_finalize_apply_enforces_wiring_audit_when_unified(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.agents_memory import AgentsMemoryError, apply_agents_memory_accepted
    from hive_planner.project_profile import write_project_profile

    paths = RepoPaths(root=tmp_path)
    write_project_profile(
        paths.root,
        profile="minimal",
        project_name="demo",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
    )
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="wiring audit"):
        apply_agents_memory_accepted(paths, accepted=["New operational fact."])


def test_finalize_apply_skips_bullets_already_in_agents(tmp_path: Path) -> None:
    from hive_planner.agents_memory import apply_agents_memory_accepted

    paths = RepoPaths(root=tmp_path)
    agents = _minimal_agents().replace(
        "- Existing durable fact one.",
        "- Existing durable fact one.\n- Keep logs concise.",
    )
    (paths.root / "AGENTS.md").write_text(agents, encoding="utf-8")
    result = apply_agents_memory_accepted(
        paths,
        accepted=["Keep logs concise.", "Add wiring audit evidence."],
        skip_wiring_audit=True,
    )
    assert result.applied
    assert result.accepted == ["Add wiring audit evidence."]
    text = (paths.root / "AGENTS.md").read_text(encoding="utf-8")
    assert text.count("Keep logs concise.") == 1
    assert "Add wiring audit evidence." in text


def test_finalize_apply_rejects_when_all_bullets_already_present(tmp_path: Path) -> None:
    from hive_planner.agents_memory import AgentsMemoryError, apply_agents_memory_accepted

    paths = RepoPaths(root=tmp_path)
    agents = _minimal_agents().replace(
        "- Existing durable fact one.",
        "- Existing durable fact one.\n- Keep logs concise.",
    )
    (paths.root / "AGENTS.md").write_text(agents, encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="already in AGENTS"):
        apply_agents_memory_accepted(
            paths,
            accepted=["Keep logs concise."],
            skip_wiring_audit=True,
        )


def test_auto_route_behavioral_writes_cl_candidates(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- API must return 404 when feature flag is disabled. # behavioral\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="All candidate"):
        run_agents_memory(paths, candidates, skip_wiring_audit=True)
    routed = paths.root / "docs" / "proposals" / "cl-candidates.md"
    assert routed.is_file()
    assert "API must return 404" in routed.read_text(encoding="utf-8")


def test_agents_memory_error_detail_includes_proposal_metadata() -> None:
    from hive_planner.agents_memory import AgentsMemoryError, agents_memory_error_detail

    exc = AgentsMemoryError(
        "All candidate bullets were rejected by validation",
        proposal_path="docs/proposals/agents-memory-1.md",
        rejected=[{"candidate": "bad", "reason": "behavioral"}],
        spec_actions=["Update docs/specs/x/spec.md"],
        current_facts="- Existing.",
        after_section="- Existing.",
        accepted=[],
    )
    detail = agents_memory_error_detail(exc)
    assert detail["proposal_path"] == "docs/proposals/agents-memory-1.md"
    assert detail["rejected"][0]["reason"] == "behavioral"


def test_apply_rolls_back_writes_proposal_on_lint_failure(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    broken = _minimal_agents().replace("## Planning Rosetta Stone", "## Missing Rosetta")
    (paths.root / "AGENTS.md").write_text(broken, encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- Valid operational candidate bullet.\n", encoding="utf-8")
    original = (paths.root / "AGENTS.md").read_text(encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="Apply rolled back") as exc_info:
        run_agents_memory(paths, candidates, apply=True)
    assert exc_info.value.proposal_path
    assert (paths.root / "AGENTS.md").read_text(encoding="utf-8") == original
    proposals = list((paths.root / "docs" / "proposals").glob("agents-memory-*.md"))
    assert proposals


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


def test_propose_behavioral_rejection_ignores_placeholder_active_feature(tmp_path: Path) -> None:
    from hive_planner.agents_memory import _evaluate_candidates, parse_sections

    text = _minimal_agents().replace("**feature-x**", "**none**")
    sections = parse_sections(text)
    _, rejected, _, _ = _evaluate_candidates(sections, ["API must return 404 when disabled."])
    assert rejected
    reason = rejected[0][1]
    assert "docs/specs/<feature>/spec.md" in reason
    assert "docs/specs/none/" not in reason


def test_propose_rejects_tag_only_candidates(tmp_path: Path) -> None:
    from hive_planner.agents_memory import _evaluate_candidates, parse_sections

    sections = parse_sections(_minimal_agents())
    accepted, rejected, _, _ = _evaluate_candidates(
        sections,
        ["# operational", "# behavioral", "Keep pytest in CI. # operational"],
    )
    assert accepted == ["Keep pytest in CI. # operational"]
    assert len(rejected) == 2
    assert all("section tag only" in reason for _, reason in rejected)


def test_parse_candidates_honors_behavioral_section_header() -> None:
    from hive_planner.agents_memory import _evaluate_candidates, _parse_candidates, parse_sections

    text = "# behavioral\n- The landing page shows a welcome banner.\n"
    raw = _parse_candidates(text)
    assert raw == ["The landing page shows a welcome banner. # behavioral"]
    sections = parse_sections(_minimal_agents())
    accepted, rejected, _, _ = _evaluate_candidates(sections, raw)
    assert not accepted
    assert rejected
    assert "spec.md" in rejected[0][1]


def test_operationalize_arm_records_failure_when_remediation_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.agents_memory import _evaluate_candidates, parse_sections
    from hive_planner.memory_routing import ARM_OPERATIONALIZE, RoutingDecision, load_routing_stats

    agents = _minimal_agents().replace(
        "- Existing durable fact one.",
        "- Run ci-check before handoff.",
    )
    sections = parse_sections(agents)
    paths = RepoPaths(root=tmp_path)

    def fake_route(bullet: str, *, feature, stats, rng=None) -> RoutingDecision:
        return RoutingDecision(
            arm=ARM_OPERATIONALIZE,
            original=bullet,
            remediations=["Run ci-check before handoff. # operational"],
            reason="test operationalize",
        )

    monkeypatch.setattr(
        "hive_planner.memory_routing.route_ambiguous_candidate",
        fake_route,
    )
    accepted, rejected, _, _ = _evaluate_candidates(
        sections,
        ["Run ci-check before handoff; API must return 404 when disabled."],
        paths=paths,
        auto_route=True,
    )
    assert not accepted
    assert rejected
    stats = load_routing_stats(paths)
    assert stats.arm(ARM_OPERATIONALIZE).failures > 1.0


def test_parse_candidates_honors_ambiguous_section_header() -> None:
    from hive_planner.agents_memory import _evaluate_candidates, _parse_candidates, parse_sections

    text = "# ambiguous\n- Run ci-check before handoff.\n"
    raw = _parse_candidates(text)
    assert raw == ["Run ci-check before handoff. # ambiguous"]
    sections = parse_sections(_minimal_agents())
    accepted, rejected, _, _ = _evaluate_candidates(sections, raw)
    assert not accepted
    assert rejected
    assert "Classification ambiguous" in rejected[0][1]


def test_parse_candidates_does_not_treat_heading_prose_as_section_tag() -> None:
    from hive_planner.agents_memory import _evaluate_candidates, _parse_candidates, parse_sections

    text = "# operational: tooling notes\n- API must return 404 when disabled.\n"
    raw = _parse_candidates(text)
    assert raw == ["API must return 404 when disabled."]
    sections = parse_sections(_minimal_agents())
    accepted, rejected, _, _ = _evaluate_candidates(sections, raw)
    assert not accepted
    assert rejected
    assert "spec.md" in rejected[0][1]


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


def test_ingest_routes_operational_out_of_behavioral_section(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    source = paths.root / "export.txt"
    source.write_text("# behavioral\n- Run ci-check before handoff.\n", encoding="utf-8")
    out = ingest_agents_candidates(paths, source)
    text = out.read_text(encoding="utf-8")
    assert "# operational" in text
    assert "Run ci-check before handoff." in text
    operational_part = text.split("# operational", 1)[1]
    assert "Run ci-check before handoff." in operational_part


def test_propose_rejects_duplicate_candidate_with_inline_tag(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- Existing durable fact one. # operational\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="All candidate"):
        propose_agents_memory(paths, candidates)


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


def test_ingest_skips_task_checkbox_lines(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    source = paths.root / "export.txt"
    source.write_text(
        "- Run ci-check before handoff.\n- [ ] Traced caller end-to-end\n",
        encoding="utf-8",
    )
    out = ingest_agents_candidates(paths, source)
    text = out.read_text(encoding="utf-8")
    assert "Run ci-check before handoff." in text
    assert "Traced caller" not in text


def test_parse_candidates_skips_task_checkbox_lines(tmp_path: Path) -> None:
    from hive_planner.agents_memory import _parse_candidates

    text = "\n".join(
        [
            "# operational",
            "- Run ci-check before handoff.",
            "- [ ] Traced caller end-to-end",
            "- [x] Integration-level validation evidence attached",
        ]
    )
    parsed = _parse_candidates(text)
    assert parsed == ["Run ci-check before handoff. # operational"]


def test_parse_candidates_ignores_prose_lines() -> None:
    from hive_planner.agents_memory import _parse_candidates

    text = "\n".join(
        [
            "# Cartridge memory candidates — feature-x",
            "",
            "Review before `agents-propose`. Behavioral lines belong in spec.md, not AGENTS.md.",
            "",
            "# operational",
            "",
            "- Run ci-check before handoff.",
        ]
    )
    parsed = _parse_candidates(text)
    assert parsed == ["Run ci-check before handoff. # operational"]


def test_parse_candidates_ignores_bullets_inside_code_fences() -> None:
    from hive_planner.agents_memory import _parse_candidates

    text = "\n".join(
        [
            "# operational",
            "",
            "- Real candidate.",
            "",
            "## Before",
            "",
            "```markdown",
            "- Existing fact inside fence.",
            "```",
        ]
    )
    parsed = _parse_candidates(text)
    assert parsed == ["Real candidate. # operational"]


def test_parse_candidates_recovers_after_unclosed_code_fence() -> None:
    from hive_planner.agents_memory import _parse_candidates

    text = "\n".join(
        [
            "# operational",
            "- First valid candidate.",
            "",
            "```markdown",
            "- Example inside fence only",
            "- Second valid candidate after missing closing fence.",
        ]
    )
    parsed = _parse_candidates(text)
    assert parsed == [
        "First valid candidate. # operational",
        "Example inside fence only # operational",
        "Second valid candidate after missing closing fence. # operational",
    ]


def test_parse_candidates_honors_behavioral_section_before_unclosed_fence() -> None:
    from hive_planner.agents_memory import _evaluate_candidates, _parse_candidates, parse_sections

    text = "# behavioral\n```markdown\n- The landing page shows a welcome banner.\n"
    raw = _parse_candidates(text)
    assert raw == ["The landing page shows a welcome banner. # behavioral"]
    sections = parse_sections(_minimal_agents())
    accepted, rejected, _, _ = _evaluate_candidates(sections, raw)
    assert not accepted
    assert rejected
    assert "spec.md" in rejected[0][1]


def test_ingest_recovers_unclosed_code_fence(tmp_path: Path) -> None:
    from hive_planner.agents_memory import ingest_agents_candidates

    paths = RepoPaths(root=tmp_path)
    source = paths.root / "export.md"
    source.write_text(
        "```markdown\n"
        "- Candidate inside unclosed opening fence.\n",
        encoding="utf-8",
    )

    out = ingest_agents_candidates(paths, source)
    text = out.read_text(encoding="utf-8")
    assert "Candidate inside unclosed opening fence." in text


def test_ingest_ignores_bullets_inside_code_fences(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    source = paths.root / "export.md"
    source.write_text(
        "# operational\n"
        "- Real candidate.\n"
        "```markdown\n"
        "- Example candidate inside fence.\n"
        "```\n",
        encoding="utf-8",
    )

    out = ingest_agents_candidates(paths, source)
    text = out.read_text(encoding="utf-8")
    assert "Real candidate." in text
    assert "Example candidate inside fence." not in text


def test_ingest_ignores_markdown_headings(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    source = paths.root / "export.md"
    source.write_text(
        "## Before\n"
        "- Run ci-check before handoff.\n"
        "## Notes\n",
        encoding="utf-8",
    )

    out = ingest_agents_candidates(paths, source)
    text = out.read_text(encoding="utf-8")
    assert "Run ci-check before handoff." in text
    assert "## Before" not in text
    assert "## Notes" not in text


def test_propose_rejects_generated_agents_memory_proposal_file(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    proposal = paths.root / "docs" / "proposals" / "agents-memory-20260626_120000.md"
    proposal.parent.mkdir(parents=True, exist_ok=True)
    proposal.write_text("# AGENTS.md Memory Proposal\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="not a generated agents-memory proposal"):
        propose_agents_memory(paths, proposal)


def test_propose_rejects_candidates_outside_project_root(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path / "project")
    paths.root.mkdir(parents=True)
    (paths.root / "AGENTS.md").write_text(_minimal_agents(), encoding="utf-8")
    outside = tmp_path / "outside-candidates.md"
    outside.write_text("- New durable operational fact.\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="inside project root"):
        propose_agents_memory(paths, outside)


def test_normalize_candidates_requires_bullets() -> None:
    with pytest.raises(AgentsMemoryError, match="No candidate bullets"):
        normalize_candidates_text("user: hello\nassistant: hi\n")
