"""Shared graph memory stores (hook: memory.shared_graph, representation.graph_native)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from hive_planner.config import RepoPaths

SCHEMA_VERSION = "shared-graph.v1"

NODE_TYPES = frozenset({"concept", "spec", "heuristic", "repo", "agent", "paper", "other"})
EDGE_RELS = frozenset({"supports", "contradicts", "depends_on", "derived_from", "related_to"})
STATUSES = frozenset({"staging", "permanent"})
Tier = Literal["staging", "permanent"]


class GraphStoreError(Exception):
    """Shared graph memory operation failed."""


@dataclass
class GraphOperationResult:
    status: str
    nodes_written: int = 0
    edges_written: int = 0
    nodes_skipped: int = 0
    edges_skipped: int = 0
    edges_dropped: int = 0
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "nodes_written": self.nodes_written,
            "edges_written": self.edges_written,
            "nodes_skipped": self.nodes_skipped,
            "edges_skipped": self.edges_skipped,
            "edges_dropped": self.edges_dropped,
            "warnings": self.warnings,
            "dry_run": self.dry_run,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_provenance() -> dict[str, Any]:
    return {
        "source_repo": "",
        "source_path": "",
        "feature": "",
        "created_at": _utc_now(),
    }


def _normalize_provenance(raw: Any) -> dict[str, Any]:
    base = _empty_provenance()
    if not isinstance(raw, dict):
        return base
    for key in ("source_repo", "source_path", "feature", "created_at"):
        val = raw.get(key)
        if val is None:
            continue
        base[key] = str(val)
    if not base["created_at"]:
        base["created_at"] = _utc_now()
    return base


def validate_node(obj: dict[str, Any], *, default_status: str = "staging") -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise GraphStoreError("Node must be a JSON object")
    node_id = obj.get("id")
    if not isinstance(node_id, str) or not node_id.strip():
        raise GraphStoreError("Node requires non-empty string id")
    node_type = obj.get("type", "other")
    if node_type not in NODE_TYPES:
        raise GraphStoreError(f"Invalid node type '{node_type}' for id={node_id}")
    label = obj.get("label", node_id)
    if not isinstance(label, str) or not label.strip():
        raise GraphStoreError(f"Node {node_id} requires non-empty label")
    properties = obj.get("properties", {})
    if properties is None:
        properties = {}
    if not isinstance(properties, dict):
        raise GraphStoreError(f"Node {node_id} properties must be an object")
    status = obj.get("status", default_status)
    if status not in STATUSES:
        raise GraphStoreError(f"Invalid node status '{status}' for id={node_id}")
    return {
        "id": node_id.strip(),
        "type": node_type,
        "label": label.strip(),
        "properties": properties,
        "provenance": _normalize_provenance(obj.get("provenance")),
        "status": status,
    }


def validate_edge(obj: dict[str, Any], *, default_status: str = "staging") -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise GraphStoreError("Edge must be a JSON object")
    edge_id = obj.get("id")
    if not isinstance(edge_id, str) or not edge_id.strip():
        raise GraphStoreError("Edge requires non-empty string id")
    frm = obj.get("from")
    to = obj.get("to")
    if not isinstance(frm, str) or not frm.strip():
        raise GraphStoreError(f"Edge {edge_id} requires non-empty 'from'")
    if not isinstance(to, str) or not to.strip():
        raise GraphStoreError(f"Edge {edge_id} requires non-empty 'to'")
    rel = obj.get("rel")
    if rel not in EDGE_RELS:
        raise GraphStoreError(f"Invalid edge rel '{rel}' for id={edge_id}")
    confidence = obj.get("confidence", 1.0)
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise GraphStoreError(f"Edge {edge_id} confidence must be a number")
    confidence_f = float(confidence)
    if confidence_f < 0.0 or confidence_f > 1.0:
        raise GraphStoreError(f"Edge {edge_id} confidence must be between 0 and 1")
    status = obj.get("status", default_status)
    if status not in STATUSES:
        raise GraphStoreError(f"Invalid edge status '{status}' for id={edge_id}")
    return {
        "id": edge_id.strip(),
        "from": frm.strip(),
        "to": to.strip(),
        "rel": rel,
        "confidence": confidence_f,
        "provenance": _normalize_provenance(obj.get("provenance")),
        "status": status,
    }


def _jsonl_path(paths: RepoPaths, tier: Tier, kind: Literal["nodes", "edges"]) -> Path:
    base = paths.shared_memory_staging if tier == "staging" else paths.shared_memory_permanent
    return base / f"{kind}.jsonl"


def _read_jsonl(
    path: Path,
    *,
    on_error: Literal["raise", "skip"] = "raise",
) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        return [], []
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSONL in {path.name} line {line_no}: {exc}"
            if on_error == "skip":
                warnings.append(msg)
                continue
            raise GraphStoreError(msg) from exc
        if not isinstance(obj, dict):
            msg = f"JSONL row must be object in {path.name} line {line_no}"
            if on_error == "skip":
                warnings.append(msg)
                continue
            raise GraphStoreError(msg)
        rows.append(obj)
    return rows, warnings


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_tier(
    paths: RepoPaths,
    tier: Tier,
    *,
    on_error: Literal["raise", "skip"] = "raise",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    nodes, node_warnings = _read_jsonl(_jsonl_path(paths, tier, "nodes"), on_error=on_error)
    edges, edge_warnings = _read_jsonl(_jsonl_path(paths, tier, "edges"), on_error=on_error)
    return nodes, edges, node_warnings + edge_warnings


def load_manifest(paths: RepoPaths) -> dict[str, Any]:
    path = paths.shared_memory_manifest
    if not path.is_file():
        return {
            "schema_version": SCHEMA_VERSION,
            "staging_nodes": 0,
            "staging_edges": 0,
            "permanent_nodes": 0,
            "permanent_edges": 0,
            "last_promote": None,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GraphStoreError(f"Invalid manifest JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise GraphStoreError("Manifest must be a JSON object")
    return data


def write_manifest(paths: RepoPaths, manifest: dict[str, Any]) -> None:
    paths.ensure_shared_memory_dirs()
    paths.shared_memory_manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def refresh_manifest_counts(paths: RepoPaths, *, last_promote: str | None = None) -> dict[str, Any]:
    # Count valid rows only — corrupt JSONL must not block status/offload refresh.
    staging_nodes, staging_edges, _ = load_tier(paths, "staging", on_error="skip")
    permanent_nodes, permanent_edges, _ = load_tier(paths, "permanent", on_error="skip")
    manifest = load_manifest(paths)
    manifest["schema_version"] = SCHEMA_VERSION
    manifest["staging_nodes"] = len(staging_nodes)
    manifest["staging_edges"] = len(staging_edges)
    manifest["permanent_nodes"] = len(permanent_nodes)
    manifest["permanent_edges"] = len(permanent_edges)
    if last_promote is not None:
        manifest["last_promote"] = last_promote
    write_manifest(paths, manifest)
    return manifest


def parse_offload_input(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.is_file():
        raise GraphStoreError(f"Input file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return [], []

    # Prefer JSON bundle when file parses as a single object/array.
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    if isinstance(data, dict) and ("nodes" in data or "edges" in data):
        raw_nodes = data.get("nodes") or []
        raw_edges = data.get("edges") or []
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise GraphStoreError("Bundle nodes/edges must be arrays")
        for item in raw_nodes:
            nodes.append(validate_node(item, default_status="staging"))
        for item in raw_edges:
            edges.append(validate_edge(item, default_status="staging"))
        return nodes, edges

    # Pretty-printed or compact single record (not a bundle, not JSONL).
    if isinstance(data, dict):
        kind = data.get("kind")
        if kind == "node" or (
            "id" in data
            and "from" not in data
            and "to" not in data
            and "rel" not in data
        ):
            payload = {k: v for k, v in data.items() if k != "kind"}
            return [validate_node(payload, default_status="staging")], []
        if kind == "edge" or ("from" in data and "to" in data and "rel" in data):
            payload = {k: v for k, v in data.items() if k != "kind"}
            return [], [validate_edge(payload, default_status="staging")]
        raise GraphStoreError(
            "JSON object must be a {nodes,edges} bundle, a node, or an edge "
            "(set kind to 'node'/'edge' or include required fields)"
        )

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                raise GraphStoreError("List input must contain objects")
            kind = item.get("kind")
            looks_like_node = (
                "id" in item
                and "from" not in item
                and "to" not in item
                and "rel" not in item
            )
            looks_like_edge = "from" in item and "to" in item and "rel" in item
            if kind == "node" or (kind is None and looks_like_node):
                payload = {k: v for k, v in item.items() if k != "kind"}
                nodes.append(validate_node(payload, default_status="staging"))
            elif kind == "edge" or (kind is None and looks_like_edge):
                payload = {k: v for k, v in item.items() if k != "kind"}
                edges.append(validate_edge(payload, default_status="staging"))
            else:
                raise GraphStoreError("List items require kind 'node' or 'edge' (or node/edge fields)")
        return nodes, edges

    # JSONL (mixed or single-kind via kind field)
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise GraphStoreError(f"Invalid JSONL line {line_no}: {exc}") from exc
        if not isinstance(item, dict):
            raise GraphStoreError(f"JSONL line {line_no} must be an object")
        kind = item.get("kind")
        looks_like_node = (
            "id" in item
            and "from" not in item
            and "to" not in item
            and "rel" not in item
        )
        looks_like_edge = "from" in item and "to" in item and "rel" in item
        if kind == "node" or (kind is None and looks_like_node):
            payload = {k: v for k, v in item.items() if k != "kind"}
            nodes.append(validate_node(payload, default_status="staging"))
        elif kind == "edge" or (kind is None and looks_like_edge):
            payload = {k: v for k, v in item.items() if k != "kind"}
            edges.append(validate_edge(payload, default_status="staging"))
        else:
            raise GraphStoreError(
                f"JSONL line {line_no}: set kind to 'node' or 'edge', or include required fields"
            )
    return nodes, edges


def offload_from_file(paths: RepoPaths, source: Path) -> GraphOperationResult:
    paths.ensure_shared_memory_dirs()
    nodes, edges = parse_offload_input(source)
    for node in nodes:
        node["status"] = "staging"
    for edge in edges:
        edge["status"] = "staging"
    if nodes:
        _append_jsonl(_jsonl_path(paths, "staging", "nodes"), nodes)
    if edges:
        _append_jsonl(_jsonl_path(paths, "staging", "edges"), edges)
    refresh_manifest_counts(paths)
    return GraphOperationResult(
        status="ok",
        nodes_written=len(nodes),
        edges_written=len(edges),
    )


def promote_staging(paths: RepoPaths, *, dry_run: bool = False) -> GraphOperationResult:
    paths.ensure_shared_memory_dirs()
    staging_nodes, staging_edges, load_warnings = load_tier(paths, "staging", on_error="skip")
    permanent_nodes, permanent_edges, perm_warnings = load_tier(
        paths, "permanent", on_error="skip"
    )

    permanent_node_ids = {n["id"] for n in permanent_nodes if isinstance(n.get("id"), str)}
    permanent_edge_ids = {e["id"] for e in permanent_edges if isinstance(e.get("id"), str)}

    result = GraphOperationResult(status="ok", dry_run=dry_run)
    result.warnings.extend(load_warnings)
    result.warnings.extend(perm_warnings)
    promote_nodes: list[dict[str, Any]] = []
    batch_ids = set(permanent_node_ids)

    for raw in staging_nodes:
        try:
            node = validate_node(raw, default_status="staging")
        except GraphStoreError as exc:
            result.nodes_skipped += 1
            result.warnings.append(f"skip invalid staging node: {exc}")
            continue
        if node["id"] in permanent_node_ids or node["id"] in {n["id"] for n in promote_nodes}:
            result.nodes_skipped += 1
            continue
        node["status"] = "permanent"
        promote_nodes.append(node)
        batch_ids.add(node["id"])

    promote_edges: list[dict[str, Any]] = []
    for raw in staging_edges:
        try:
            edge = validate_edge(raw, default_status="staging")
        except GraphStoreError as exc:
            result.edges_skipped += 1
            result.warnings.append(f"skip invalid staging edge: {exc}")
            continue
        if edge["id"] in permanent_edge_ids or edge["id"] in {e["id"] for e in promote_edges}:
            result.edges_skipped += 1
            continue
        if edge["from"] not in batch_ids or edge["to"] not in batch_ids:
            result.edges_dropped += 1
            result.warnings.append(
                f"drop edge {edge['id']}: missing endpoint "
                f"(from={edge['from']} to={edge['to']})"
            )
            continue
        edge["status"] = "permanent"
        promote_edges.append(edge)

    result.nodes_written = len(promote_nodes)
    result.edges_written = len(promote_edges)

    if dry_run:
        return result

    if promote_nodes:
        _append_jsonl(_jsonl_path(paths, "permanent", "nodes"), promote_nodes)
    if promote_edges:
        _append_jsonl(_jsonl_path(paths, "permanent", "edges"), promote_edges)

    # Staging is a queue: clear after successful promote (promoted + handled rows consumed).
    nodes_path = _jsonl_path(paths, "staging", "nodes")
    edges_path = _jsonl_path(paths, "staging", "edges")
    nodes_path.write_text("", encoding="utf-8")
    edges_path.write_text("", encoding="utf-8")

    # Only stamp last_promote when something actually landed in permanent.
    last_promote = _utc_now() if (promote_nodes or promote_edges) else None
    refresh_manifest_counts(paths, last_promote=last_promote)
    return result


def graph_status(paths: RepoPaths) -> dict[str, Any]:
    paths.ensure_shared_memory_dirs()
    manifest = refresh_manifest_counts(paths)
    return {
        "schema_version": SCHEMA_VERSION,
        "root": str(paths.root),
        "shared_memory": str(paths.shared_memory.relative_to(paths.root)).replace("\\", "/"),
        "manifest": manifest,
    }


def export_tier(paths: RepoPaths, tier: Tier) -> dict[str, Any]:
    if tier not in ("staging", "permanent"):
        raise GraphStoreError(f"Invalid tier '{tier}'")
    paths.ensure_shared_memory_dirs()
    nodes, edges, warnings = load_tier(paths, tier, on_error="skip")
    return {
        "schema_version": SCHEMA_VERSION,
        "tier": tier,
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
    }
