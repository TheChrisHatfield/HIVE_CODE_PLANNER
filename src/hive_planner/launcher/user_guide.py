from __future__ import annotations

from pathlib import Path

from hive_planner.launcher.config import LauncherConfig, default_hive_root

_FALLBACK_GUIDE = """Hive Planner — quick help

What is this?
  HIVE (Hierarchical, Inference, Versatile Engine) Code Planner.
  Prompting is not enough context for an agent. Hive feeds project memory,
  source documents, and long ideation (Rosetta Stone) into Spec Kit so the
  agent gets a spec, plan, and tasks before it codes.
  This desktop app runs that workflow on your PC. No browser.

First time?
  Settings → Reset onboarding to run the setup wizard, or:
  Settings → Scan for Python → Install / update Hive
  Settings → Agent MCP → Enable — any MCP agent can call this Hive Planner

Daily use:
  Projects → Add link… (or Create project), then Set as active
  Home → Open in Cursor
  Home → Run health check before you hand the project to someone else
  Home → Loop controls — opens Controls for bug hunt, CodeSpec, and the agnostic loop
  Home → CodeSpec — opens Controls on a CodeSpec block (same tab as Loop controls)
  Controls — each block is one loop. Pick the loop, pick the command, then Run.
  Use + to add another block. The last block stays.
  Say implementation loop, code spec, or agnostic loop in Cursor chat to start that loop there.
  Controls → Install CodeSpec installs on the Cursor window in front (folds settings, then Enable).
  Home → Agent prompt templates — copy a prompt into Cursor chat
  Home → Rosetta cartridge eject — export a planning pack for Gemini, Perplexity, or ChatGPT
  Home → Verify vendor pins / Scan legacy deployment (or unified-verify from a terminal)
  Home → Deploy agent handoff — copies Spec Kit and Continual Learning files into the project

Full guide:
  scripts/README.md in this repo, also shown on the Home tab when the file is available.
"""


def unified_vendor_help_text() -> str:
    """Help appended when scripts/README.md has no Unified vendor path section."""
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
AGENT_MCP_SECTION_MARKER = "Agent MCP"


def implementation_loop_help_text() -> str:
    """Help appended when scripts/README.md has no Implementation loop section."""
    return """## Implementation loop

Controls calls this loop **CodeSpec**. Use it after a feature already has `spec.md`, `plan.md`, and `tasks.md`. It codes that task list; it does not write a new spec.

1. **Home → CodeSpec** opens Controls on a CodeSpec block. **Home → Loop controls** opens the same tab. **+** adds another loop block; **−** removes one, and the last block stays. **Install CodeSpec** targets the Cursor window in front, folds settings, then Enable. Compact only hides settings.
2. On that block, pick a command (**Enable**, **Status**, **Start**, **Handoff**, **Check**, **Accept**, **Commit**), then **Run**. The block lists the pack's steps and marks the one that is running or stopped. There is no role picker. Type **code spec** in the Loop box or in Cursor chat.

CLI: `py -3.11 -m hive_planner implementation-loop` with `status`, `start`, `handoff`, `check`, `accept`, or `commit`. Init installs the loop only with `--implementation-loop-pack`.

Do not merge, push to trunk, force-push, or deploy from this loop.
"""


def agnostic_loop_help_text() -> str:
    """Help appended when scripts/README.md has no Agnostic loop section."""
    return """## Agnostic loop

Pause-cycle work chooser (hive-loop-kit). It picks the next slice of work; it is not a bug hunt and not the implementation loop.

1. **Home → Loop controls**, then on a Controls block pick **Agnostic loop** and **Run** (**Enable**, **Arm**, **Begin**, **Review**, …). **+** adds another block.
2. CLI or `scripts/agnostic_loop.py`: `arm` / `begin` / `review` / `observe` / `choose` / `status`.
3. Replace `.hive/agnostic-loop/catalog.json` to change reward names and hooks.

CLI: `py -3.11 -m hive_planner agnostic-loop`. Init installs it only with `--agnostic-loop`. Say **agnostic loop** or **hive loop kit** in Cursor chat.
"""


def agent_mcp_help_text() -> str:
    """Launcher help for Settings Agent MCP (appended if scripts/README.md is stale)."""
    return """## Agent MCP

Settings **Agent MCP → Enable** lets any MCP agent call this Hive Planner. It writes `hive-planner` into that repo's `.cursor/mcp.json` for Cursor. Copy launch command for any other agent. Reload MCP in that agent after you add it.

CLI: `py -3.11 -m hive_planner mcp-serve` (portable: `HivePlanner.exe --hive-cli mcp-serve`).
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
    if readme_on_disk and AGENT_MCP_SECTION_MARKER not in text:
        text = text.rstrip() + "\n\n" + agent_mcp_help_text().strip() + "\n"
    return text
