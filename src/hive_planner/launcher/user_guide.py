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
  Home → Agent prompt templates — copy-paste into Cursor chat
  Home → Run health check before handoff
  Home → Verify vendor pins / Scan legacy deployment (unified handoff)
  Home → Open in Cursor

Unified vendor (Spec Kit + Continual Learning):
  Home → Deploy agent handoff copies pinned overlays into the project.
  Home → Verify vendor pins checks pins and overlay revs (or: unified-verify CLI).
  Hive source maintainers: vendor-sync --check / --apply (see scripts/README.md)

Full guide:
  Open scripts/README.md in this repo (also shown on the Home tab when available).
"""


def unified_vendor_help_text() -> str:
    """Plain-English launcher help for Stage 9 unified vendor path."""
    return """## Unified vendor path (Spec Kit + Continual Learning)

Hive **unified handoff** ships vendored, Hive-patched copies of GitHub Spec Kit and the
Cursor Continual Learning plugin — no separate marketplace install.

### What gets deployed

| Path | Purpose |
|------|---------|
| `.hive/upstream-pins.json` | Snapshot of pinned upstream refs and Hive patch revs |
| `.hive/spec-kit/` | Spec Kit templates (wiring audit, Rosetta nav, workflow gates) |
| `.cursor/plugins/hive-continual-learning/` | Continual Learning plugin (wiring audit gate, Durable Workspace Facts) |

The desktop app **Deploy agent handoff** button (Home tab) runs the same deploy as
`init --agent-handoff unified` / `deploy_agent_handoff_scaffold`.

### When to use what

| Situation | Action |
|-----------|--------|
| New project with unified handoff | **Projects → Create project** with handoff **unified**, or **Home → Deploy agent handoff** on an existing Hive project |
| After upgrading Hive Planner | **Home → Deploy agent handoff** again (refreshes overlays when patch rev changes) |
| Check pins and overlays in a project | **Home → Verify vendor pins**, or `py -3.11 -m hive_planner unified-verify` |
| Detect old marketplace / starter-kit layout | **Home → Scan legacy deployment** |
| Migrate marketplace CL → Hive vendored CL | **Home → Migrate marketplace CL…**, or `py -3.11 -m hive_planner cl-migrate` |
| Health check includes vendor step | **Home → Run health check** — fails `unified-vendor` when pins or overlays drift |

### Wiring audit and memory promotion (unified handoff)

Before promoting Continual Learning candidates into `AGENTS.md`:

1. Complete the **Integration wiring audit** checklist in `tasks.md`
2. **Home → Record wiring audit…** — enter your validation command (e.g. `pytest -q`)
3. **Home → Check wiring audit** — confirm attestation is current (also in **Run health check**)
4. **Home → Promote memory…** — run `agents-propose` on staged candidates in `docs/proposals/`
5. **Home → Apply memory…** — run `agents-apply` (or accept the prompt after propose)

CLI equivalents:

```powershell
py -3.11 -m hive_planner wiring-audit record --evidence "pytest -q"
py -3.11 -m hive_planner wiring-audit check
py -3.11 -m hive_planner agents-propose --candidates docs/proposals/candidates-….md
py -3.11 -m hive_planner agents-apply --candidates docs/proposals/candidates-….md
```

### Command line (project folder)

```powershell
py -3.11 -m hive_planner unified-verify
```

Read the JSON output for missing files or stale overlay revs. Re-run **Deploy agent handoff**
or bootstrap with `--agent-handoff unified` to repair.

### Hive source repo maintainers

Run these from the **Hive Planner repo root** (where `vendor/manifest.json` lives):

```powershell
py -3.11 -m hive_planner vendor-sync --check
py -3.11 -m hive_planner vendor-sync --apply
py -3.11 -m hive_planner unified-verify
```

- `--check` — validate manifest schema and pin status (default)
- `--apply` — import pinned upstream trees via git sparse checkout

Operator guide: `docs/unified-handoff-upstream-forks.md`
"""

UNIFIED_VENDOR_SECTION_MARKER = "## Unified vendor path"


def user_guide_path(config: LauncherConfig | None = None) -> Path:
    from hive_planner.runtime_paths import bundled_resource, is_portable_runtime

    if is_portable_runtime():
        bundled = bundled_resource("scripts", "README.md")
        if bundled is not None:
            return bundled
    root = config.normalized_hive_root() if config else default_hive_root()
    return root.resolve() / "scripts" / "README.md"


def load_user_guide(config: LauncherConfig | None = None) -> str:
    path = user_guide_path(config)
    readme_on_disk = path.is_file()
    text: str | None = None
    if readme_on_disk:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = None
    if text is None:
        text = _FALLBACK_GUIDE
        readme_on_disk = False
    if readme_on_disk and UNIFIED_VENDOR_SECTION_MARKER not in text:
        text = text.rstrip() + "\n\n" + unified_vendor_help_text().strip() + "\n"
    return text
