"""Implementation loop — code a finished Hive spec in separate Cursor passes.

Adapted from microsoft/agentic-loops (MIT, copyright Mr. Das, 2026).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PACK_1 = "1-pack"
PACK_4 = "4-pack"
VALID_PACKS = frozenset({PACK_1, PACK_4})

LOOP_DIR = Path(".hive") / "implementation-loop"
ROLE_DIR = LOOP_DIR / "roles"
COMMAND_PATH = Path(".cursor") / "commands" / "implementation-loop.md"
RULE_PATH = Path(".cursor") / "rules" / "implementation-loop.mdc"

NOTICE_TEXT = """MIT License

Copyright (c) 2026 Mr. Das

Adapted from https://github.com/microsoft/agentic-loops

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

RETROSPECTIVE_HEADER = "# implementation-loop retrospective log — count only date lines\n"


def validate_pack(pack: str) -> str:
    if pack not in VALID_PACKS:
        raise ValueError(f"Invalid pack '{pack}' — use one of: {', '.join(sorted(VALID_PACKS))}")
    return pack


def is_implementation_loop_request(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    question_starters = ("what is", "where is", "how do", "how does", "is it", "does it", "can i")
    if any(lowered.startswith(q) for q in question_starters):
        return False
    phrases = [
        "implementation loop",
        "implement the spec",
        "run the implementation loop",
        "start the implementation loop",
        "/implementation-loop",
    ]
    if any(p in lowered for p in phrases):
        return True
    if re.search(r"\bimplement\b", lowered) and re.search(r"\bspec\b", lowered):
        return True
    return False


@dataclass
class LoopState:
    feature: str = ""
    pack: str = ""
    branch: str = ""
    current_task: str = ""
    round_trips: int = 0
    status: str = "idle"
    pr_url: str = ""
    slice_signoff: str = "continue"

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "pack": self.pack,
            "branch": self.branch,
            "current_task": self.current_task,
            "round_trips": self.round_trips,
            "status": self.status,
            "pr_url": self.pr_url,
            "slice_signoff": self.slice_signoff,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LoopState:
        return cls(
            feature=str(raw.get("feature", "")),
            pack=str(raw.get("pack", "")),
            branch=str(raw.get("branch", "")),
            current_task=str(raw.get("current_task", "")),
            round_trips=int(raw.get("round_trips", 0)),
            status=str(raw.get("status", "idle")),
            pr_url=str(raw.get("pr_url", "")),
            slice_signoff=str(raw.get("slice_signoff", "continue")),
        )


@dataclass
class ReadinessReport:
    ready: bool
    feature: str
    missing: list[str] = field(default_factory=list)
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "feature": self.feature,
            "missing": self.missing,
            "blocked_reason": self.blocked_reason,
        }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _read_existing_json_object(path: Path, label: str) -> dict[str, Any] | None:
    """Return the object if the file exists. Raise when the file is present but invalid."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _posix_rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _write_if_changed(path: Path, text: str, root: Path, written: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")
    written.append(_posix_rel(root, path))


def _normalize_git_branch(ref: str) -> str:
    name = ref.strip()
    if name.startswith("origin/"):
        return name.split("/", 1)[1]
    return name


def _resolve_trunk(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if out.returncode == 0 and out.stdout.strip():
            return _normalize_git_branch(out.stdout)
    except Exception:
        pass
    for candidate in ("main", "master"):
        try:
            out = subprocess.run(
                ["git", "show-ref", "--verify", f"refs/heads/{candidate}"],
                capture_output=True,
                cwd=root,
            )
            if out.returncode == 0:
                return candidate
        except Exception:
            pass
    return "main"


def _current_branch(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def _has_open_task(tasks_path: Path) -> bool:
    if not tasks_path.is_file():
        return False
    text = tasks_path.read_text(encoding="utf-8", errors="replace")
    return re.search(r"^- \[ \]", text, re.MULTILINE) is not None


def _discover_commands(root: Path) -> dict[str, str]:
    commands: dict[str, str] = {}
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        if "pytest" in text and "[tool.pytest" in text:
            commands["test:quick"] = "py -3.11 -m pytest"
        if "ci-check" in text or "hive_planner" in text or "hive-planner" in text:
            commands["test:full"] = "py -3.11 -m hive_planner ci-check"
        if (root / "src").is_dir() and "setuptools" in text:
            commands["build"] = "py -3.11 -m compileall -q src"
    for name in ("Makefile", "makefile", "GNUmakefile"):
        p = root / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            if "build" not in commands and re.search(r"^build:", text, re.MULTILINE):
                commands["build"] = "make build"
            if "test:quick" not in commands and re.search(r"^test:", text, re.MULTILINE):
                commands["test:quick"] = "make test"
            break
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            if "build" not in commands and "build" in scripts:
                commands["build"] = "npm run build"
            if "test:quick" not in commands and "test" in scripts:
                commands["test:quick"] = "npm test"
        except Exception:
            pass
    for wf in (root / ".github" / "workflows").glob("*.yml") if (root / ".github" / "workflows").is_dir() else []:
        text = wf.read_text(encoding="utf-8", errors="replace")
        if "pytest" in text and "test:quick" not in commands:
            commands["test:quick"] = "py -3.11 -m pytest"
        if "hive_planner ci-check" in text and "test:full" not in commands:
            commands["test:full"] = "py -3.11 -m hive_planner ci-check"
    return commands


def _detect_push_default(root: Path) -> bool:
    try:
        out = subprocess.run(
            ["git", "remote"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        return "origin" in out.stdout.splitlines()
    except Exception:
        return False


def render_cursor_rule() -> str:
    phrases = [
        "implementation loop",
        "implement the spec",
        "run the implementation loop",
        "start the implementation loop",
        "/implementation-loop",
    ]
    listed = ", ".join(f'"{p}"' for p in phrases)
    return f"""---
description: Start the implementation loop when the user asks to implement a finished Hive spec
alwaysApply: true
---

# Implementation loop trigger

When the user asks to run the implementation loop in any chat on this repo — the message is or clearly requests it, including {listed} — read `.cursor/commands/implementation-loop.md` and execute that script in this turn. If that file is missing, report that the loop is not installed and stop.

Match intent, not only an exact string. A question about the loop itself (what it is, where it is installed, whether it is enabled) is not a start signal. A bug-hunt phrase is not a start signal.
"""


def render_cursor_command(pack: str) -> str:
    validate_pack(pack)
    roles = ["coordinator"] if pack == PACK_1 else ["coordinator", "coder", "checker", "reviewer"]
    role_list = ", ".join(roles)
    return f"""---
description: Run the implementation loop for a finished Hive spec
---

# Implementation loop ({pack})

Roles: {role_list}

Read `.hive/implementation-loop/roles/coordinator.md` and follow it. The coordinator owns the task list, the state file, and git.

If this is a {pack}, the coordinator {'performs all duties alone' if pack == PACK_1 else 'delegates to coder, checker, and reviewer as separate subagent passes'}.

Do not merge, push to trunk, force-push, or deploy.
"""


def render_role_coordinator(pack: str) -> str:
    validate_pack(pack)
    solo = pack == PACK_1
    lines = [
        "# Implementation loop coordinator",
        "",
        "You coordinate the coding loop for a finished Hive spec. You own `tasks.md` checkoff, `.hive/implementation-loop/state.json`, the handoff file, and git.",
        "",
        "## Startup",
        "",
        "1. Run `implementation-loop status --feature <feature>`. If it exits 2, report the blocked reason and stop.",
        "2. Load `docs/specs/<feature>/spec.md`, `plan.md`, and `tasks.md`.",
        "3. Load `.hive/implementation-loop/state.json`. If `status` is `running` for a different feature, ask the human before switching.",
        "4. Pick the next task: the first `- [ ]` checkbox in `tasks.md` file order.",
        "5. If no open checkbox remains, set `status` to `complete`, append the retrospective line, and stop.",
        "",
        "## One task",
        "",
        "Write `.hive/implementation-loop/handoff.md` before each pass. It names the feature, the task (id or checkbox line plus heading), the role, the repo root, and the spec/plan/tasks paths. Replace `result.md` when this task's first handoff is written.",
        "",
        "The pass **appends** to `.hive/implementation-loop/result.md`. Each entry has `task`, `role`, `outcome`, `evidence`, and `question` (when `outcome` is `fail`). Do not overwrite earlier role entries for this task.",
        "",
        "A missing or stale result is a failed pass.",
        "",
        "Do not edit `AGENTS.md`.",
        "",
        "## Round trips",
        "",
        "Check `round_trips` before every delegation, including a re-handoff after a human answer. One round trip is one delegation plus its return. Increment `round_trips` on each one. At 10, stop and ask the human before another pass. The count resets to `0` when the task is committed.",
        "",
        "A role `fail` with `question` set: ask the human, then re-hand the same role (one round trip). Reviewer `fail` without a question returns to the coder. `needs-sign-off` pauses; do not start the coder.",
        "",
        "## Git",
        "",
        "Commit only after the checker and reviewer results are `pass`. Commit the task's product files, `tasks.md`, and any approved `plan.md` edit. Leave `.hive/implementation-loop/` runtime files unstaged.",
        "",
        "Do not merge, push to trunk, force-push, or deploy.",
        "",
        "When `push` is true and `origin` exists, push after commit. Open one pull request on the first push. Store the URL in `state.json`.",
        "",
        "If push fails, keep the commit, set `status` to `blocked`, and ask the human. Do not retry silently.",
        "",
        "## Slice pause",
        "",
        "At the end of a slice, continue to the next task when the reviewer passed and no assumption is unresolved. Pause when the reviewer marked `needs-sign-off`, or when an assumption is unresolved.",
        "",
        "## Retrospective",
        "",
        "When a feature reaches `status: complete`, append `YYYY-MM-DD | completed=N | feature-id` to `.hive/implementation-loop/retrospective.log` before starting another feature. Count only date lines. Ask for pull-request approval only when `pr_url` is set; otherwise ask for local merge approval.",
        "",
        "## Behavior stop",
        "",
        "If the code would change what the product does, stop. Set `status` to `blocked`, leave the diff uncommitted, and ask the human to update `spec.md` first.",
    ]
    if solo:
        lines.extend([
            "",
            "## 1-pack duties",
            "",
            "You perform implement, check, and review yourself. You do not delegate to coder, checker, or reviewer files. You still append check and review outcomes to `result.md` before commit.",
        ])
    else:
        lines.extend([
            "",
            "## 4-pack duties",
            "",
            "Delegate to `coder.md`, `checker.md`, and `reviewer.md` as separate subagent passes. Do not implement, check, or review yourself.",
        ])
    return "\n".join(lines) + "\n"


def render_role_coder() -> str:
    return """# Implementation loop coder

You implement the single task named in `.hive/implementation-loop/handoff.md`. You may edit product code. You do not commit, push, or deploy.

## Rules

- Read `docs/specs/<feature>/spec.md` and `plan.md` before editing.
- Change only what the task asks for.
- Record assumptions on the task in `tasks.md` as a marked line: `Assumption: ...` or `Assumption: unresolved ...`.
- Leave the work uncommitted when you return.
- If you hit a blocking question, append a `result.md` entry with `outcome: fail` and the `question` field. Do not guess.
- Do not edit `AGENTS.md`. Do not commit.
"""


def render_role_checker() -> str:
    return """# Implementation loop checker

You verify the coder's changes. You do not edit product code. You do not commit.

## Steps

1. Read `.hive/implementation-loop/handoff.md` and the coder's diff.
2. Run the `build` command from `.hive/implementation-loop/commands.json`.
3. Run `test:quick` from `.hive/implementation-loop/commands.json`.
4. Run the integration wiring audit checklist (`.cursor/rules/integration-wiring-audit.mdc`).
5. Append a `result.md` entry with `outcome: pass` and the evidence, or `outcome: fail` and the failing step. Do not overwrite other roles.

If any step fails, report it and stop. Do not edit `AGENTS.md`. Do not commit.
"""


def render_role_reviewer() -> str:
    return """# Implementation loop reviewer

You compare the diff to `docs/specs/<feature>/spec.md` and `plan.md`. You do not edit product code. You do not commit.

## Steps

1. Read `.hive/implementation-loop/handoff.md` and the coder's diff.
2. Check that the change matches the task and does not change what the product must do.
3. If the build approach changed, note the `plan.md` edit that is needed.
4. Append a `result.md` entry with `outcome: pass`, `outcome: fail`, or `outcome: fail` plus `question` when you need human input. Do not overwrite other roles.
5. Mark `needs-sign-off` in `result.md` when the slice assumptions need human validation.

Do not edit `AGENTS.md`. Do not commit.
"""


def render_retrospective() -> str:
    return """# Implementation loop retrospective

Run this when the coordinator counts five or more completed features since the last retrospective line.

## Steps

1. Read `.hive/implementation-loop/retrospective.log`. Count only lines that match `YYYY-MM-DD | completed=N | ...`.
2. Review task notes, result files, and commits since the last line.
3. Keep lessons that recur. Drop notes that apply to one task only.
4. Write proposals to `docs/proposals/implementation-loop-candidates.md` with `# operational` and `# behavioral` sections.
5. Do not edit `AGENTS.md` directly. The human approves each item.
   - Operational items go through `agents-propose` / `agents-apply`.
   - Behavioral items are applied by editing the owning `spec.md`.
   - Role notes are edited into `.hive/implementation-loop/roles/` after approval.
"""


def install_implementation_loop(root: Path, pack: str, *, force_pack: bool = False) -> list[str]:
    root = root.resolve()
    validate_pack(pack)
    loop_dir = root / LOOP_DIR
    role_dir = root / ROLE_DIR
    command_path = root / COMMAND_PATH
    rule_path = root / RULE_PATH

    written: list[str] = []

    state_path = loop_dir / "state.json"
    existing_state = _read_existing_json_object(state_path, "state.json")
    if existing_state is not None:
        existing_pack = str(existing_state.get("pack", ""))
        if existing_pack and existing_pack != pack and not force_pack:
            raise ValueError(f"Existing pack '{existing_pack}' — use --force-pack to change")
        if existing_pack != pack:
            existing_state["pack"] = pack
            _write_json(state_path, existing_state)
            written.append(_posix_rel(root, state_path))
    else:
        state = LoopState(pack=pack, branch=_current_branch(root))
        _write_json(state_path, state.to_dict())
        written.append(_posix_rel(root, state_path))

    commands_path = loop_dir / "commands.json"
    existing_commands = _read_existing_json_object(commands_path, "commands.json")
    discovered = _discover_commands(root)
    if existing_commands is None:
        commands = {
            "build": discovered.get("build", ""),
            "test:quick": discovered.get("test:quick", ""),
            "test:full": discovered.get("test:full", ""),
            "push": _detect_push_default(root),
        }
        _write_json(commands_path, commands)
        written.append(_posix_rel(root, commands_path))
    else:
        changed = False
        for key in ("build", "test:quick", "test:full"):
            if not str(existing_commands.get(key, "")).strip() and discovered.get(key):
                existing_commands[key] = discovered[key]
                changed = True
        if "push" not in existing_commands:
            existing_commands["push"] = _detect_push_default(root)
            changed = True
        if changed:
            _write_json(commands_path, existing_commands)
            written.append(_posix_rel(root, commands_path))

    log_path = loop_dir / "retrospective.log"
    if not log_path.is_file():
        log_path.write_text(RETROSPECTIVE_HEADER, encoding="utf-8")
        written.append(_posix_rel(root, log_path))

    notice_path = loop_dir / "NOTICE"
    if not notice_path.is_file():
        notice_path.write_text(NOTICE_TEXT, encoding="utf-8")
        written.append(_posix_rel(root, notice_path))

    _write_if_changed(loop_dir / "retrospective.md", render_retrospective(), root, written)
    _write_if_changed(role_dir / "coordinator.md", render_role_coordinator(pack), root, written)

    if pack == PACK_4:
        for name, renderer in (("coder", render_role_coder), ("checker", render_role_checker), ("reviewer", render_role_reviewer)):
            _write_if_changed(role_dir / f"{name}.md", renderer(), root, written)
    else:
        for name in ("coder", "checker", "reviewer"):
            p = role_dir / f"{name}.md"
            if p.is_file():
                p.unlink()
                written.append(_posix_rel(root, p) + " (removed)")

    _write_if_changed(command_path, render_cursor_command(pack), root, written)
    _write_if_changed(rule_path, render_cursor_rule(), root, written)

    return written


def assess_implementation_readiness(root: Path, feature: str) -> ReadinessReport:
    root = root.resolve()
    missing: list[str] = []

    project_json = root / ".hive" / "project.json"
    if not project_json.is_file():
        missing.append(".hive/project.json")

    for rel in (
        f"docs/specs/{feature}/spec.md",
        f"docs/specs/{feature}/plan.md",
        f"docs/specs/{feature}/tasks.md",
        f"docs/delta/20_micro/{feature}.md",
    ):
        if not (root / rel).is_file():
            missing.append(rel)

    tasks_path = root / f"docs/specs/{feature}/tasks.md"
    all_checked = tasks_path.is_file() and not _has_open_task(tasks_path)

    commands_path = root / LOOP_DIR / "commands.json"
    commands = _read_json(commands_path)
    if commands is None:
        missing.append(".hive/implementation-loop/commands.json")
    else:
        for key in ("build", "test:quick", "test:full"):
            if not str(commands.get(key, "")).strip():
                missing.append(f"commands.json missing {key}")

    state_path = root / LOOP_DIR / "state.json"
    state = _read_json(state_path)
    if state is None:
        missing.append(".hive/implementation-loop/state.json")
    else:
        pack = str(state.get("pack", ""))
        if pack not in VALID_PACKS:
            missing.append(f"invalid pack '{pack}'")

    if all_checked and not missing:
        return ReadinessReport(ready=True, feature=feature, missing=[], blocked_reason="complete")

    if tasks_path.is_file() and not _has_open_task(tasks_path):
        missing.append(f"docs/specs/{feature}/tasks.md has no open task")

    trunk = _resolve_trunk(root)
    branch = _current_branch(root)
    if not branch:
        missing.append("no current git branch")
    elif branch == trunk:
        missing.append(f"current branch '{branch}' is trunk '{trunk}'")

    ready = not missing
    return ReadinessReport(
        ready=ready,
        feature=feature,
        missing=missing,
        blocked_reason="; ".join(missing) if missing else "",
    )


def preview_agent_prompt(pack: str) -> str:
    validate_pack(pack)
    return render_role_coordinator(pack)


def read_installed_pack(root: Path) -> str | None:
    state = _read_json(root.resolve() / LOOP_DIR / "state.json")
    if not state:
        return None
    pack = str(state.get("pack", ""))
    return pack if pack in VALID_PACKS else None
