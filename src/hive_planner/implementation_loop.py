"""Implementation loop — code a finished Hive spec in separate Cursor passes.

Adapted from microsoft/agentic-loops (MIT, copyright Mr. Das, 2026).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
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
_SKIP_DIRTY_NAMES = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "node_modules",
        ".eggs",
    }
)


def validate_pack(pack: str) -> str:
    if pack not in VALID_PACKS:
        raise ValueError(f"Invalid pack '{pack}' — use one of: {', '.join(sorted(VALID_PACKS))}")
    return pack


def is_implementation_loop_request(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    run_phrases = (
        "run the implementation loop",
        "start the implementation loop",
        "implement the spec",
        "/implementation-loop",
    )
    about_loop = re.search(
        r"\b(what is|what's|what are|where is|how do|how does|is it|does it|can i)\b",
        lowered,
    ) or (
        "implementation loop" in lowered
        and re.search(r"\b(what|where|how|whether)\b", lowered)
    ) or (
        "implementation loop" in lowered
        and re.search(r"\b(is|whether)\b.{0,80}\b(enabled|installed)\b", lowered)
    )
    if about_loop and not any(p in lowered for p in run_phrases):
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
    baseline_dirty: list[str] = field(default_factory=list)
    last_retrospective_n: int = 0

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
            "baseline_dirty": list(self.baseline_dirty),
            "last_retrospective_n": self.last_retrospective_n,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LoopState:
        baseline = raw.get("baseline_dirty") or []
        if not isinstance(baseline, list):
            baseline = []
        return cls(
            feature=str(raw.get("feature", "")),
            pack=str(raw.get("pack", "")),
            branch=str(raw.get("branch", "")),
            current_task=str(raw.get("current_task", "")),
            round_trips=_coerce_round_trips(raw.get("round_trips", 0)),
            status=str(raw.get("status", "idle")),
            pr_url=str(raw.get("pr_url", "")),
            slice_signoff=str(raw.get("slice_signoff", "continue")),
            baseline_dirty=[str(p).replace("\\", "/") for p in baseline],
            last_retrospective_n=_coerce_round_trips(raw.get("last_retrospective_n", 0)),
        )


def _coerce_round_trips(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _validate_feature_id(feature: str, action: str = "start") -> str:
    name = (feature or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
        raise CoordinatorError("invalid feature id", action=action, feature=name)
    return name


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


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(data, indent=2) + "\n")


def _posix_rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _write_if_changed(path: Path, text: str, root: Path, written: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if path.is_file():
        try:
            previous = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            previous = None
    if previous == text:
        return
    _write_text_atomic(path, text)
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


def _require_non_trunk(root: Path, action: str) -> str:
    branch = _current_branch(root)
    trunk = _resolve_trunk(root)
    if not branch or branch == "HEAD":
        raise CoordinatorError("no current git branch", action=action)
    if branch == trunk:
        raise CoordinatorError(
            f"current branch '{branch}' is trunk '{trunk}'",
            action=action,
        )
    return branch


def _require_loop_branch(root: Path, state: LoopState, action: str) -> str:
    branch = _current_branch(root)
    if not branch or branch == "HEAD":
        raise CoordinatorError("no current git branch", action=action)
    if state.branch and branch != state.branch:
        raise CoordinatorError(
            f"current branch '{branch}' is not loop branch '{state.branch}'",
            action=action,
            feature=state.feature,
        )
    return branch


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
    return re.search(r"^[ \t]{0,3}- \[ \]", text, re.MULTILINE) is not None


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
    for name in ("Justfile", "justfile"):
        p = root / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            if "build" not in commands and re.search(r"^build[\s:]", text, re.MULTILINE):
                commands["build"] = "just build"
            if "test:quick" not in commands and re.search(r"^test[\s:]", text, re.MULTILINE):
                commands["test:quick"] = "just test"
            break
    for name in ("Taskfile.yml", "Taskfile.yaml", "taskfile.yml"):
        p = root / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            if "build" not in commands and re.search(r"^ {2,4}build:", text, re.MULTILINE):
                commands["build"] = "task build"
            if "test:quick" not in commands and re.search(r"^ {2,4}test:", text, re.MULTILINE):
                commands["test:quick"] = "task test"
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
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        for wf in [*workflows.glob("*.yml"), *workflows.glob("*.yaml")]:
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
py -3.11 -m hive_planner implementation-loop check
py -3.11 -m hive_planner implementation-loop accept --role <role>
py -3.11 -m hive_planner implementation-loop commit
```

If this is a {pack}, the coordinator {'performs implement, then Python check, then review, then commit' if pack == PACK_1 else 'delegates coder and reviewer as separate Cursor passes; Python runs check (build / test:quick / wiring audit)'}.

If a bug hunt is already in progress, finish or pause it before starting this loop.

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
        "Before each delegated pass run `implementation-loop handoff --role <role>`. Python writes `handoff.md` and increments `round_trips`. After the coder (or 1-pack implement) returns, run `implementation-loop check` — Python runs `build`, `test:quick`, and the wiring audit when enforced, then appends the checker `result.md` entry. After each role, run `implementation-loop accept --role <role>`.",
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
        "A role `fail` with `question` set: ask the human, then re-hand the same role (one round trip). Checker or reviewer `fail` without a question returns to the coder, then checker, then reviewer. `needs-sign-off` pauses; do not start the coder.",
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
        "Each `##` section that contains a checkbox is a slice. A heading with no checkboxes is not a slice. If no such heading exists, the whole file is one slice.",
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
            "You implement and review yourself. You do not delegate to coder, checker, or reviewer files. Call `implementation-loop check` for the checker result, write the reviewer `result.md` entry, then run `implementation-loop commit`.",
        ])
    else:
        lines.extend([
            "",
            "## 4-pack duties",
            "",
            "Delegate to `coder.md` and `reviewer.md` as separate Cursor passes. Do not implement or review yourself. After the coder, run `implementation-loop check` (Python checker infrastructure). Call `handoff`, then `accept`, then `commit`.",
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

Python owns this pass. Run `py -3.11 -m hive_planner implementation-loop check` (or Home **Loop check**). Do not re-run the gates by hand unless `check` is missing.

`check` runs `build` and `test:quick` from `.hive/implementation-loop/commands.json`, then the wiring audit when the project enforces it, and appends the checker `result.md` entry. You do not edit product code. You do not commit.

Do not edit `AGENTS.md`. Do not commit.
"""


def render_role_reviewer() -> str:
    return """# Implementation loop reviewer

You compare the diff to `docs/specs/<feature>/spec.md` and `plan.md`. You do not edit product code. You do not commit.

## Steps

1. Read `.hive/implementation-loop/handoff.md` and the coder's diff.
2. Check that the change matches the task and does not change what the product must do.
3. If the build approach changed, note the `plan.md` edit that is needed.
4. Append a `result.md` entry with `outcome: pass`, `outcome: fail`, `outcome: fail` plus `question` when you need human input, or `outcome: needs-sign-off`. Do not overwrite other roles.

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
    feature = (feature or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", feature):
        return ReadinessReport(
            ready=False,
            feature=feature,
            missing=["invalid feature id"],
            blocked_reason="invalid feature id",
        )
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
    try:
        commands = _read_existing_json_object(commands_path, "commands.json")
    except ValueError:
        commands = None
        missing.append("commands.json is not valid JSON")
    if commands is None and "commands.json is not valid JSON" not in missing:
        missing.append(".hive/implementation-loop/commands.json")
    elif commands is not None:
        for key in ("build", "test:quick", "test:full"):
            if not str(commands.get(key, "")).strip():
                missing.append(f"commands.json missing {key}")

    state_path = root / LOOP_DIR / "state.json"
    try:
        state = _read_existing_json_object(state_path, "state.json")
    except ValueError:
        state = None
        missing.append("state.json is not valid JSON")
    if state is None and "state.json is not valid JSON" not in missing:
        missing.append(".hive/implementation-loop/state.json")
    elif state is not None:
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
    if not branch or branch == "HEAD":
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
    pr_url: str = ""

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
            "pr_url": self.pr_url,
        }


def _loop_dir(root: Path) -> Path:
    return root / LOOP_DIR


def _read_feature_tasks(root: Path, feature: str, action: str) -> str:
    path = root / f"docs/specs/{feature}/tasks.md"
    if not path.is_file():
        raise CoordinatorError(
            f"docs/specs/{feature}/tasks.md is missing",
            action=action,
            feature=feature,
        )
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoordinatorError(
            f"cannot read tasks.md: {exc}",
            action=action,
            feature=feature,
        ) from exc


def _load_state(root: Path) -> LoopState:
    path = _loop_dir(root) / "state.json"
    try:
        data = _read_existing_json_object(path, "state.json")
    except ValueError as exc:
        raise CoordinatorError(str(exc), action="load") from exc
    if data is None:
        raise CoordinatorError("state.json is missing — install the loop first", action="load")
    return LoopState.from_dict(data)


def _save_state(root: Path, state: LoopState) -> None:
    try:
        _write_json(_loop_dir(root) / "state.json", state.to_dict())
    except OSError as exc:
        raise CoordinatorError(f"cannot write state.json: {exc}", action="save") from exc


def _git(root: Path, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, stdout="", stderr="git not found")


def _dirty_paths(root: Path) -> list[str]:
    proc = _git(root, "status", "--porcelain", "-uall")
    if proc.returncode != 0:
        raise CoordinatorError(proc.stderr.strip() or "git status failed", action="git")
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw.strip().strip('"').replace("\\", "/"))
    return paths


def _paths_for_commit(root: Path, feature: str, baseline: list[str]) -> list[str]:
    now = _unrelated_dirty(_dirty_paths(root))
    baseline_set = set(baseline)
    keep = {
        f"docs/specs/{feature}/tasks.md",
        f"docs/specs/{feature}/plan.md",
    }
    return [path for path in now if path in keep or path not in baseline_set]


def _unrelated_dirty(paths: list[str]) -> list[str]:
    unrelated: list[str] = []
    for posix in paths:
        if posix.startswith(".hive/") or posix == ".hive":
            continue
        parts = posix.split("/")
        if posix.endswith((".pyc", ".pyo")) or any(part in _SKIP_DIRTY_NAMES for part in parts):
            continue
        unrelated.append(posix)
    return unrelated


def _parse_open_task_line(line: str, heading: str) -> tuple[str, str, str] | None:
    match = re.match(r"^[ \t]{0,3}- \[ \] (.+)$", line)
    if not match:
        return None
    body = match.group(1).strip()
    id_match = re.match(r"^(T\d+)\b", body, re.IGNORECASE)
    task_id = id_match.group(1) if id_match else ""
    return task_id, heading, body


def _first_open_task(text: str) -> tuple[str, str, str]:
    heading = ""
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
        parsed = _parse_open_task_line(line, heading)
        if parsed:
            return parsed
    return "", "", ""


def _open_task_for_current(text: str, current: str, *, action: str) -> tuple[str, str, str]:
    heading = ""
    if current:
        for line in text.splitlines():
            if line.startswith("## "):
                heading = line[3:].strip()
            parsed = _parse_open_task_line(line, heading)
            if parsed and _task_token_matches(parsed[2], current, current):
                return parsed
        raise CoordinatorError(
            "current task is not an open checkbox",
            action=action,
            task=current,
        )
    return _first_open_task(text)


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
            match = re.match(r"^([ \t]{0,3}- \[ \] )(.+?)(\r?\n)?$", line)
            if match:
                rest = match.group(2).strip()
                if _task_token_matches(rest, task_id, body):
                    nl = match.group(3) or ""
                    indent = match.group(1)[: len(match.group(1)) - len("- [ ] ")]
                    line = f"{indent}- [x] {rest}{nl}"
                    done = True
        out.append(line)
    if not done:
        raise CoordinatorError("could not check off the current task", action="commit")
    return "".join(out)


def _task_line_unresolved(text: str, task_id: str, body: str) -> bool:
    for line in text.splitlines():
        match = re.match(r"^[ \t]{0,3}- \[ \] (.+)$", line)
        if not match:
            continue
        rest = match.group(1).strip()
        if _task_token_matches(rest, task_id, body):
            return "assumption: unresolved" in line.lower()
    return False


def _slice_has_open_after(text: str, heading: str) -> bool:
    if not heading:
        return _has_open_task_text(text)
    in_slice = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_slice = line[3:].strip() == heading
            continue
        if in_slice and re.match(r"^[ \t]{0,3}- \[ \]", line):
            return True
    return False


def _has_open_task_text(text: str) -> bool:
    return re.search(r"^[ \t]{0,3}- \[ \]", text, re.MULTILINE) is not None


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
                _set_result_field(current, key, value)
            continue
        if current is not None and ":" in line:
            key, value = line.split(":", 1)
            _set_result_field(current, key, value)
    if current:
        entries.append(current)
    return entries


def _set_result_field(entry: dict[str, str], key: str, value: str) -> None:
    name = key.strip().lower()
    text = value.strip()
    if name in {"role", "outcome"}:
        text = text.lower()
    entry[name] = text


def _entry_task_matches(entry: dict[str, str], task: str) -> bool:
    if not task:
        return True
    return _task_token_matches(str(entry.get("task", "")).strip(), task, task)


def _last_entry(entries: list[dict[str, str]], task: str, role: str) -> dict[str, str] | None:
    found: dict[str, str] | None = None
    for entry in entries:
        if entry.get("role") != role:
            continue
        if not _entry_task_matches(entry, task):
            continue
        found = entry
    return found


def _last_outcome(entries: list[dict[str, str]], task: str, role: str) -> str | None:
    entry = _last_entry(entries, task, role)
    if entry is None:
        return None
    return entry.get("outcome", "")


def _next_role_after_accept(role: str, outcome: str, question: str) -> str:
    if outcome == "fail":
        if question.strip():
            return role
        if role in {"checker", "reviewer"}:
            return "coder"
    return role


def _role_pass_after(entries: list[dict[str, str]], task: str, later_role: str, earlier_role: str) -> bool:
    later_idx = _last_role_index(entries, task, later_role)
    if later_idx is None or entries[later_idx].get("outcome") != "pass":
        return False
    earlier_idx = _last_role_index(entries, task, earlier_role)
    if earlier_idx is None:
        return False
    return later_idx > earlier_idx


def _checker_pass_after_coder(entries: list[dict[str, str]], task: str) -> bool:
    return _role_pass_after(entries, task, "checker", "coder")


def _last_role_index(entries: list[dict[str, str]], task: str, role: str) -> int | None:
    found: int | None = None
    for index, entry in enumerate(entries):
        if entry.get("role") != role:
            continue
        if not _entry_task_matches(entry, task):
            continue
        found = index
    return found


def _force_coder_after_fail(entries: list[dict[str, str]], task: str, failed_role: str) -> bool:
    """True when the last outcome for failed_role is fail without question and no later coder."""
    index = _last_role_index(entries, task, failed_role)
    if index is None:
        return False
    entry = entries[index]
    if entry.get("outcome") != "fail":
        return False
    if str(entry.get("question", "")).strip():
        return False
    for later in entries[index + 1 :]:
        if later.get("role") == "coder" and _entry_task_matches(later, task):
            return False
    return True


def _result_path(root: Path) -> Path:
    return _loop_dir(root) / "result.md"


def _read_result_text(root: Path, action: str) -> str:
    path = _result_path(root)
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoordinatorError(f"cannot read result.md: {exc}", action=action) from exc


def _reset_result(root: Path, task: str) -> None:
    try:
        _result_path(root).write_text(f"# result — {task or 'current task'}\n", encoding="utf-8")
    except OSError as exc:
        raise CoordinatorError(f"cannot write result.md: {exc}", action="handoff") from exc


def _evidence_line(label: str, proc: subprocess.CompletedProcess[str]) -> str:
    blob = (proc.stderr or proc.stdout or "").strip().replace("\n", " ")
    if len(blob) > 400:
        blob = blob[:400] + "…"
    extra = f": {blob}" if blob else ""
    return f"{label} exit {proc.returncode}{extra}"


def _append_result_entry(
    root: Path,
    task: str,
    role: str,
    outcome: str,
    evidence: str,
    *,
    action: str,
) -> None:
    path = _result_path(root)
    existing = _read_result_text(root, action)
    if not existing.strip():
        existing = f"# result — {task or 'current task'}\n"
    safe = evidence.replace("\n", " ").strip() or "(no evidence)"
    block = (
        f"\n- task: {task}\n"
        f"  role: {role}\n"
        f"  outcome: {outcome}\n"
        f"  evidence: {safe}\n"
    )
    try:
        path.write_text(existing + block, encoding="utf-8")
    except OSError as exc:
        raise CoordinatorError(f"cannot write result.md: {exc}", action=action) from exc


def _checker_wiring_audit_step(root: Path, feature: str) -> tuple[str, bool] | None:
    from hive_planner.config import RepoPaths
    from hive_planner.wiring_audit import check_wiring_audit, wiring_audit_enforced

    paths = RepoPaths(root=root)
    if not wiring_audit_enforced(paths):
        return None
    report = check_wiring_audit(paths, feature=feature)
    detail = (report.detail or "").replace("\n", " ").strip()
    if len(detail) > 400:
        detail = detail[:400] + "…"
    extra = f": {detail}" if detail else ""
    return (f"wiring-audit {'pass' if report.ok else 'fail'}{extra}", report.ok)


def _completed_feature_count(text: str) -> int:
    return len(re.findall(r"^\d{4}-\d{2}-\d{2} \| completed=", text, re.MULTILINE))


def _retrospective_due(completed: int, last: int = 0) -> bool:
    return completed > 0 and completed >= last + 5


def _ensure_proposal_stub(root: Path) -> None:
    path = root / "docs" / "proposals" / "implementation-loop-candidates.md"
    if path.is_file() and path.read_text(encoding="utf-8").strip():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# operational\n\n# behavioral\n", encoding="utf-8")


def _append_retrospective(root: Path, feature: str) -> int:
    log_path = _loop_dir(root) / "retrospective.log"
    existing = log_path.read_text(encoding="utf-8") if log_path.is_file() else RETROSPECTIVE_HEADER
    if re.search(rf"\| {re.escape(feature)}\s*$", existing, re.MULTILINE):
        return _completed_feature_count(existing)
    n = _completed_feature_count(existing) + 1
    line = f"{date.today().isoformat()} | completed={n} | {feature}\n"
    if not existing.endswith("\n"):
        existing += "\n"
    log_path.write_text(existing + line, encoding="utf-8")
    return n


def _gh(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["gh", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(["gh", *args], 127, stdout="", stderr="gh not found")


def _open_or_reuse_pull_request(root: Path, state: LoopState, feature: str) -> str:
    existing = state.pr_url.strip()
    if existing:
        return existing
    created = _gh(
        root,
        "pr",
        "create",
        "--title",
        f"implementation-loop {feature}",
        "--body",
        f"Implementation-loop commits for `{feature}`.",
    )
    if created.returncode != 0:
        return ""
    blob = "\n".join((created.stdout or "", created.stderr or ""))
    lines = [line.strip() for line in blob.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("http://") or line.startswith("https://"):
            return line
    return ""


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
    try:
        (_loop_dir(root) / "handoff.md").write_text(text, encoding="utf-8")
    except OSError as exc:
        raise CoordinatorError(
            f"cannot write handoff.md: {exc}",
            action="handoff",
            feature=feature,
        ) from exc


def coordinator_start(
    root: Path,
    feature: str,
    *,
    allow_dirty: bool = False,
    force_feature: bool = False,
) -> CoordinatorReport:
    root = root.resolve()
    feature = _validate_feature_id(feature, "start")
    report_ready = assess_implementation_readiness(root, feature)
    state = _load_state(root)

    if state.status == "blocked" and not force_feature:
        raise CoordinatorError(
            "loop is blocked — pass --force-feature after the human agrees",
            action="start",
            feature=feature,
        )

    if report_ready.blocked_reason == "complete" and report_ready.ready:
        state.status = "complete"
        state.feature = feature
        state.current_task = ""
        state.round_trips = 0
        completed = _append_retrospective(root, feature)
        next_role = ""
        if _retrospective_due(completed, state.last_retrospective_n):
            _ensure_proposal_stub(root)
            state.last_retrospective_n = completed
            next_role = "retrospective"
        _save_state(root, state)
        return CoordinatorReport(
            ok=True,
            action="start",
            feature=feature,
            round_trips=0,
            blocked_reason="complete",
            next_role=next_role,
            pr_url=state.pr_url,
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

    tasks_text = _read_feature_tasks(root, feature, "start")
    task_id, _heading, body = _first_open_task(tasks_text)
    current = task_id or body
    previous_task = state.current_task
    previous_feature = state.feature
    state.feature = feature
    state.branch = _current_branch(root)
    state.status = "running"
    state.current_task = current
    state.slice_signoff = "continue"
    state.baseline_dirty = list(unrelated)
    if previous_task != current or previous_feature != feature:
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
    role = (role or "").strip().lower()
    if state.status != "running" or not state.feature:
        raise CoordinatorError("loop is not running — start first", action="handoff", role=role)
    _require_loop_branch(root, state, "handoff")
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

    entries = parse_result_entries(_read_result_text(root, "handoff"))
    task = state.current_task
    if pack == PACK_4:
        last_reviewer = _last_outcome(entries, task, "reviewer")
        last_checker = _last_outcome(entries, task, "checker")
        if role == "coder" and (
            last_reviewer == "needs-sign-off" or last_checker == "needs-sign-off"
        ):
            raise CoordinatorError(
                "needs-sign-off pauses; do not start the coder",
                action="handoff",
                feature=state.feature,
                task=task,
                role=role,
            )
        if _force_coder_after_fail(entries, task, "reviewer") and role != "coder":
            raise CoordinatorError(
                "reviewer fail returns to coder",
                action="handoff",
                feature=state.feature,
                task=task,
                role=role,
            )
        if _force_coder_after_fail(entries, task, "checker") and role != "coder":
            raise CoordinatorError(
                "checker fail returns to coder",
                action="handoff",
                feature=state.feature,
                task=task,
                role=role,
            )
        if role == "checker" and _last_outcome(entries, task, "coder") != "pass":
            raise CoordinatorError(
                "checker handoff requires last coder outcome pass",
                action="handoff",
                feature=state.feature,
                task=task,
                role=role,
            )
        if role == "reviewer" and not _checker_pass_after_coder(entries, task):
            raise CoordinatorError(
                "reviewer handoff requires checker pass after the last coder",
                action="handoff",
                feature=state.feature,
                task=task,
                role=role,
            )

    tasks_text = _read_feature_tasks(root, state.feature, "handoff")
    task_id, heading, body = _open_task_for_current(tasks_text, state.current_task, action="handoff")
    if not state.current_task:
        state.current_task = task_id or body
        task = state.current_task
        _reset_result(root, state.current_task)
        entries = []
    has_current = any(
        _task_token_matches(str(entry.get("task", "")), task, task) for entry in entries
    )
    if not has_current and role in {"coder", "coordinator"}:
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


def coordinator_check(root: Path) -> CoordinatorReport:
    root = root.resolve()
    state = _load_state(root)
    if state.status != "running" or not state.feature:
        raise CoordinatorError("loop is not running — start first", action="check")
    _require_loop_branch(root, state, "check")
    pack = state.pack if state.pack in VALID_PACKS else PACK_4
    entries = parse_result_entries(_read_result_text(root, "check"))
    task = state.current_task
    if pack == PACK_4:
        if _force_coder_after_fail(entries, task, "reviewer"):
            raise CoordinatorError(
                "reviewer fail returns to coder",
                action="check",
                feature=state.feature,
                task=task,
                role="checker",
            )
        if _force_coder_after_fail(entries, task, "checker"):
            raise CoordinatorError(
                "checker fail returns to coder",
                action="check",
                feature=state.feature,
                task=task,
                role="checker",
            )
        if _last_outcome(entries, task, "coder") != "pass":
            raise CoordinatorError(
                "check requires last coder outcome pass",
                action="check",
                feature=state.feature,
                task=task,
                role="checker",
            )
        if _last_outcome(entries, task, "reviewer") == "needs-sign-off" or _last_outcome(
            entries, task, "checker"
        ) == "needs-sign-off":
            raise CoordinatorError(
                "needs-sign-off pauses; do not start the checker",
                action="check",
                feature=state.feature,
                task=task,
                role="checker",
            )

    steps: list[str] = []
    outcome = "pass"
    for key in ("build", "test:quick"):
        proc = _run_named_command(root, key)
        steps.append(_evidence_line(key, proc))
        if proc.returncode != 0:
            outcome = "fail"
            break
    if outcome == "pass":
        wiring = _checker_wiring_audit_step(root, state.feature)
        if wiring is not None:
            line, ok = wiring
            steps.append(line)
            if not ok:
                outcome = "fail"

    _append_result_entry(root, task, "checker", outcome, "; ".join(steps), action="check")
    failed = outcome == "fail"
    return CoordinatorReport(
        ok=not failed,
        action="check",
        feature=state.feature,
        task=task,
        role="checker",
        round_trips=state.round_trips,
        blocked_reason="fail" if failed else "",
        next_role="coder" if failed else "checker",
    )


def coordinator_accept(root: Path, role: str) -> CoordinatorReport:
    root = root.resolve()
    state = _load_state(root)
    role = (role or "").strip().lower()
    if state.status != "running" or not state.feature:
        raise CoordinatorError("loop is not running — start first", action="accept", role=role)
    pack = state.pack if state.pack in VALID_PACKS else PACK_4
    allowed = {"coordinator", "checker", "reviewer"} if pack == PACK_1 else HANDOFF_ROLES_4
    if role not in allowed:
        raise CoordinatorError(
            f"role '{role}' is not valid for {pack}",
            action="accept",
            feature=state.feature,
            role=role,
        )
    text = _read_result_text(root, "accept")
    if not text.strip():
        raise CoordinatorError("result.md is missing", action="accept", feature=state.feature, role=role)
    entries = parse_result_entries(text)
    entry = _last_entry(entries, state.current_task, role)
    outcome = entry.get("outcome", "") if entry else None
    if outcome not in {"pass", "fail", "needs-sign-off"}:
        raise CoordinatorError(
            f"missing result for task '{state.current_task}' role '{role}'",
            action="accept",
            feature=state.feature,
            task=state.current_task,
            role=role,
            round_trips=state.round_trips,
        )
    if outcome == "needs-sign-off":
        state.slice_signoff = "needs-sign-off"
        _save_state(root, state)
    elif state.slice_signoff == "needs-sign-off" and outcome == "pass" and role == "reviewer":
        state.slice_signoff = "continue"
        _save_state(root, state)
    blocked = ""
    if outcome == "fail":
        blocked = "fail"
    elif outcome == "needs-sign-off":
        blocked = "needs-sign-off"
    return CoordinatorReport(
        ok=True,
        action="accept",
        feature=state.feature,
        task=state.current_task,
        role=role,
        round_trips=state.round_trips,
        blocked_reason=blocked,
        next_role=_next_role_after_accept(role, outcome, str(entry.get("question", "") if entry else "")),
    )


def _push_enabled(commands: dict[str, Any] | None) -> bool:
    if not commands:
        return False
    value = commands.get("push")
    if value is True or value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}:
        return True
    return False


def _run_named_command(root: Path, key: str) -> subprocess.CompletedProcess[str]:
    try:
        commands = _read_existing_json_object(_loop_dir(root) / "commands.json", "commands.json") or {}
    except ValueError as exc:
        return subprocess.CompletedProcess(
            [key],
            127,
            stdout="",
            stderr=str(exc),
        )
    raw = str(commands.get(key, "")).strip()
    if not raw:
        return subprocess.CompletedProcess(
            [key],
            127,
            stdout="",
            stderr=f"commands.json missing {key}",
        )
    try:
        args = shlex.split(raw, posix=(sys.platform != "win32"))
    except ValueError as exc:
        return subprocess.CompletedProcess([raw], 127, stdout="", stderr=str(exc))
    try:
        return subprocess.run(
            args,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        name = args[0] if args else raw
        detail = str(exc).strip() or "not found"
        return subprocess.CompletedProcess(
            args or [raw],
            127,
            stdout="",
            stderr=f"{name} not found: {detail}",
        )


def _restore_tasks_after_git_failure(
    root: Path,
    tasks_path: Path,
    original: str,
    staged: list[str],
) -> None:
    tasks_path.write_text(original, encoding="utf-8")
    if staged:
        _git(root, "reset", "HEAD", "--", *[path.replace("\\", "/") for path in staged])


def coordinator_commit(root: Path) -> CoordinatorReport:
    root = root.resolve()
    state = _load_state(root)
    if state.status != "running" or not state.feature:
        raise CoordinatorError("loop is not running — start first", action="commit")
    _require_non_trunk(root, "commit")
    _require_loop_branch(root, state, "commit")
    feature = state.feature
    tasks_path = root / f"docs/specs/{feature}/tasks.md"
    tasks_text = _read_feature_tasks(root, feature, "commit")
    task_id, heading, body = _open_task_for_current(tasks_text, state.current_task, action="commit")
    current = state.current_task or task_id or body
    if _task_line_unresolved(tasks_text, task_id, body):
        raise CoordinatorError(
            "unresolved assumption blocks commit",
            action="commit",
            feature=feature,
            task=current,
        )

    entries = parse_result_entries(_read_result_text(root, "commit"))
    reviewer_outcome = _last_outcome(entries, current, "reviewer")
    if reviewer_outcome == "needs-sign-off" or state.slice_signoff == "needs-sign-off":
        raise CoordinatorError("needs-sign-off blocks commit", action="commit", feature=feature, task=current)
    for role in COMMIT_ROLES:
        if _last_outcome(entries, current, role) != "pass":
            raise CoordinatorError(
                f"commit requires {role} outcome pass",
                action="commit",
                feature=feature,
                task=current,
            )
    if (state.pack if state.pack in VALID_PACKS else PACK_4) == PACK_4:
        if not _checker_pass_after_coder(entries, current):
            raise CoordinatorError(
                "commit requires checker pass after the last coder",
                action="commit",
                feature=feature,
                task=current,
            )
        if not _role_pass_after(entries, current, "reviewer", "checker"):
            raise CoordinatorError(
                "commit requires reviewer pass after the last checker",
                action="commit",
                feature=feature,
                task=current,
            )

    dirty = _dirty_paths(root)
    if any(p == "AGENTS.md" or p.endswith("/AGENTS.md") for p in dirty):
        raise CoordinatorError("AGENTS.md is dirty — commit blocked", action="commit", feature=feature, task=current)

    checked = _check_off_task(tasks_text, task_id, body)
    tasks_path.write_text(checked, encoding="utf-8")

    to_add = _paths_for_commit(root, feature, state.baseline_dirty)
    if not to_add:
        _restore_tasks_after_git_failure(root, tasks_path, tasks_text, [])
        raise CoordinatorError("nothing to commit", action="commit", feature=feature, task=current)
    staged: list[str] = []
    try:
        for rel in to_add:
            add = _git(root, "add", "--", rel.replace("\\", "/"))
            if add.returncode != 0:
                raise CoordinatorError(
                    add.stderr.strip() or f"git add failed for {rel}",
                    action="commit",
                    feature=feature,
                    task=current,
                )
            staged.append(rel)

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
    except CoordinatorError:
        _restore_tasks_after_git_failure(root, tasks_path, tasks_text, staged)
        raise
    except OSError as exc:
        _restore_tasks_after_git_failure(root, tasks_path, tasks_text, staged)
        raise CoordinatorError(str(exc), action="commit", feature=feature, task=current) from exc
    sha = _git(root, "rev-parse", "HEAD").stdout.strip()

    still_dirty = _dirty_paths(root)
    leaked = [p for p in still_dirty if p.startswith(".hive/implementation-loop/")]
    # Runtime files may remain dirty; that is required. Product commit must not include them.

    state.round_trips = 0
    more = _has_open_task_text(checked)
    slice_open = _slice_has_open_after(checked, heading)

    try:
        commands = _read_existing_json_object(_loop_dir(root) / "commands.json", "commands.json") or {}
    except ValueError as exc:
        raise CoordinatorError(str(exc), action="commit", feature=feature, task=current) from exc
    if _push_enabled(commands) and _detect_push_default(root):
        pushed = _git(root, "push", "-u", "origin", state.branch or "HEAD")
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
                pr_url=state.pr_url,
            )
        url = _open_or_reuse_pull_request(root, state, feature)
        if url:
            state.pr_url = url

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
                pr_url=state.pr_url,
            )

    blocked_reason = ""
    completed = 0
    next_role = ""
    if not more:
        state.status = "complete"
        state.current_task = ""
        completed = _append_retrospective(root, feature)
        blocked_reason = "complete"
        if _retrospective_due(completed, state.last_retrospective_n):
            _ensure_proposal_stub(root)
            state.last_retrospective_n = completed
            next_role = "retrospective"
    else:
        next_id, _, next_body = _first_open_task(checked)
        state.status = "running"
        state.current_task = next_id or next_body
        _reset_result(root, state.current_task)
        next_role = "coordinator" if state.pack == PACK_1 else "coder"

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
        next_role=next_role,
        pr_url=state.pr_url,
    )
