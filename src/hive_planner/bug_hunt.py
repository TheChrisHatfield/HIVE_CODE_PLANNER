"""Continuous bug-hunt agent script (hook: change.bugfix_mode, integration.wiring_audit)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ITERATIONS = 50
MIN_ITERATIONS = 1
MAX_ITERATIONS = 200

COMMAND_REL = Path(".cursor") / "commands" / "bug-hunt.md"
RULE_REL = Path(".cursor") / "rules" / "bug-hunt.mdc"
PACKET_REL = Path(".hive") / "bug-hunt" / "AGENT_PROMPT.md"
DUAL_LANE_REL = Path(".cursor") / "rules" / "bug-hunt-dual-lane.mdc"
SCRIPTS_REL = Path("scripts") / "bug-hunt.md"
OVERLAY_REL = Path(".hive") / "bug-hunt" / "repo-overlay.md"

# Explicit phrases plus common typos (also listed in the always-on Cursor rule).
TRIGGER_PHRASES = (
    "bug hunt",
    "bug hun",
    "bung hunt",
    "do a bug hunt",
    "do a bung hunt",
    "bug-hunt",
    "bughunt",
    "/bug-hunt",
    "hunt for bugs",
    "hunt bugs",
    "hunting bugs",
    "run a bug hunt",
    "start a bug hunt",
    "perform a bug hunt",
    "bug hunting",
    "bug hunts",
)

_COMMAND_QUESTION = re.compile(
    r"(?i)^\s*(how\s+(do\s+i|does|to)|where\s+(is|does)|what\s+(is|does)|does)\b"
)
_HUNT_BUGS = re.compile(r"(?i)\bhunt(?:ing)?\s+(?:for\s+)?(?:any\s+|the\s+)?bugs?\b")
_BUG_HUNT = re.compile(r"(?i)\bbu[gn]g?\s*-?\s*hun(?:t(?:s|ing)?)?\b")
_SLASH = re.compile(r"(?i)(?:^|\s)/bug-?hunt\b")
_COMPOUND = re.compile(r"(?i)\bbughunt\b")


class BugHuntError(Exception):
    """Bug-hunt install failed."""


@dataclass
class BugHuntInstall:
    root: Path
    iterations: int
    command_path: Path
    rule_path: Path
    packet_path: Path
    files_written: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "iterations": self.iterations,
            "command": str(COMMAND_REL).replace("\\", "/"),
            "rule": str(RULE_REL).replace("\\", "/"),
            "packet": str(PACKET_REL).replace("\\", "/"),
            "scripts": str(SCRIPTS_REL).replace("\\", "/"),
            "overlay": str(OVERLAY_REL).replace("\\", "/"),
            "files_written": list(self.files_written),
        }


def validate_iterations(iterations: int) -> int:
    if not isinstance(iterations, int) or isinstance(iterations, bool):
        raise BugHuntError(f"iterations must be an integer, got {iterations!r}")
    if iterations < MIN_ITERATIONS or iterations > MAX_ITERATIONS:
        raise BugHuntError(
            f"iterations must be between {MIN_ITERATIONS} and {MAX_ITERATIONS}, got {iterations}"
        )
    return iterations


def is_bug_hunt_request(text: str) -> bool:
    """True when chat text asks to run a hunt, not when it asks how the command works."""
    if not text or not str(text).strip():
        return False
    raw = str(text).strip()
    has_signal = bool(
        _SLASH.search(raw)
        or _COMPOUND.search(raw)
        or _BUG_HUNT.search(raw)
        or _HUNT_BUGS.search(raw)
    )
    if not has_signal:
        return False
    if _COMMAND_QUESTION.search(raw):
        return False
    return True


def _read_repo_overlay(root: Path) -> str:
    path = root / OVERLAY_REL
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    return f"\n{text}\n" if text else ""


def _prompt_options(root: Path) -> tuple[bool, str]:
    target = root.resolve()
    return (target / DUAL_LANE_REL).is_file(), _read_repo_overlay(target)


def preview_agent_prompt(root: Path, iterations: int = DEFAULT_ITERATIONS) -> str:
    """Same script text install would write (overlay + dual-lane), without writing files."""
    dual_lane, overlay = _prompt_options(root)
    return render_agent_prompt(iterations, dual_lane=dual_lane, overlay=overlay)


render_prompt_for_root = preview_agent_prompt


def render_agent_prompt(
    iterations: int = DEFAULT_ITERATIONS,
    *,
    dual_lane: bool = False,
    overlay: str = "",
) -> str:
    """The bug-hunt script agents execute. Review is internal; the loop does not wait on the user."""
    count = validate_iterations(iterations)
    base = f"""Execute a continuous {count}-iteration bug-hunting and wiring verification loop where you deep-dive into code logic and functional issues, automatically apply a fix, perform your own internal agent review of the patch, automatically commit the changes when that self-review passes, and repeat the process autonomously until the code is at a satisfactory quality level to stop — or until {count} reviewed fixes are committed.

You do not do one bug at a time and then wait. Pause only for that internal review, then continue the next iteration without waiting for the user. That is the intent of this script.

## Each iteration

1. Find one real functional or wiring bug: wrong result, a throw on a path the user can hit, a skipped link (UI or event never reaches the handler, or success is reported when a required step was skipped), or a dead setting. Skip style nits, drive-by refactors, and speculative guards that do not match a failure.
2. Apply the smallest fix that closes that failure. Follow this repo's theme, connectivity, and validation rules when the change touches them.
3. Self-review the patch before committing. The review passes only when all of these hold:
   - The change matches the failure you named.
   - A test or contract covers the fix when this repo has a harness for that layer.
   - Wiring audit: the chain from the user-visible action to the handler and the persisted or rendered result is actually called.
   - Only files for this fix are staged.
4. Commit locally with a message that says why. Do not push, open a pull request, or upload to a remote.
5. Start the next iteration immediately. Do not ask the user whether to continue.

## Stop

Stop after {count} committed fixes, or after two consecutive areas with no real bug. That empty-area stop is the satisfactory quality level — report the commits, what each one fixed, and any area you searched that had no bug. Do not invent work to fill the budget. Do not push.
"""
    extra = ""
    if dual_lane:
        extra += """
## This repo - dual-lane (phone + Z Fold)

Also follow `.cursor/rules/bug-hunt-dual-lane.mdc` and active Spec Kit FR-032-FR-034 / US7:

- Prefer **universal** fixes in shared layers (`services/search`, `core:data`, shared UI). Only touch fold shell for selection / two-pane / cover-to-unfold / width.
- Classify each committed fix: `universal` | `phone-wiring` | `fold-wiring`.
- Batch related findings when efficient; still self-review and commit before the next batch.
- Automated gate when possible: `services/search` pytest, Android unit tests, root pytest, `hive_planner ci-check`.
- Do not mark a hunt cycle release-ready if nav/fold wiring changed and only one device lane was exercised.
"""
    if overlay:
        extra += overlay if overlay.startswith("\n") else f"\n{overlay}\n"
    return base + extra


def render_cursor_rule() -> str:
    """Always-on trigger so a chat request to hunt bugs starts the installed script."""
    listed = ", ".join(f'"{p}"' for p in TRIGGER_PHRASES)
    return f"""---
description: Start the bug-hunt loop when the user asks to hunt bugs in any chat in this repo
alwaysApply: true
---

# Bug hunt trigger

When the user asks to run a bug hunt in any chat on this repo — the message is or clearly requests a bug hunt, including typos and derivatives such as {listed} — read `.cursor/commands/bug-hunt.md` and execute that script in this turn. If that file is missing, read `scripts/bug-hunt.md`. Start the loop and keep going: after each internal review and local commit, begin the next iteration without asking the user to continue. Do not stop after one bug. Do not reply with instructions for how to invoke the command.

Match intent, not only an exact string: "please hunt for bugs", "start hunting bugs", "run a bug-hunt", or "/bug-hunt" are start signals. A question about the command itself (whether it works, where the file is, how to install it) is not a start signal.
"""


def render_cursor_command(
    iterations: int = DEFAULT_ITERATIONS,
    *,
    dual_lane: bool = False,
    overlay: str = "",
) -> str:
    count = validate_iterations(iterations)
    body = render_agent_prompt(count, dual_lane=dual_lane, overlay=overlay)
    return (
        "---\n"
        "description: Continuous bug hunt (bug hunt, bug hun, bung hunt, do a bug hunt) — "
        "find, fix, self-review, commit locally, repeat.\n"
        "---\n\n"
        f"{body}"
    )


def _write_if_needed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def missing_bug_hunt_artifacts(root: Path) -> list[str]:
    """Relative paths that must exist after a successful install."""
    target = root.resolve()
    missing: list[str] = []
    for rel in (COMMAND_REL, RULE_REL, PACKET_REL, SCRIPTS_REL):
        if not (target / rel).is_file():
            missing.append(rel.as_posix())
    return missing


def install_bug_hunt(
    root: Path,
    iterations: int = DEFAULT_ITERATIONS,
    *,
    force: bool = True,
) -> BugHuntInstall:
    count = validate_iterations(iterations)
    target = root.resolve()
    if not target.is_dir():
        raise BugHuntError(f"repo root is not a directory: {target}")

    dual_lane, overlay = _prompt_options(target)
    prompt = render_agent_prompt(count, dual_lane=dual_lane, overlay=overlay)
    command_path = target / COMMAND_REL
    rule_path = target / RULE_REL
    packet_path = target / PACKET_REL
    scripts_path = target / SCRIPTS_REL
    written: list[str] = []
    pairs = (
        (command_path, render_cursor_command(count, dual_lane=dual_lane, overlay=overlay), COMMAND_REL),
        (rule_path, render_cursor_rule(), RULE_REL),
        (packet_path, prompt, PACKET_REL),
        (scripts_path, prompt, SCRIPTS_REL),
    )
    for path, content, rel in pairs:
        if _write_if_needed(path, content, force=force):
            written.append(rel.as_posix())
    return BugHuntInstall(
        root=target,
        iterations=count,
        command_path=command_path,
        rule_path=rule_path,
        packet_path=packet_path,
        files_written=written,
    )
