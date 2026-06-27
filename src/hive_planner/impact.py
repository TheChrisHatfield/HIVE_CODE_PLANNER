from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hive_planner.config import RepoPaths, validate_feature_id
from hive_planner.call_graph import build_package_graph, secondary_call_targets


class ImpactError(Exception):
    """Impact packet generation failed."""


@dataclass
class ImpactTarget:
    path: str
    level: str
    reason: str


@dataclass
class ImpactPacket:
    packet_id: str
    feature: str
    hook_ids: list[str]
    primary: list[ImpactTarget] = field(default_factory=list)
    secondary: list[ImpactTarget] = field(default_factory=list)
    tertiary: list[ImpactTarget] = field(default_factory=list)
    risk_score: str = "low"
    validations: list[str] = field(default_factory=list)
    mode: str = "default"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


def _feature_spec_dir(paths: RepoPaths, feature: str) -> Path:
    return paths.root / "docs" / "specs" / feature


def _parse_test_map(paths: RepoPaths) -> dict[str, list[str]]:
    test_map_path = paths.root / "docs" / "change-impact" / "test-map.md"
    if not test_map_path.exists():
        return {}

    mapping: dict[str, list[str]] = {}
    for line in test_map_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `src/"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 2:
            continue
        module = parts[0].strip("`")
        tests_cell = parts[1]
        tests = [t.strip().strip("`") for t in tests_cell.split(",")]
        mapping[module] = [t for t in tests if t]
    return mapping


def _normalize_repo_path(paths: RepoPaths, file_path: Path) -> str:
    resolved = file_path.resolve()
    try:
        rel = resolved.relative_to(paths.root.resolve())
        return rel.as_posix()
    except ValueError:
        return resolved.as_posix()


def _tests_for_src_path(repo_path: str, test_map: dict[str, list[str]]) -> list[str]:
    if repo_path in test_map:
        return list(test_map[repo_path])
    tests: set[str] = set()
    for module, module_tests in test_map.items():
        if repo_path.startswith(f"{module}/"):
            tests.update(module_tests)
    return sorted(tests)


def _hook_ids_for_feature(feature: str) -> list[str]:
    hooks = ["change.impact", "change.levels", "change.validation"]
    if feature.startswith("cartridge-compiler"):
        hooks.extend(["compiler.pipeline", "context.document_sourcing"])
    if feature.startswith("cartridge-translator"):
        hooks.extend(["context.cartridge", "context.cartridge_schema", "compiler.pipeline"])
    if feature.startswith("agents-memory"):
        hooks.extend(["automation.ci_memory", "memory.agents_md", "workflow.git_handoff"])
    if feature.startswith("embedding-retrieval"):
        hooks.extend(["compiler.pipeline", "context.library"])
    if feature.startswith("cartridge-delta-emit"):
        hooks.extend(["context.cartridge", "context.delta", "compiler.pipeline"])
    if feature.startswith("change-impact"):
        hooks.append("next.files")
    if feature.startswith("git-handoff-ci"):
        hooks.extend(["workflow.git_handoff", "automation.ci_memory", "change.validation"])
    if feature.startswith("cartridge-pack"):
        hooks.extend(["context.cartridge", "context.cartridge_schema", "compiler.pipeline"])
    if feature.startswith("roadmap-complete"):
        hooks.extend(["workflow.tools", "workflow.blueprint_first", "change.validation"])
    if feature.startswith("project-bootstrap") or feature.startswith("starter-kit"):
        hooks.extend(["workflow.project_bootstrap", "repo.starter_files"])
    return hooks


def _classify_path(repo_path: str) -> tuple[str, str]:
    if repo_path.startswith("src/"):
        return "primary", "Direct source edit target"
    if repo_path.startswith("tests/"):
        return "secondary", "Test file connected to source behavior"
    if repo_path.startswith("docs/delta/"):
        return "tertiary", "Delta doc — architecture/mission alignment impact"
    if repo_path.startswith("docs/specs/"):
        return "tertiary", "Spec artifact — behavioral contract may need update"
    if repo_path.startswith("docs/"):
        return "tertiary", "Documentation reference impact"
    return "secondary", "Repo artifact connected to change scope"


def build_impact_packet(
    paths: RepoPaths,
    feature: str,
    files: list[Path],
    *,
    mode: str = "default",
    deep: bool = False,
) -> ImpactPacket:
    if mode not in {"default", "bugfix"}:
        raise ImpactError(f"Unknown impact mode '{mode}' — use default or bugfix")

    try:
        feature = validate_feature_id(feature)
    except ValueError as exc:
        raise ImpactError(str(exc)) from exc

    spec_dir = _feature_spec_dir(paths, feature)
    spec_file = spec_dir / "spec.md"
    if not spec_file.is_file():
        rel = spec_file.relative_to(paths.root)
        raise ImpactError(f"Unknown feature '{feature}' — missing {rel.as_posix()}")

    if not files:
        raise ImpactError("At least one --files path is required")

    test_map = _parse_test_map(paths)
    packet_id = f"chg_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{feature}"

    repo_paths: list[str] = []
    for file_path in files:
        repo_path = _normalize_repo_path(paths, file_path)
        if repo_path not in repo_paths:
            repo_paths.append(repo_path)

    use_graph = (mode == "bugfix" or deep) and any(p.startswith("src/") for p in repo_paths)
    graph = build_package_graph(paths) if use_graph else None

    packet = ImpactPacket(
        packet_id=packet_id,
        feature=feature,
        hook_ids=_hook_ids_for_feature(feature),
        mode=mode,
    )
    if mode == "bugfix" and "change.bugfix_mode" not in packet.hook_ids:
        packet.hook_ids.append("change.bugfix_mode")

    src_count = 0
    seen_tests: set[str] = set()
    seen_targets: set[str] = set()

    for repo_path in repo_paths:
        if repo_path in seen_targets:
            continue
        seen_targets.add(repo_path)
        level, reason = _classify_path(repo_path)
        target = ImpactTarget(path=repo_path, level=level, reason=reason)
        if level == "primary":
            packet.primary.append(target)
            src_count += 1
            for test_path in _tests_for_src_path(repo_path, test_map):
                if test_path in seen_tests:
                    continue
                seen_tests.add(test_path)
                packet.secondary.append(
                    ImpactTarget(
                        path=test_path,
                        level="secondary",
                        reason=f"Mapped test for {repo_path}",
                    )
                )
            if graph and repo_path.startswith("src/"):
                for caller_path, reason in secondary_call_targets(graph, repo_path):
                    if caller_path in seen_targets:
                        continue
                    seen_targets.add(caller_path)
                    packet.secondary.append(
                        ImpactTarget(path=caller_path, level="secondary", reason=reason)
                    )
                    for test_path in _tests_for_src_path(caller_path, test_map):
                        if test_path in seen_tests:
                            continue
                        seen_tests.add(test_path)
                        packet.secondary.append(
                            ImpactTarget(
                                path=test_path,
                                level="secondary",
                                reason=f"Mapped regression test for caller {caller_path}",
                            )
                        )
        elif level == "secondary":
            packet.secondary.append(target)
        else:
            packet.tertiary.append(target)

    packet.validations = ["Run mapped pytest targets", "Re-run hive_planner ingest/emit if compiler paths changed"]
    if packet.tertiary:
        packet.validations.append("Review Delta/spec docs for consistency")
    if use_graph:
        packet.validations.append("Review call-graph secondary targets before editing")
    if mode == "bugfix":
        packet.validations.extend(
            [
                "Identify failing symptom and causal chain before patching",
                "Run mapped regression tests for primary and caller modules",
                "Avoid overfitting fix to one symptom — check secondary call sites",
            ]
        )
        packet.risk_score = "medium"
    if src_count > 1 and packet.risk_score == "low":
        packet.risk_score = "medium"
    if packet.tertiary and src_count:
        packet.risk_score = "medium-high"
    elif packet.tertiary and mode != "bugfix":
        packet.risk_score = "medium"

    return packet


def write_impact_packet(paths: RepoPaths, packet: ImpactPacket) -> Path:
    out_dir = paths.root / "docs" / "change-impact" / "impact-packets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{packet.packet_id}.json"
    out_path.write_text(json.dumps(packet.to_dict(), indent=2), encoding="utf-8")
    return out_path


def load_latest_impact_packet(paths: RepoPaths, feature: str | None = None) -> tuple[ImpactPacket | None, str | None]:
    packet_dir = paths.root / "docs" / "change-impact" / "impact-packets"
    if not packet_dir.exists():
        return None, None

    candidates = sorted(
        packet_dir.glob("chg_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    errors: list[str] = []
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if feature and data.get("feature") != feature:
                continue
            packet = ImpactPacket(
                packet_id=data["packet_id"],
                feature=data["feature"],
                hook_ids=list(data.get("hook_ids", [])),
                primary=[ImpactTarget(**t) for t in data.get("primary", [])],
                secondary=[ImpactTarget(**t) for t in data.get("secondary", [])],
                tertiary=[ImpactTarget(**t) for t in data.get("tertiary", [])],
                risk_score=data.get("risk_score", "low"),
                validations=list(data.get("validations", [])),
                mode=data.get("mode", "default"),
                created_at=data.get("created_at", ""),
            )
            return packet, None
        except (json.JSONDecodeError, OSError, TypeError, KeyError) as exc:
            errors.append(f"Invalid impact packet {path.name}: {exc}")
            continue
    if errors:
        return None, errors[0]
    return None, None


def impact_warnings(paths: RepoPaths, feature: str | None = None) -> list[str]:
    packet_dir = paths.root / "docs" / "change-impact" / "impact-packets"
    if not packet_dir.exists():
        return []

    warnings: list[str] = []
    candidates = sorted(
        packet_dir.glob("chg_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            warnings.append(f"Invalid impact packet {path.name}: {exc}")
            continue
        if feature and data.get("feature") != feature:
            continue
        return warnings

    return warnings
