from __future__ import annotations

import json
import shutil
from pathlib import Path

from hive_planner.bug_hunt import advance_rank_pass, render_agent_prompt
from hive_planner.contract_adaptation import (
    MAX_RELATED_PER_ANCHOR,
    MAX_RELATED_PER_PASS,
    bounded_neighborhood,
    discover_edges,
    detect_contract_findings,
    evaluate_contract,
)


def _edge(upstream: str, downstream: str, *, key: str = "feature_id") -> dict[str, object]:
    return {
        "verified": True,
        "upstream_path": upstream,
        "downstream_path": downstream,
        "contract_key": key,
        "upstream_rule": r"^[A-Za-z0-9_-]+$",
        "downstream_rule": r"^[A-Za-z0-9_]+$",
        "edge_type": "call",
        "upstream_symbol": "validate",
        "downstream_symbol": "validate",
    }


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "ui.py").write_text("def validate(value):\n    return value\n", encoding="utf-8")
    (root / "src" / "impl.py").write_text("def validate(value):\n    return value\n", encoding="utf-8")
    return root


def test_contract_finding_has_witness_and_stable_edge_id(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    findings = detect_contract_findings(root, [_edge("src/ui.py", "src/impl.py")])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.witness == "a-b"
    assert len(finding.edge_id) == 24
    assert finding.coverage()["detector_evidence"]["contract_rule_version"] == 1


def test_policy_and_stale_edges_fail_closed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    raw = _edge("src/ui.py", "src/impl.py")
    first = detect_contract_findings(root, [raw])[0]
    manifest = root / ".hive" / "bug-hunt"
    manifest.mkdir(parents=True)
    (manifest / "contracts.json").write_text(
        json.dumps({"edges": [raw], "policies": [{"version": 1, "edge_id": first.edge_id}]}),
        encoding="utf-8",
    )
    assert detect_contract_findings(root) == []
    stale_raw = dict(raw)
    stale_raw["source_hash"] = first.source_hash
    root.joinpath("src", "impl.py").write_text("changed\n", encoding="utf-8")
    assert detect_contract_findings(root, [stale_raw]) == []


def test_neighborhood_is_deduplicated_and_bounded(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    findings = []
    for i in range(MAX_RELATED_PER_PASS + 3):
        path = root / "src" / f"impl_{i}.py"
        path.write_text("def validate(value):\n    return value\n", encoding="utf-8")
        findings.extend(
            detect_contract_findings(
                root, [_edge("src/ui.py", path.relative_to(root).as_posix(), key=f"k{i}")]
            )
        )
    neighborhood = bounded_neighborhood(findings)
    assert len(neighborhood) <= MAX_RELATED_PER_PASS
    assert MAX_RELATED_PER_ANCHOR == 8


def test_prompt_describes_r12_runtime_path() -> None:
    prompt = render_agent_prompt(1)
    assert "R12 contract adaptation" in prompt
    assert "4 KiB of UTF-8 JSON" in prompt


def test_fixture_adapter_discovers_python_contract_edge() -> None:
    root = Path(__file__).parent / "fixtures" / "bug_hunt" / "contract_mismatch"
    assert len(discover_edges(root, languages={"py"})) == 1
    findings = detect_contract_findings(root)
    assert len(findings) == 1
    assert findings[0].related_path == "src/implementation_loop.py"


def test_adapter_normalizes_contract_key_case(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "src" / "ui.py").write_text(
        "# hive-contract: edge=feature-flow key=Feature_ID "
        "rule=^[A-Za-z0-9_-]+$ role=upstream\n",
        encoding="utf-8",
    )
    (root / "src" / "impl.py").write_text(
        "# hive-contract: edge=feature-flow key=feature_id "
        "rule=^[A-Za-z0-9_]+$ role=downstream\n",
        encoding="utf-8",
    )
    assert len(discover_edges(root, languages={"py"})) == 1
    assert len(detect_contract_findings(root)) == 1


def test_fixture_adapter_discovers_csharp_contract_edge() -> None:
    root = Path(__file__).parent / "fixtures" / "bug_hunt" / "contract_mismatch_csharp"
    assert len(discover_edges(root, languages={"cs"})) == 1
    assert len(detect_contract_findings(root)) == 1


def test_unsupported_rule_version_and_language_fail_closed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    edge = _edge("src/ui.py", "src/impl.py")
    assert evaluate_contract(edge, root, contract_rule_version=2) is None
    assert discover_edges(root, languages={"js"}) == []


def test_contract_finding_reaches_rank_queue(tmp_path: Path) -> None:
    source = Path(__file__).parent / "fixtures" / "bug_hunt" / "contract_mismatch"
    root = tmp_path / "repo"
    shutil.copytree(source, root)
    result = advance_rank_pass(
        root,
        fresh=True,
        files=[root / "src" / "ui.py", root / "src" / "implementation_loop.py"],
    )
    assert result["top"] == "src/implementation_loop.py"
