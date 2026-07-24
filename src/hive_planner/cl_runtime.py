"""Continual Learning runtime profiles — Cursor plugin vs IDE-agnostic headless path."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CL_RUNTIME_CURSOR = "cursor"
CL_RUNTIME_HEADLESS = "headless"
CL_RUNTIME_EXTERNAL = "external"
CL_RUNTIMES = frozenset({CL_RUNTIME_CURSOR, CL_RUNTIME_HEADLESS, CL_RUNTIME_EXTERNAL})
CL_RUNTIME_MANIFEST = ".hive/cl-runtime.json"
HEADLESS_CL_WORKFLOW_REL = ".hive/continual-learning/WORKFLOW.md"

CURSOR_CL_ARTIFACTS = (
    ".cursor/plugins/hive-continual-learning/README.md",
    ".cursor/plugins/hive-continual-learning/WORKFLOW.md",
    ".cursor/plugins/hive-continual-learning/agents/agents-memory-updater.md",
    ".cursor/plugins/hive-continual-learning/skills/continual-learning/SKILL.md",
    ".cursor/plugins/hive-continual-learning/.cursor-plugin/plugin.json",
    ".cursor/plugins/hive-continual-learning/hooks/hooks.json",
    ".cursor/plugins/hive-continual-learning/hooks/continual-learning-stop.py",
)

HEADLESS_CL_ARTIFACTS = (
    HEADLESS_CL_WORKFLOW_REL,
    CL_RUNTIME_MANIFEST,
)


def normalize_cl_runtime(value: str | None, *, default: str = CL_RUNTIME_CURSOR) -> str:
    runtime = str(value or default).strip().lower()
    if runtime in CL_RUNTIMES:
        return runtime
    if runtime in {"cli", "portable", "agnostic", "none-plugin"}:
        return CL_RUNTIME_HEADLESS
    return default


def requires_cursor_plugin(runtime: str) -> bool:
    return normalize_cl_runtime(runtime) == CL_RUNTIME_CURSOR


def cl_runtime_launcher_choice(current: str) -> str:
    """Map a resolved runtime to the launcher dialog choice (cursor | headless only)."""
    resolved = normalize_cl_runtime(current)
    if resolved == CL_RUNTIME_EXTERNAL:
        return CL_RUNTIME_HEADLESS
    if resolved in {CL_RUNTIME_CURSOR, CL_RUNTIME_HEADLESS}:
        return resolved
    return CL_RUNTIME_CURSOR


def continual_learning_artifact_paths(runtime: str) -> tuple[str, ...]:
    if requires_cursor_plugin(runtime):
        return CURSOR_CL_ARTIFACTS
    return HEADLESS_CL_ARTIFACTS


def read_cl_runtime_manifest(project_root: Path) -> dict | None:
    path = project_root.resolve() / CL_RUNTIME_MANIFEST
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def resolve_cl_runtime(project_root: Path) -> str:
    from hive_planner.project_profile import read_project_profile

    meta = read_project_profile(project_root)
    if meta and meta.cl_runtime:
        return normalize_cl_runtime(meta.cl_runtime)
    manifest = read_cl_runtime_manifest(project_root)
    if manifest and manifest.get("runtime"):
        return normalize_cl_runtime(str(manifest["runtime"]))
    if meta and meta.cl_source:
        return CL_RUNTIME_CURSOR
    return CL_RUNTIME_CURSOR


def _headless_workflow_markdown(runtime: str) -> str:
    runtime_label = "headless (CLI)" if runtime == CL_RUNTIME_HEADLESS else "external IDE"
    return f"""# Continual Learning — {runtime_label}

Hive unified handoff supports Continual Learning without the Cursor plugin.

## Memory loop (IDE-agnostic)

1. Capture learnings in `docs/proposals/candidates.md` (see `docs/proposals/candidates-template.md`).
2. Record wiring audit when enforced (`.cursor/rules/integration-wiring-audit.mdc`).
3. Propose: `py -3.11 -m hive_planner agents-propose --candidates docs/proposals/candidates.md`
4. Review the generated proposal under `docs/proposals/`.
5. Apply: `py -3.11 -m hive_planner agents-apply --candidates docs/proposals/candidates.md`
6. Validate: `py -3.11 -m hive_planner ci-check`

Or ingest exported bullets: `py -3.11 -m hive_planner agents-ingest --from path/to/export.txt`

## Contract

Behavioral truth stays in Spec Kit `docs/specs/<feature>/spec.md`. Operational bullets only in
`AGENTS.md` `## Durable Workspace Facts`. See `docs/cl-spec-integration.md`.

## Switch to Cursor plugin runtime

```powershell
py -3.11 -m hive_planner cl-runtime set cursor
py -3.11 -m hive_planner deploy-handoff
```

Use **Home → Deploy agent handoff** in Hive Planner, or re-run unified bootstrap deploy.
"""


def write_cl_runtime_manifest(project_root: Path, runtime: str) -> Path:
    root = project_root.resolve()
    path = root / CL_RUNTIME_MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "runtime": normalize_cl_runtime(runtime),
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def deploy_headless_cl_artifacts(
    target: Path,
    runtime: str,
    *,
    force: bool = False,
    written: list[str] | None = None,
) -> None:
    normalized = normalize_cl_runtime(runtime, default=CL_RUNTIME_HEADLESS)
    if normalized == CL_RUNTIME_CURSOR:
        raise ValueError("deploy_headless_cl_artifacts requires headless or external runtime")
    root = target.resolve()
    workflow_path = root / HEADLESS_CL_WORKFLOW_REL
    if force or not workflow_path.is_file():
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(_headless_workflow_markdown(normalized), encoding="utf-8")
        if written is not None:
            rel = HEADLESS_CL_WORKFLOW_REL
            if rel not in written:
                written.append(rel)
    manifest_path = write_cl_runtime_manifest(root, normalized)
    if written is not None:
        rel = manifest_path.relative_to(root).as_posix()
        if rel not in written:
            written.append(rel)


def set_project_cl_runtime(project_root: Path, runtime: str) -> Path:
    from hive_planner.agent_handoff import integrations_from_mode, resolve_agent_handoff_mode
    from hive_planner.project_profile import resolve_project_profile, write_project_profile

    normalized = normalize_cl_runtime(runtime)
    root = project_root.resolve()
    existing = resolve_project_profile(root)
    if not existing:
        raise ValueError(f"Not a Hive project: {root}")
    mode = existing.agent_handoff_mode
    spec_kit = existing.spec_kit_enabled
    cl_enabled = existing.continual_learning_enabled
    if mode is None:
        mode = resolve_agent_handoff_mode(root)
    if spec_kit is None or cl_enabled is None:
        inferred_spec, inferred_cl = integrations_from_mode(mode)
        if spec_kit is None:
            spec_kit = inferred_spec
        if cl_enabled is None:
            cl_enabled = inferred_cl
    write_cl_runtime_manifest(root, normalized)
    return write_project_profile(
        root,
        profile=existing.bootstrap_profile,
        project_name=existing.project_name,
        hive_planner_version=existing.hive_planner_version,
        agent_handoff_mode=mode,
        spec_kit_enabled=spec_kit,
        continual_learning_enabled=cl_enabled,
        cl_source=existing.cl_source,
        cl_runtime=normalized,
    )
