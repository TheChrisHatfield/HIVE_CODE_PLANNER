"""Home action groups: headings, saved order, and arrange-mode moves."""

from __future__ import annotations

from typing import Any

MAX_GROUP_TITLE = 40

HOME_ACTIONS: dict[str, dict[str, Any]] = {
    "ci_check": {
        "label": "Run health check",
        "primary": True,
        "tooltip": "Check that plans, specs, and code maps match before you hand work to an AI agent.",
    },
    "open_cursor": {
        "label": "Open in Cursor",
        "primary": False,
        "tooltip": "Open your active linked project in the Cursor editor.",
    },
    "map_sync": {
        "label": "Sync impact maps",
        "primary": False,
        "tooltip": "Refresh the lists that link source files to tests so you know what to re-test after edits.",
    },
    "deploy_handoff": {
        "label": "Deploy agent handoff",
        "primary": False,
        "tooltip": "Copy planning and memory tools into your project so AI agents can follow your workflow.",
    },
    "load_cartridge": {
        "label": "Load cartridge…",
        "primary": False,
        "tooltip": "Open the dialog to add reference files, turn a research note into drafts, or import a cartridge folder.",
    },
    "explore": {
        "label": "Open in Explorer",
        "primary": False,
        "tooltip": "Open your active project folder in Windows File Explorer.",
    },
    "loop_controls": {
        "label": "Loop controls",
        "primary": False,
        "tooltip": "Open the Controls tab: CodeSpec, bug hunt, and agnostic loop on the active repo. Add more than one loop block.",
    },
    "codespec": {
        "label": "CodeSpec",
        "primary": False,
        "tooltip": "Open Controls on a CodeSpec block. CodeSpec codes a finished spec through Enable, Start, Handoff, Check, Accept, and Commit. Loop controls still opens the same tab.",
    },
    "load_sources": {
        "label": "Load Sources…",
        "primary": False,
        "tooltip": "Add PDF or text files (notes, papers, specs) for AI agents to reference while planning.",
    },
    "wiring_check": {
        "label": "Check wiring audit",
        "primary": False,
        "tooltip": "See whether required integration checks were completed before agent handoff.",
    },
    "wiring_record": {
        "label": "Record wiring audit…",
        "primary": False,
        "tooltip": "Mark integration checks as done after you verify agents and tools are connected correctly.",
    },
    "promote_memory": {
        "label": "Promote memory…",
        "primary": False,
        "tooltip": "Autonomously route and apply candidates to AGENTS.md (auto-splits long bullets; no preview).",
    },
    "apply_memory": {
        "label": "Apply memory…",
        "primary": False,
        "tooltip": "Re-run autonomous apply on a candidates file (same routing as Promote memory).",
    },
    "verify_pins": {
        "label": "Verify vendor pins",
        "primary": False,
        "tooltip": "Confirm bundled planning tool versions match what this Hive release expects.",
    },
    "scan_legacy": {
        "label": "Scan legacy deployment",
        "primary": False,
        "tooltip": "Find older project setups that may need upgrading to the current agent handoff format.",
    },
    "set_cl_runtime": {
        "label": "Set CL runtime…",
        "primary": False,
        "tooltip": "Choose how AI memory runs: inside Cursor, or through a separate command-line tool.",
    },
    "migrate_cl": {
        "label": "Migrate marketplace CL…",
        "primary": False,
        "tooltip": "Move learned facts from the Cursor plugin into your project's own memory file.",
    },
}

DEFAULT_HOME_GROUPS: list[dict[str, Any]] = [
    {
        "id": "project",
        "title": "Project",
        "actions": [
            "ci_check",
            "open_cursor",
            "map_sync",
            "deploy_handoff",
            "load_cartridge",
            "explore",
        ],
    },
    {"id": "loops", "title": "Loops", "actions": ["loop_controls", "codespec"]},
    {"id": "sources", "title": "Sources", "actions": ["load_sources"]},
    {
        "id": "memory",
        "title": "Memory",
        "actions": ["wiring_check", "wiring_record", "promote_memory", "apply_memory"],
    },
    {
        "id": "setup",
        "title": "Setup",
        "actions": ["verify_pins", "scan_legacy", "set_cl_runtime", "migrate_cl"],
    },
]


def default_home_groups() -> list[dict[str, Any]]:
    return [
        {"id": str(group["id"]), "title": str(group["title"]), "actions": list(group["actions"])}
        for group in DEFAULT_HOME_GROUPS
    ]


def _clean_title(value: object, fallback: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return fallback
    return text[:MAX_GROUP_TITLE]


def normalize_home_groups(raw: object) -> list[dict[str, Any]]:
    """Keep known actions exactly once. Unknown ids drop. Missing ids append to the last group."""
    known = list(HOME_ACTIONS)
    known_set = set(known)
    groups: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(raw, list):
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            group_id = str(item.get("id") or f"group-{index + 1}").strip() or f"group-{index + 1}"
            if any(existing["id"] == group_id for existing in groups):
                group_id = f"{group_id}-{index + 1}"
            title = _clean_title(item.get("title"), f"Group {len(groups) + 1}")
            actions: list[str] = []
            for action_id in item.get("actions") or []:
                key = str(action_id).strip()
                if key not in known_set or key in seen:
                    continue
                seen.add(key)
                actions.append(key)
            groups.append({"id": group_id, "title": title, "actions": actions})
    if not groups:
        groups = default_home_groups()
        seen = {action_id for group in groups for action_id in group["actions"]}
    missing = [action_id for action_id in known if action_id not in seen]
    if missing:
        groups[-1]["actions"].extend(missing)
    return groups


def rename_home_group(groups: list[dict[str, Any]], index: int, title: str) -> list[dict[str, Any]]:
    next_groups = normalize_home_groups(groups)
    if index < 0 or index >= len(next_groups):
        return next_groups
    fallback = str(next_groups[index].get("title") or f"Group {index + 1}")
    next_groups[index]["title"] = _clean_title(title, fallback)
    return next_groups


def move_home_group(groups: list[dict[str, Any]], index: int, delta: int) -> list[dict[str, Any]]:
    next_groups = normalize_home_groups(groups)
    target = index + int(delta)
    if index < 0 or index >= len(next_groups) or target < 0 or target >= len(next_groups) or target == index:
        return next_groups
    item = next_groups.pop(index)
    next_groups.insert(target, item)
    return next_groups


def move_home_action(groups: list[dict[str, Any]], action_id: str, delta: int) -> list[dict[str, Any]]:
    """Move one action left/right. At a group edge, the button changes groups."""
    next_groups = normalize_home_groups(groups)
    group_index = None
    position = None
    for index, group in enumerate(next_groups):
        actions = list(group.get("actions") or [])
        if action_id in actions:
            group_index = index
            position = actions.index(action_id)
            break
    if group_index is None or position is None:
        return next_groups
    step = int(delta)
    if step == 0:
        return next_groups
    current = next_groups[group_index]["actions"]
    if step < 0:
        if position > 0:
            current[position], current[position - 1] = current[position - 1], current[position]
            return next_groups
        if group_index == 0:
            return next_groups
        current.pop(position)
        next_groups[group_index - 1]["actions"].append(action_id)
        return next_groups
    if position < len(current) - 1:
        current[position], current[position + 1] = current[position + 1], current[position]
        return next_groups
    if group_index >= len(next_groups) - 1:
        return next_groups
    current.pop(position)
    next_groups[group_index + 1]["actions"].insert(0, action_id)
    return next_groups
