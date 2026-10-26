"""Implementation loop — code a finished Hive spec in separate Cursor passes.

Adapted from microsoft/agentic-loops (MIT, copyright Mr. Das, 2026).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import date
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
ROUND_TRIP_CAP = 10
HANDOFF_ROLES_4 = frozenset({"coder", "checker", "reviewer"})
HANDOFF_ROLES_1 = frozenset({"coordinator"})
COMMIT_ROLES = ("checker", "reviewer")
GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Hive implementation-loop",
    "GIT_AUTHOR_EMAIL": "implementation-loop@hive.local",
    "GIT_COMMITTER_NAME": "Hive implementation-loop",
    "GIT_COMMITTER_EMAIL": "implementation-loop@hive.local",
}


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
    round_trips: int = 0
    current_task: str = ""
    pack: str = ""
    pr_url: str = ""
    state_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "feature": self.feature,
            "missing": self.missing,
            "blocked_reason": self.blocked_reason,
            "round_trips": self.round_trips,
            "current_task": self.current_task,
            "pack": self.pack,
            "pr_url": self.pr_url,
            "state_status": self.state_status,
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

If several features have open tasks and the message names none, ask which feature. If exactly one feature has open tasks, that feature is the target. If none are ready, report `implementation-loop status` and stop.
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

Read `.hive/implementation-loop/roles/coordinator.md` and follow it.

Call the Python coordinator gates. Do not `git commit`, edit `state.json` round trips, or write `handoff.md` by hand.

```text
py -3.11 -m hive_planner implementation-loop start --feature <id>
py -3.11 -m hive_planner implementation-loop handoff --role {'coordinator' if pack == PACK_1 else 'coder'}
py -3.11 -m hive_planner implementation-loop accept --role <role>
py -3.11 -m hive_planner implementation-loop commit
```

If this is a {pack}, the coordinator {'performs implement, check, and review, then calls commit' if pack == PACK_1 else 'delegates to coder, checker, and reviewer as separate subagent passes, then calls commit'}.

Do not merge, push to trunk, force-push, or deploy.
"""


def render_role_coordinator(pack: str) -> str:
    validate_pack(pack)
    solo = pack == PACK_1
    lines = [
        "# Implementation loop coordinator",
        "",
        "You coordinate the coding loop for a finished Hive spec. Python owns `tasks.md` checkoff, `.hive/implementation-loop/state.json`, the handoff file, and git. You call those gates. You do not implement them by hand.",
        "",
        "## Startup",
        "",
        "1. Run `py -3.11 -m hive_planner implementation-loop start --feature <feature>`. If it exits 2, report the blocked reason and stop.",
        "2. Load `docs/specs/<feature>/spec.md`, `plan.md`, and `tasks.md`.",
        "3. Unrelated dirty paths: start already blocked unless the human passed `--allow-dirty`. Do not stash or discard unrelated changes.",
        "",
        "## One task",
        "",
        "Before each delegated pass run `implementation-loop handoff --role <role>`. Python writes `handoff.md` and increments `round_trips`. After the role returns, run `implementation-loop accept --role <role>`.",
        "",
        "The pass **appends** to `.hive/implementation-loop/result.md`. Each entry has `task`, `role`, `outcome`, `evidence`, and `question` (when `outcome` is `fail`). Do not overwrite earlier role entries for this task.",
        "",
        "A missing or stale result is a failed pass.",
        "",
        "Do not edit `AGENTS.md`.",
        "",
        "## Round trips",
        "",
        "Python checks `round_trips` on each `handoff`, including a re-handoff after a human answer. At 10, `handoff` exits 2 unless the human passed `--continue-after-cap`. The count resets to `0` on `commit`.",
        "",
        "A role `fail` with `question` set: ask the human, then re-hand the same role (one round trip). Reviewer `fail` without a question returns to the coder. `needs-sign-off` pauses; do not start the coder.",
        "",
        "## Git",
        "",
        "Run `implementation-loop commit` only after `accept` for checker and reviewer is `pass`. Do not `git commit` yourself. Python commits product files, `tasks.md`, and any `plan.md` edit, leaves `.hive/` unstaged, and uses a message with the feature id and task id or a 6–10 word slug.",
        "",
        "Do not merge, push to trunk, force-push, or deploy.",
        "",
        "Python pushes when `push` is true and `origin` exists. If push fails, the commit is kept, `status` is `blocked`, and you ask the human. Do not retry silently.",
        "",
        "## Slice pause",
        "",
        "A slice is the first `##` section that contains a checkbox. A heading with no checkboxes is not a slice. If no such heading exists, the whole file is one slice.",
        "",
        "At the end of a slice run `test:full` from `commands.json`. On failure, set `status` to `blocked`, keep the commits, add no repair task, and ask the human.",
        "",
        "Continue to the next task when the reviewer passed and no assumption is unresolved. Pause when the reviewer marked `needs-sign-off`, or when a task line still has `Assumption: unresolved`.",
        "",
        "## Retrospective",
        "",
        "When a feature reaches `status: complete`, append `YYYY-MM-DD | completed=N | feature-id` to `.hive/implementation-loop/retrospective.log` before starting another feature. Count only date lines. When `N` has grown by 5 or more since the last retrospective, run `.hive/implementation-loop/retrospective.md` before starting another feature. Ask for pull-request approval only when `pr_url` is set; otherwise ask for local merge approval.",
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
            "You perform implement, check, and review yourself. You do not delegate to coder, checker, or reviewer files. You still append checker and reviewer outcomes to `result.md`, then run `implementation-loop commit`.",
        ])
    else:
        lines.extend([
            "",
            "## 4-pack duties",
            "",
            "Delegate to `coder.md`, `checker.md`, and `reviewer.md` as separate subagent passes. Do not implement, check, or review yourself. Call `handoff`, then `accept`, then `commit`.",
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


def _state_report_fields(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {}
    try:
        trips = int(state.get("round_trips", 0) or 0)
    except (TypeError, ValueError):
        trips = 0
    return {
        "round_trips": trips,
        "current_task": str(state.get("current_task", "")),
        "pack": str(state.get("pack", "")),
        "pr_url": str(state.get("pr_url", "")),
        "state_status": str(state.get("status", "")),
    }


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
        return ReadinessReport(
            ready=True,
            feature=feature,
            missing=[],
            blocked_reason="complete",
            **_state_report_fields(state),
        )

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
        **_state_report_fields(state),
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


class CoordinatorError(Exception):
    def __init__(self, message: str, **fields: Any) -> None:
        super().__init__(message)
        self.fields = fields


@dataclass
class CoordinatorReport:
    ok: bool
    action: str
    feature: str
    task: str = ""
    role: str = ""
    round_trips: int = 0
    blocked_reason: str = ""
    dirty: list[str] = field(default_factory=list)
    commit: str = ""
    next_role: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "feature": self.feature,
            "task": self.task,
            "role": self.role,
            "round_trips": self.round_trips,
            "blocked_reason": self.blocked_reason,
            "dirty": self.dirty,
            "commit": self.commit,
            "next_role": self.next_role,
        }


def _loop_dir(root: Path) -> Path:
    return root / LOOP_DIR


def _load_state(root: Path) -> LoopState:
    path = _loop_dir(root) / "state.json"
    data = _read_existing_json_object(path, "state.json")
    if data is None:
        raise CoordinatorError("state.json is missing — install the loop first", action="load")
    return LoopState.from_dict(data)


def _save_state(root: Path, state: LoopState) -> None:
    _write_json(_loop_dir(root) / "state.json", state.to_dict())


def _git(root: Path, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, env=env)


def _dirty_paths(root: Path) -> list[str]:
    proc = _git(root, "status", "--porcelain", "-uall")
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw.strip().strip('"').replace("\\", "/"))
    return paths


def _unrelated_dirty(paths: list[str]) -> list[str]:
    unrelated: list[str] = []
    for posix in paths:
        if posix.startswith(".hive/") or posix == ".hive":
            continue
        if "__pycache__" in posix.split("/") or posix.endswith(".pyc"):
            continue
        unrelated.append(posix)
    return unrelated


def _first_open_task(text: str) -> tuple[str, str, str]:
    heading = ""
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
        match = re.match(r"^- \[ \] (.+)$", line)
        if match:
            body = match.group(1).strip()
            id_match = re.match(r"^(T\d+)\b", body, re.IGNORECASE)
            task_id = id_match.group(1) if id_match else ""
            return task_id, heading, body
    return "", "", ""


def _task_slug(body: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", body)
    if words and re.match(r"^T\d+$", words[0], re.IGNORECASE):
        words = words[1:]
    chosen = words[:10]
    return "-".join(w.lower() for w in chosen) if chosen else "task"


def _task_token_matches(rest: str, task_id: str, body: str) -> bool:
    rest = rest.strip()
    if body and rest == body:
        return True
    if not task_id:
        return False
    token = rest.split()[0] if rest else ""
    return token == task_id


def _check_off_task(text: str, task_id: str, body: str) -> str:
    lines = text.splitlines(keepends=True)
    done = False
    out: list[str] = []
    for line in lines:
        if not done:
            match = re.match(r"^(- \[ \] )(.+?)(\r?\n)?$", line)
            if match:
                rest = match.group(2).strip()
                if _task_token_matches(rest, task_id, body):
                    nl = match.group(3) or ""
                    line = f"- [x] {rest}{nl}"
                    done = True
        out.append(line)
    if not done:
        raise CoordinatorError("could not check off the current task", action="commit")
    return "".join(out)


def _task_line_unresolved(text: str, task_id: str, body: str) -> bool:
    for line in text.splitlines():
        match = re.match(r"^- \[ \] (.+)$", line)
        if not match:
            continue
        rest = match.group(1).strip()
        if _task_token_matches(rest, task_id, body):
            return "Assumption: unresolved" in line
    return False


def _slice_has_open_after(text: str, heading: str) -> bool:
    if not heading:
        return _has_open_task_text(text)
    in_slice = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_slice = line[3:].strip() == heading
            continue
        if in_slice and re.match(r"^- \[ \]", line):
            return True
    return False


def _has_open_task_text(text: str) -> bool:
    return re.search(r"^- \[ \]", text, re.MULTILINE) is not None


def parse_result_entries(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current:
                entries.append(current)
            current = {}
            rest = line[2:]
            if ":" in rest:
                key, value = rest.split(":", 1)
                current[key.strip()] = value.strip()
            continue
        if current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip()
    if current:
        entries.append(current)
    return entries


def _last_outcome(entries: list[dict[str, str]], task: str, role: str) -> str | None:
    found: str | None = None
    for entry in entries:
        if entry.get("role") != role:
            continue
        entry_task = str(entry.get("task", "")).strip()
        if task and not _task_token_matches(entry_task, task, task):
            continue
        found = entry.get("outcome", "")
    return found


def _result_path(root: Path) -> Path:
    return _loop_dir(root) / "result.md"


def _reset_result(root: Path, task: str) -> None:
    _result_path(root).write_text(f"# result — {task or 'current task'}\n", encoding="utf-8")


def _append_retrospective(root: Path, feature: str) -> None:
    log_path = _loop_dir(root) / "retrospective.log"
    existing = log_path.read_text(encoding="utf-8") if log_path.is_file() else RETROSPECTIVE_HEADER
    if re.search(rf"\| {re.escape(feature)}\s*$", existing, re.MULTILINE):
        return
    n = len(re.findall(r"^\d{4}-\d{2}-\d{2} \| completed=", existing, re.MULTILINE)) + 1
    line = f"{date.today().isoformat()} | completed={n} | {feature}\n"
    if not existing.endswith("\n"):
        existing += "\n"
    log_path.write_text(existing + line, encoding="utf-8")


def _write_handoff(root: Path, state: LoopState, role: str, heading: str, body: str) -> None:
    feature = state.feature
    task = state.current_task
    text = "\n".join(
        [
            f"feature: {feature}",
            f"task: {task}",
            f"task_text: {body}",
            f"heading: {heading}",
            f"role: {role}",
            f"repo_root: {root.as_posix()}",
            f"spec: docs/specs/{feature}/spec.md",
            f"plan: docs/specs/{feature}/plan.md",
            f"tasks: docs/specs/{feature}/tasks.md",
            f"round_trips: {state.round_trips}",
            "",
        ]
    )
    (_loop_dir(root) / "handoff.md").write_text(text, encoding="utf-8")


def coordinator_start(
    root: Path,
    feature: str,
    *,
    allow_dirty: bool = False,
    force_feature: bool = False,
) -> CoordinatorReport:
    root = root.resolve()
    report_ready = assess_implementation_readiness(root, feature)
    state = _load_state(root)

    if report_ready.blocked_reason == "complete" and report_ready.ready:
        state.status = "complete"
        state.feature = feature
        state.current_task = ""
        state.round_trips = 0
        _save_state(root, state)
        _append_retrospective(root, feature)
        return CoordinatorReport(
            ok=True,
            action="start",
            feature=feature,
            round_trips=0,
            blocked_reason="complete",
        )

    if not report_ready.ready:
        raise CoordinatorError(
            report_ready.blocked_reason or "not ready",
            action="start",
            feature=feature,
        )

    if state.status == "running" and state.feature and state.feature != feature and not force_feature:
        raise CoordinatorError(
            f"loop is running for '{state.feature}' — pass --force-feature to switch",
            action="start",
            feature=feature,
        )

    unrelated = _unrelated_dirty(_dirty_paths(root))
    if unrelated and not allow_dirty:
        raise CoordinatorError(
            "unrelated dirty paths block start",
            action="start",
            feature=feature,
            dirty=unrelated,
        )

    tasks_text = (root / f"docs/specs/{feature}/tasks.md").read_text(encoding="utf-8")
    task_id, _heading, body = _first_open_task(tasks_text)
    current = task_id or body
    previous = state.current_task
    state.feature = feature
    state.branch = _current_branch(root)
    state.status = "running"
    state.current_task = current
    state.slice_signoff = "continue"
    if previous != current:
        state.round_trips = 0
        _reset_result(root, current)
    _save_state(root, state)
    return CoordinatorReport(
        ok=True,
        action="start",
        feature=feature,
        task=current,
        round_trips=state.round_trips,
        dirty=unrelated if allow_dirty else [],
        next_role="coordinator" if state.pack == PACK_1 else "coder",
    )


def coordinator_handoff(
    root: Path,
    role: str,
    *,
    continue_after_cap: bool = False,
) -> CoordinatorReport:
    root = root.resolve()
    state = _load_state(root)
    if state.status != "running" or not state.feature:
        raise CoordinatorError("loop is not running — start first", action="handoff", role=role)
    pack = state.pack if state.pack in VALID_PACKS else PACK_4
    allowed = HANDOFF_ROLES_1 if pack == PACK_1 else HANDOFF_ROLES_4
    if role not in allowed:
        raise CoordinatorError(
            f"role '{role}' is not valid for {pack}",
            action="handoff",
            feature=state.feature,
            role=role,
        )
    if state.round_trips >= ROUND_TRIP_CAP and not continue_after_cap:
        raise CoordinatorError(
            f"round_trips is {state.round_trips} — pass --continue-after-cap after the human agrees",
            action="handoff",
            feature=state.feature,
            task=state.current_task,
            role=role,
            round_trips=state.round_trips,
        )

    entries = parse_result_entries(_result_path(root).read_text(encoding="utf-8") if _result_path(root).is_file() else "")
    task = state.current_task
    if pack == PACK_4:
        if role == "checker" and _last_outcome(entries, task, "coder") != "pass":
            raise CoordinatorError(
                "checker handoff requires last coder outcome pass",
                action="handoff",
                feature=state.feature,
                task=task,
                role=role,
            )
        if role == "reviewer" and _last_outcome(entries, task, "checker") != "pass":
            raise CoordinatorError(
                "reviewer handoff requires last checker outcome pass",
                action="handoff",
                feature=state.feature,
                task=task,
                role=role,
            )

    tasks_text = (root / f"docs/specs/{state.feature}/tasks.md").read_text(encoding="utf-8")
    task_id, heading, body = _first_open_task(tasks_text)
    if not state.current_task:
        state.current_task = task_id or body
        _reset_result(root, state.current_task)
    state.round_trips += 1
    _write_handoff(root, state, role, heading, body)
    _save_state(root, state)
    return CoordinatorReport(
        ok=True,
        action="handoff",
        feature=state.feature,
        task=state.current_task,
        role=role,
        round_trips=state.round_trips,
        next_role=role,
    )


def coordinator_accept(root: Path, role: str) -> CoordinatorReport:
    root = root.resolve()
    state = _load_state(root)
    if state.status != "running" or not state.feature:
        raise CoordinatorError("loop is not running — start first", action="accept", role=role)
    path = _result_path(root)
    if not path.is_file():
        raise CoordinatorError("result.md is missing", action="accept", feature=state.feature, role=role)
    entries = parse_result_entries(path.read_text(encoding="utf-8"))
    outcome = _last_outcome(entries, state.current_task, role)
    if outcome not in {"pass", "fail"}:
        raise CoordinatorError(
            f"missing result for task '{state.current_task}' role '{role}'",
            action="accept",
            feature=state.feature,
            task=state.current_task,
            role=role,
            round_trips=state.round_trips,
        )
    return CoordinatorReport(
        ok=True,
        action="accept",
        feature=state.feature,
        task=state.current_task,
        role=role,
        round_trips=state.round_trips,
        blocked_reason="" if outcome == "pass" else "fail",
        next_role=role,
    )


def _run_named_command(root: Path, key: str) -> subprocess.CompletedProcess[str]:
    commands = _read_json(_loop_dir(root) / "commands.json") or {}
    raw = str(commands.get(key, "")).strip()
    if not raw:
        raise CoordinatorError(f"commands.json missing {key}", action="commit")
    args = shlex.split(raw, posix=os.name != "nt")
    return subprocess.run(args, cwd=root, capture_output=True, text=True)


def coordinator_commit(root: Path) -> CoordinatorReport:
    root = root.resolve()
    state = _load_state(root)
    if state.status != "running" or not state.feature:
        raise CoordinatorError("loop is not running — start first", action="commit")
    feature = state.feature
    tasks_path = root / f"docs/specs/{feature}/tasks.md"
    tasks_text = tasks_path.read_text(encoding="utf-8")
    task_id, heading, body = _first_open_task(tasks_text)
    current = state.current_task or task_id or body
    if _task_line_unresolved(tasks_text, task_id, body):
        raise CoordinatorError(
            "unresolved assumption blocks commit",
            action="commit",
            feature=feature,
            task=current,
        )

    entries = parse_result_entries(_result_path(root).read_text(encoding="utf-8") if _result_path(root).is_file() else "")
    for role in COMMIT_ROLES:
        if _last_outcome(entries, current, role) != "pass":
            raise CoordinatorError(
                f"commit requires {role} outcome pass",
                action="commit",
                feature=feature,
                task=current,
            )
    if _last_outcome(entries, current, "reviewer") == "needs-sign-off" or state.slice_signoff == "needs-sign-off":
        raise CoordinatorError("needs-sign-off blocks commit", action="commit", feature=feature, task=current)

    dirty = _dirty_paths(root)
    if any(p == "AGENTS.md" or p.endswith("/AGENTS.md") for p in dirty):
        raise CoordinatorError("AGENTS.md is dirty — commit blocked", action="commit", feature=feature, task=current)

    checked = _check_off_task(tasks_text, task_id, body)
    tasks_path.write_text(checked, encoding="utf-8")

    to_add = _unrelated_dirty(_dirty_paths(root))
    if not to_add:
        raise CoordinatorError("nothing to commit", action="commit", feature=feature, task=current)
    for rel in to_add:
        add = _git(root, "add", "--", rel.replace("/", os.sep))
        if add.returncode != 0:
            raise CoordinatorError(
                add.stderr.strip() or f"git add failed for {rel}",
                action="commit",
                feature=feature,
                task=current,
            )

    label = task_id or _task_slug(body)
    message = f"implementation-loop {feature} {label}"
    committed = _git(root, "commit", "-m", message, extra_env=GIT_IDENTITY)
    if committed.returncode != 0:
        raise CoordinatorError(
            committed.stderr.strip() or committed.stdout.strip() or "git commit failed",
            action="commit",
            feature=feature,
            task=current,
        )
    sha = _git(root, "rev-parse", "HEAD").stdout.strip()

    still_dirty = _dirty_paths(root)
    leaked = [p for p in still_dirty if p.startswith(".hive/implementation-loop/")]
    # Runtime files may remain dirty; that is required. Product commit must not include them.

    state.round_trips = 0
    more = _has_open_task_text(checked)
    slice_open = _slice_has_open_after(checked, heading)
    blocked_reason = ""
    if not more:
        state.status = "complete"
        state.current_task = ""
        _append_retrospective(root, feature)
        blocked_reason = "complete"
    else:
        next_id, _, next_body = _first_open_task(checked)
        state.status = "running"
        state.current_task = next_id or next_body
        _reset_result(root, state.current_task)

    commands = _read_json(_loop_dir(root) / "commands.json") or {}
    push_wanted = commands.get("push") is True
    if push_wanted and _detect_push_default(root):
        pushed = _git(root, "push", "-u", "origin", "HEAD")
        if pushed.returncode != 0:
            state.status = "blocked"
            _save_state(root, state)
            return CoordinatorReport(
                ok=False,
                action="commit",
                feature=feature,
                task=current,
                round_trips=0,
                blocked_reason=pushed.stderr.strip() or "git push failed",
                commit=sha,
            )

    if not slice_open:
        full = _run_named_command(root, "test:full")
        if full.returncode != 0:
            state.status = "blocked"
            _save_state(root, state)
            return CoordinatorReport(
                ok=False,
                action="commit",
                feature=feature,
                task=current,
                round_trips=0,
                blocked_reason=full.stderr.strip() or full.stdout.strip() or "test:full failed",
                commit=sha,
            )

    _save_state(root, state)
    return CoordinatorReport(
        ok=True,
        action="commit",
        feature=feature,
        task=current,
        round_trips=0,
        blocked_reason=blocked_reason,
        commit=sha,
        dirty=leaked,
        next_role="" if not more else ("coordinator" if state.pack == PACK_1 else "coder"),
    )
