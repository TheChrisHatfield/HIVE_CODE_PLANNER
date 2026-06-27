from __future__ import annotations

from pathlib import Path

from hive_planner.launcher.config import LauncherConfig, default_hive_root

_FALLBACK_GUIDE = """Hive Planner — quick help

What is this?
  A desktop control panel for Cursor projects that use Hive planning folders.
  No browser required.

First time?
  Settings → Reset onboarding to run the setup wizard, or:
  Settings → Scan for Python → Install / update Hive

Daily use:
  Projects → Open project… (or Create project)
  Home → Run health check before handoff
  Home → Open in Cursor

Full guide:
  Open scripts/README.md in this repo (also shown on the Home tab when available).
"""


def user_guide_path(config: LauncherConfig | None = None) -> Path:
    root = config.normalized_hive_root() if config else default_hive_root()
    return root.resolve() / "scripts" / "README.md"


def load_user_guide(config: LauncherConfig | None = None) -> str:
    path = user_guide_path(config)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return _FALLBACK_GUIDE
