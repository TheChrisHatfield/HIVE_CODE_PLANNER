"""Bootstrap detection for linked Cursor workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hive_planner.agent_handoff import validate_unified_handoff
from hive_planner.config import is_repo_root

LinkBootstrapAction = Literal["link_only", "add_missing", "overwrite", "create"]


@dataclass(frozen=True)
class BootstrapState:
    target: Path
    has_start_here: bool
    has_rosetta: bool
    hive_ready: bool
    handoff_missing: list[str]
    is_empty: bool

    @property
    def has_partial_hive(self) -> bool:
        return self.has_start_here or self.has_rosetta

    @property
    def has_existing_hive_files(self) -> bool:
        return self.hive_ready or self.has_start_here

    @property
    def needs_handoff_repair(self) -> bool:
        return bool(self.handoff_missing)

    @property
    def allows_add_missing(self) -> bool:
        if self.is_empty:
            return False
        if self.has_partial_hive and not self.hive_ready:
            return True
        return self.hive_ready and self.needs_handoff_repair


@dataclass(frozen=True)
class LinkBootstrapChoice:
    action: LinkBootstrapAction
    profile: str
    agent_handoff: str
    cl_runtime: str


def summarize_bootstrap_state(target: Path) -> BootstrapState:
    resolved = target.resolve()
    has_start_here = (resolved / "START_HERE.md").is_file()
    has_rosetta = (resolved / "docs" / "planning-rosetta-stone.md").is_file()
    hive_ready = is_repo_root(resolved)
    try:
        is_empty = resolved.is_dir() and not any(resolved.iterdir())
    except OSError:
        is_empty = False
    handoff = validate_unified_handoff(resolved)
    missing = list(handoff.missing) if handoff.mode == "unified" else []
    return BootstrapState(
        target=resolved,
        has_start_here=has_start_here,
        has_rosetta=has_rosetta,
        hive_ready=hive_ready,
        handoff_missing=missing,
        is_empty=is_empty,
    )
