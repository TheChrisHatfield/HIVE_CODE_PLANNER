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
  Home → Rosetta cartridge eject — export contract for Gemini / Perplexity planning sessions
  Home → Run health check before handoff
  Home → Enable bug hunt — then say "bug hunt" (or hunt for bugs) in any Cursor chat
  Home → Enable implementation loop — then Loop status / start / handoff / check / accept / commit, or say "implementation loop" in chat
  Home → Enable agnostic loop — installs the hive-loop-kit (arm / begin / review), or say "agnostic loop" / "hive loop kit"
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
4. **Home → Promote memory…** — run autonomous `agents-propose --apply` (auto-split / route) on staged candidates
5. **Home → Apply memory…** — re-run apply on a candidates file if needed

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
IMPLEMENTATION_LOOP_SECTION_MARKER = "## Implementation loop"
AGNOSTIC_LOOP_SECTION_MARKER = "## Agnostic loop"


def implementation_loop_help_text() -> str:
    """Plain-English launcher help for Home Loop buttons (appended if scripts/README.md is stale)."""
    return """## Implementation loop

Use this after a feature already has `spec.md`, `plan.md`, and `tasks.md`. It codes that task list; it does not write a new spec.

1. **Home → Enable implementation loop** — pick **1-pack** (one coordinator) or **4-pack** (coder + Python check + reviewer).
2. **Loop status** — is the feature ready to code?
3. **Loop start** — start coordinator gates for that feature.
4. **Loop handoff** — write `handoff.md` and count a round trip for a role.
5. **Loop check** — run `build`, `test:quick`, and the wiring audit for this task (not a bug hunt).
6. **Loop accept** — accept the role’s `result.md` entry.
7. **Loop commit** — one Python commit after checker and reviewer pass.

CLI: `py -3.11 -m hive_planner implementation-loop` with `status`, `start`, `handoff`, `check`, `accept`, or `commit`. Init installs the loop only with `--implementation-loop-pack`.

Do not merge, push to trunk, force-push, or deploy from this loop.
"""


def agnostic_loop_help_text() -> str:
    """Plain-English launcher help for Home Enable agnostic loop (appended if scripts/README.md is stale)."""
    return """## Agnostic loop

Pause-cycle work chooser (hive-loop-kit). It picks the next slice of work; it is not a bug hunt and not the implementation loop.

1. **Home → Enable agnostic loop** — installs scripts, catalog, skill, and chat command.
2. CLI or `scripts/agnostic_loop.py`: `arm` / `begin` / `review` / `observe` / `choose` / `status`.
3. Replace `.hive/agnostic-loop/catalog.json` to change reward names and hooks.

CLI: `py -3.11 -m hive_planner agnostic-loop`. Init installs it only with `--agnostic-loop`. Say **agnostic loop** or **hive loop kit** in Cursor chat.
"""


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
    if readme_on_disk and IMPLEMENTATION_LOOP_SECTION_MARKER not in text:
        text = text.rstrip() + "\n\n" + implementation_loop_help_text().strip() + "\n"
    if readme_on_disk and AGNOSTIC_LOOP_SECTION_MARKER not in text:
        text = text.rstrip() + "\n\n" + agnostic_loop_help_text().strip() + "\n"
    return text
