"""Bounded, evidence-backed cross-layer contract detection for bug hunts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CONTRACT_RULE_VERSION = 1
COVERAGE_VERSION = 1
MAX_RELATED_PER_ANCHOR = 8
MAX_RELATED_PER_PASS = 16
CONTRACT_METADATA_LIMIT = 4096
SUPPORTED_SUFFIXES = frozenset({".py", ".cs"})
_SAFE_WITNESSES = ("a", "a-b", "a_b", "a.b", "a b", "1", "é")
_ANNOTATION = re.compile(
    r"""hive-contract:\s*edge=(?P<edge>\S+)\s+key=(?P<key>\S+)\s+
        rule=(?P<rule>\S+)\s+role=(?P<role>upstream|downstream)
        (?:\s+symbol=(?P<symbol>\S+))?""",
    re.IGNORECASE | re.VERBOSE,
)


def _relative(path: object) -> str | None:
    if not isinstance(path, str):
        return None
    value = path.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or ":" in value:
        return None
    parts = value.split("/")
    if any(part in {"", ".."} for part in parts):
        return None
    return "/".join(parts)


def _rule(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.strip().split())
    if not value or len(value) > 512:
        return None
    return value


def _key(value: object, *, case_sensitive: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > 128:
        return None
    return value if case_sensitive else value.casefold()


def _edge_id(
    upstream_path: str,
    downstream_path: str,
    key: str,
    upstream_rule: str,
    downstream_rule: str,
    edge_type: str,
) -> str:
    canonical = "\x1f".join(
        (
            upstream_path.casefold(),
            downstream_path.casefold(),
            key.casefold(),
            upstream_rule,
            downstream_rule,
            edge_type,
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _source_hash(root: Path, paths: Iterable[str]) -> str | None:
    digest = hashlib.sha256()
    try:
        for rel in paths:
            path = root / rel
            data = path.read_bytes()
            digest.update(rel.casefold().encode("utf-8"))
            digest.update(b"\0")
            digest.update(data)
            digest.update(b"\0")
    except (OSError, UnicodeError):
        return None
    return digest.hexdigest()


def _witness(upstream: str, downstream: str) -> str | None:
    """Return a finite counterexample for the supported regex subset."""
    try:
        left = re.compile(upstream)
        right = re.compile(downstream)
    except re.error:
        return None
    for candidate in _SAFE_WITNESSES:
        try:
            if left.fullmatch(candidate) and not right.fullmatch(candidate):
                return candidate
        except (TypeError, re.error):
            return None
    return None


@dataclass(frozen=True)
class ContractFinding:
    coverage_version: int
    edge_id: str
    upstream_path: str
    downstream_path: str
    contract_key: str
    upstream_rule: str
    downstream_rule: str
    edge_type: str
    upstream_symbol: str
    downstream_symbol: str
    witness: str
    source_hash: str

    @property
    def anchor_path(self) -> str:
        return self.upstream_path

    @property
    def related_path(self) -> str:
        return self.downstream_path

    def coverage(self, *, mode: str = "contract") -> dict[str, object]:
        return {
            "coverage_version": self.coverage_version,
            "mode": mode,
            "edge_id": self.edge_id,
            "anchor_path": self.anchor_path,
            "related_path": self.related_path,
            "contract_key": self.contract_key,
            "upstream_rule": self.upstream_rule,
            "downstream_rule": self.downstream_rule,
            "edge_type": self.edge_type,
            "detector_evidence": {
                "upstream_symbol": self.upstream_symbol,
                "downstream_symbol": self.downstream_symbol,
                "witness": self.witness,
                "source_hash": self.source_hash,
                "contract_rule_version": CONTRACT_RULE_VERSION,
            },
        }


def _valid_edge(root: Path, raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict) or raw.get("verified") is not True:
        return None
    upstream = _relative(raw.get("upstream_path"))
    downstream = _relative(raw.get("downstream_path"))
    key = _key(raw.get("contract_key"), case_sensitive=bool(raw.get("case_sensitive_key")))
    upstream_rule = _rule(raw.get("upstream_rule"))
    downstream_rule = _rule(raw.get("downstream_rule"))
    edge_type = _rule(raw.get("edge_type"))
    upstream_symbol = _rule(raw.get("upstream_symbol")) or ""
    downstream_symbol = _rule(raw.get("downstream_symbol")) or ""
    if not all((upstream, downstream, key, upstream_rule, downstream_rule, edge_type)):
        return None
    if Path(upstream).suffix.casefold() not in SUPPORTED_SUFFIXES:
        return None
    if Path(downstream).suffix.casefold() not in SUPPORTED_SUFFIXES:
        return None
    try:
        upstream_file = (root / upstream).resolve()
        downstream_file = (root / downstream).resolve()
        root_resolved = root.resolve()
        upstream_file.relative_to(root_resolved)
        downstream_file.relative_to(root_resolved)
    except (OSError, ValueError):
        return None
    if not upstream_file.is_file() or not downstream_file.is_file():
        return None
    source_hash = _source_hash(root, (upstream, downstream))
    if source_hash is None or (
        raw.get("source_hash") is not None and raw.get("source_hash") != source_hash
    ):
        return None
    return {
        "upstream": upstream,
        "downstream": downstream,
        "key": key,
        "upstream_rule": upstream_rule,
        "downstream_rule": downstream_rule,
        "edge_type": edge_type,
        "upstream_symbol": upstream_symbol,
        "downstream_symbol": downstream_symbol,
        "source_hash": source_hash,
    }


def discover_edges(root: Path, languages: Iterable[str] | None = None) -> list[dict[str, object]]:
    """Discover verified contract annotations from supported source adapters.

    An annotation is explicit evidence from a language adapter, for example:
    ``# hive-contract: edge=feature key=feature_id rule=^[A-Za-z]+$ role=upstream``.
    Unknown syntax and incomplete pairs fail closed.
    """
    root = Path(root)
    wanted = {str(item).casefold() for item in (languages or SUPPORTED_SUFFIXES)}
    records: dict[str, dict[str, dict[str, object]]] = {}
    for base in (root / "src", root):
        if not base.is_dir():
            continue
        try:
            paths = sorted(base.rglob("*"))
        except OSError:
            continue
        for path in paths:
            if not path.is_file() or path.suffix.casefold() not in SUPPORTED_SUFFIXES:
                continue
            if path.suffix.casefold() not in wanted and path.suffix.casefold().lstrip(".") not in wanted:
                continue
            try:
                rel = path.relative_to(root).as_posix()
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError, ValueError):
                continue
            if "/tests/" in f"/{rel}" or rel.startswith("tests/"):
                continue
            for match in _ANNOTATION.finditer(text):
                data = match.groupdict()
                edge = str(data["edge"])
                role = str(data["role"]).casefold()
                records.setdefault(edge, {})[role] = {
                    "path": rel,
                    "key": data["key"],
                    "rule": data["rule"],
                    "symbol": data.get("symbol") or "",
                }
    edges: list[dict[str, object]] = []
    for edge_name, pair in sorted(records.items()):
        upstream = pair.get("upstream")
        downstream = pair.get("downstream")
        if (
            not upstream
            or not downstream
            or str(upstream["key"]).casefold() != str(downstream["key"]).casefold()
        ):
            continue
        edges.append(
            {
                "verified": True,
                "upstream_path": upstream["path"],
                "downstream_path": downstream["path"],
                "contract_key": upstream["key"],
                "upstream_rule": upstream["rule"],
                "downstream_rule": downstream["rule"],
                "edge_type": "annotated-call",
                "upstream_symbol": upstream["symbol"],
                "downstream_symbol": downstream["symbol"],
            }
        )
    return edges


def evaluate_contract(
    edge: object,
    root: Path,
    *,
    contract_rule_version: int = CONTRACT_RULE_VERSION,
) -> ContractFinding | None:
    """Evaluate one adapter edge using the versioned finite witness grammar."""
    if contract_rule_version != CONTRACT_RULE_VERSION:
        return None
    findings = detect_contract_findings(root, [edge])
    return findings[0] if findings else None


def detect_contract_findings(
    root: Path,
    edges: Iterable[object] | None = None,
    *,
    manifest: Path | None = None,
) -> list[ContractFinding]:
    """Return deterministic findings; invalid edges fail closed.

    ``edges`` is the adapter boundary. When omitted, the optional manifest is
    read from `.hive/bug-hunt/contracts.json`.
    """
    root = Path(root)
    if edges is None:
        manifest = manifest or root / ".hive" / "bug-hunt" / "contracts.json"
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, MemoryError):
            payload = {}
        manifest_edges = payload.get("edges", []) if isinstance(payload, dict) else []
        edges = [*manifest_edges, *discover_edges(root)]
        policies = payload.get("policies", []) if isinstance(payload, dict) else []
    else:
        policies = []
    allowed_policies = {
        item.get("edge_id")
        for item in policies
        if isinstance(item, dict) and item.get("version") == 1
    }
    findings: list[ContractFinding] = []
    seen: set[str] = set()
    for raw in edges:
        edge = _valid_edge(root, raw)
        if edge is None:
            continue
        witness = _witness(str(edge["upstream_rule"]), str(edge["downstream_rule"]))
        if witness is None:
            continue
        edge_id = _edge_id(
            str(edge["upstream"]),
            str(edge["downstream"]),
            str(edge["key"]),
            str(edge["upstream_rule"]),
            str(edge["downstream_rule"]),
            str(edge["edge_type"]),
        )
        if edge_id in allowed_policies or edge_id in seen:
            continue
        seen.add(edge_id)
        findings.append(
            ContractFinding(
                coverage_version=COVERAGE_VERSION,
                edge_id=edge_id,
                upstream_path=str(edge["upstream"]),
                downstream_path=str(edge["downstream"]),
                contract_key=str(edge["key"]),
                upstream_rule=str(edge["upstream_rule"]),
                downstream_rule=str(edge["downstream_rule"]),
                edge_type=str(edge["edge_type"]),
                upstream_symbol=str(edge["upstream_symbol"]),
                downstream_symbol=str(edge["downstream_symbol"]),
                witness=witness,
                source_hash=str(edge["source_hash"]),
            )
        )
    findings.sort(key=lambda item: (item.edge_id, item.upstream_path, item.downstream_path))
    return findings


def bounded_neighborhood(findings: Iterable[ContractFinding]) -> dict[str, dict[str, object]]:
    """Build one-hop candidates with deterministic per-anchor/pass bounds."""
    grouped: dict[str, list[ContractFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.anchor_path.casefold(), []).append(finding)
    candidates: list[ContractFinding] = []
    for group in grouped.values():
        candidates.extend(sorted(group, key=lambda item: (item.edge_id, item.related_path))[:MAX_RELATED_PER_ANCHOR])
    candidates.sort(key=lambda item: (item.edge_id, item.related_path))
    result: dict[str, dict[str, object]] = {}
    for finding in candidates:
        if len(result) >= MAX_RELATED_PER_PASS:
            break
        result.setdefault(finding.related_path.casefold(), {
            "file": finding.related_path,
            "signals": {},
            "findings": 1,
            "coverage": finding.coverage(),
            "coverage_bonus": 0.0,
        })
    return result
