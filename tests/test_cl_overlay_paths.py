from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_cl_overlay_doc_links_resolve_from_deploy_paths() -> None:
    """CL plugin files live under .cursor/plugins/ — links must reach repo root, not .cursor/."""
    root = _repo_root()
    overlay = root / "src" / "hive_planner" / "vendor_templates" / "continual-learning"
    contract = root / "docs" / "cl-spec-integration.md"
    assert contract.is_file()

    cases = (
        (overlay / "README.md", "../../../../docs/cl-spec-integration.md"),
        (overlay / "WORKFLOW.md", "../../../../docs/cl-spec-integration.md"),
        (overlay / "agents" / "agents-memory-updater.md", "../../../../../docs/cl-spec-integration.md"),
        (overlay / "skills" / "continual-learning" / "SKILL.md", "../../../../../../docs/cl-spec-integration.md"),
    )
    for doc_path, rel_link in cases:
        text = doc_path.read_text(encoding="utf-8")
        assert rel_link in text, f"{doc_path.name} missing expected link {rel_link!r}"
        assert (doc_path.parent / rel_link).resolve() == contract.resolve()
