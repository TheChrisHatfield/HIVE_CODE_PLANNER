"""Tests for shared graph memory (hook: memory.shared_graph)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.graph_store import (
    GraphStoreError,
    export_tier,
    graph_status,
    offload_from_file,
    promote_staging,
    validate_edge,
    validate_node,
)

FIXTURE = Path(__file__).parent / "fixtures" / "shared-graph" / "sample-bundle.json"


def _paths(tmp_path: Path) -> RepoPaths:
    return RepoPaths(root=tmp_path)


def test_validate_node_rejects_bad_type() -> None:
    with pytest.raises(GraphStoreError, match="Invalid node type"):
        validate_node({"id": "n1", "type": "widget", "label": "x"})


def test_validate_edge_rejects_bad_confidence() -> None:
    with pytest.raises(GraphStoreError, match="confidence"):
        validate_edge(
            {
                "id": "e1",
                "from": "a",
                "to": "b",
                "rel": "supports",
                "confidence": 1.5,
            }
        )


def test_offload_appends_staging(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    result = offload_from_file(paths, FIXTURE)
    assert result.status == "ok"
    assert result.nodes_written == 2
    assert result.edges_written == 1
    staging_nodes = (paths.shared_memory_staging / "nodes.jsonl").read_text(encoding="utf-8")
    assert "n-rosetta" in staging_nodes
    status = graph_status(paths)
    assert status["manifest"]["staging_nodes"] == 2
    assert status["manifest"]["staging_edges"] == 1


def test_promote_moves_to_permanent_and_clears_staging(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    offload_from_file(paths, FIXTURE)
    result = promote_staging(paths)
    assert result.nodes_written == 2
    assert result.edges_written == 1
    assert result.edges_dropped == 0
    permanent = export_tier(paths, "permanent")
    assert {n["id"] for n in permanent["nodes"]} == {"n-rosetta", "n-spec-kit"}
    assert permanent["edges"][0]["status"] == "permanent"
    staging = export_tier(paths, "staging")
    assert staging["nodes"] == []
    assert staging["edges"] == []
    status = graph_status(paths)
    assert status["manifest"]["permanent_nodes"] == 2
    assert status["manifest"]["last_promote"]


def test_promote_skips_duplicate_ids(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    offload_from_file(paths, FIXTURE)
    first = promote_staging(paths)
    first_promote_at = graph_status(paths)["manifest"]["last_promote"]
    assert first_promote_at
    # Force re-queue of already-permanent ids (bypass offload dedupe) to exercise promote skip.
    staging_nodes = paths.shared_memory_staging / "nodes.jsonl"
    staging_edges = paths.shared_memory_staging / "edges.jsonl"
    permanent = export_tier(paths, "permanent")
    staging_nodes.write_text(
        "\n".join(json.dumps(n) for n in permanent["nodes"]) + "\n",
        encoding="utf-8",
    )
    staging_edges.write_text(
        "\n".join(json.dumps(e) for e in permanent["edges"]) + "\n",
        encoding="utf-8",
    )
    result = promote_staging(paths)
    assert result.nodes_written == 0
    assert result.nodes_skipped == 2
    assert result.edges_skipped == 1
    status = graph_status(paths)
    assert status["manifest"]["permanent_nodes"] == 2
    # No-op promote (all duplicates) must not refresh last_promote.
    assert status["manifest"]["last_promote"] == first_promote_at
    assert first.nodes_written == 2


def test_promote_drops_dangling_edge(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    dangling = tmp_path / "dangling.json"
    dangling.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "n-only",
                        "type": "concept",
                        "label": "Only",
                    }
                ],
                "edges": [
                    {
                        "id": "e-dangle",
                        "from": "n-only",
                        "to": "n-missing",
                        "rel": "related_to",
                        "confidence": 0.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    offload_from_file(paths, dangling)
    result = promote_staging(paths)
    assert result.nodes_written == 1
    assert result.edges_written == 0
    assert result.edges_dropped == 1
    assert any("e-dangle" in w for w in result.warnings)
    permanent = export_tier(paths, "permanent")
    assert len(permanent["nodes"]) == 1
    assert permanent["edges"] == []


def test_promote_dry_run_does_not_write(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    offload_from_file(paths, FIXTURE)
    result = promote_staging(paths, dry_run=True)
    assert result.dry_run is True
    assert result.nodes_written == 2
    permanent = export_tier(paths, "permanent")
    assert permanent["nodes"] == []
    staging = export_tier(paths, "staging")
    assert len(staging["nodes"]) == 2


def test_offload_jsonl_kind(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    jsonl = tmp_path / "mixed.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "node",
                        "id": "n-a",
                        "type": "repo",
                        "label": "Repo A",
                    }
                ),
                json.dumps(
                    {
                        "kind": "node",
                        "id": "n-b",
                        "type": "repo",
                        "label": "Repo B",
                    }
                ),
                json.dumps(
                    {
                        "kind": "edge",
                        "id": "e-ab",
                        "from": "n-a",
                        "to": "n-b",
                        "rel": "depends_on",
                        "confidence": 1.0,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    result = offload_from_file(paths, jsonl)
    assert result.nodes_written == 2
    assert result.edges_written == 1


def test_offload_pretty_printed_single_node(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    pretty = tmp_path / "single-node.json"
    pretty.write_text(
        '{\n  "id": "n-pretty",\n  "type": "concept",\n  "label": "Pretty Node"\n}\n',
        encoding="utf-8",
    )
    result = offload_from_file(paths, pretty)
    assert result.nodes_written == 1
    assert result.edges_written == 0
    staging = export_tier(paths, "staging")
    assert staging["nodes"][0]["id"] == "n-pretty"


def test_offload_skips_duplicate_ids_already_in_staging_or_permanent(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    first = offload_from_file(paths, FIXTURE)
    assert first.nodes_written == 2
    assert first.edges_written == 1
    second = offload_from_file(paths, FIXTURE)
    assert second.nodes_written == 0
    assert second.edges_written == 0
    assert second.nodes_skipped == 2
    assert second.edges_skipped == 1
    status = graph_status(paths)
    assert status["manifest"]["staging_nodes"] == 2
    assert status["manifest"]["staging_edges"] == 1

    promote_staging(paths)
    third = offload_from_file(paths, FIXTURE)
    assert third.nodes_written == 0
    assert third.nodes_skipped == 2
    assert graph_status(paths)["manifest"]["staging_nodes"] == 0


def test_promote_skips_corrupt_jsonl_and_promotes_valid(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    offload_from_file(paths, FIXTURE)
    nodes_path = paths.shared_memory_staging / "nodes.jsonl"
    nodes_path.write_text(
        nodes_path.read_text(encoding="utf-8") + "{not-valid-json\n",
        encoding="utf-8",
    )
    result = promote_staging(paths)
    assert result.nodes_written == 2
    assert result.edges_written == 1
    assert any("Invalid JSONL" in w for w in result.warnings)
    permanent = export_tier(paths, "permanent")
    assert {n["id"] for n in permanent["nodes"]} == {"n-rosetta", "n-spec-kit"}


def test_status_tolerates_corrupt_staging_jsonl(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    offload_from_file(paths, FIXTURE)
    nodes_path = paths.shared_memory_staging / "nodes.jsonl"
    nodes_path.write_text(
        nodes_path.read_text(encoding="utf-8") + "{broken\n",
        encoding="utf-8",
    )
    status = graph_status(paths)
    assert status["manifest"]["staging_nodes"] == 2
    assert status["manifest"]["staging_edges"] == 1


def test_offload_jsonl_node_without_type_defaults_other(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    jsonl = tmp_path / "no-type.jsonl"
    jsonl.write_text(
        json.dumps({"id": "n-bare", "label": "Bare Node"}) + "\n",
        encoding="utf-8",
    )
    result = offload_from_file(paths, jsonl)
    assert result.nodes_written == 1
    staging = export_tier(paths, "staging")
    assert staging["nodes"][0]["type"] == "other"
    assert staging["nodes"][0]["id"] == "n-bare"


def test_export_tolerates_corrupt_jsonl(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    offload_from_file(paths, FIXTURE)
    nodes_path = paths.shared_memory_staging / "nodes.jsonl"
    nodes_path.write_text(
        nodes_path.read_text(encoding="utf-8") + "{nope\n",
        encoding="utf-8",
    )
    payload = export_tier(paths, "staging")
    assert len(payload["nodes"]) == 2
    assert len(payload["edges"]) == 1
    assert any("Invalid JSONL" in w for w in payload["warnings"])
