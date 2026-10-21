"""Continuous bug-hunt agent script (hook: change.bugfix_mode, integration.wiring_audit)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_ITERATIONS = 50
MIN_ITERATIONS = 1
MAX_ITERATIONS = 200

COMMAND_REL = Path(".cursor") / "commands" / "bug-hunt.md"
RULE_REL = Path(".cursor") / "rules" / "bug-hunt.mdc"
PACKET_REL = Path(".hive") / "bug-hunt" / "AGENT_PROMPT.md"


class BugHuntError(Exception):
    """Bug-hunt install failed."""


@dataclass
class BugHuntInstall:
    root: Path
    iterations: int
    command_path: Path
    rule_path: Path
    packet_path: Path

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "iterations": self.iterations,
            "command": str(COMMAND_REL).replace("\\", "/"),
            "rule": str(RULE_REL).replace("\\", "/"),
            "packet": str(PACKET_REL).replace("\\", "/"),
        }


def validate_iterations(iterations: int) -> int:
    if not isinstance(iterations, int) or isinstance(iterations, bool):
        raise BugHuntError(f"iterations must be an integer, got {iterations!r}")
    if iterations < MIN_ITERATIONS or iterations > MAX_ITERATIONS:
        raise BugHuntError(
            f"iterations must be between {MIN_ITERATIONS} and {MAX_ITERATIONS}, got {iterations}"
        )
    return iterations


DUAL_LANE_REL = Path(".cursor") / "rules" / "bug-hunt-dual-lane.mdc"
SCRIPTS_REL = Path("scripts") / "bug-hunt.md"

# Phrases that start the loop in any chat (including common typos).
TRIGGER_PHRASES = (
    "bug hunt",
    "bug hun",
    "bung hunt",
    "do a bug hunt",
    "do a bung hunt",
    "bug-hunt",
    "bughunt",
    "/bug-hunt",
)


def render_agent_prompt(iterations: int = DEFAULT_ITERATIONS, *, dual_lane: bool = False) -> str:
    """The bug-hunt script agents execute. Review is internal; the loop does not wait on the user."""
    count = validate_iterations(iterations)
    base = f"""Execute a continuous {count}-iteration bug-hunting and wiring verification loop. Deep-dive into code logic and functional issues. For each real bug, apply a minimal fix, perform your own internal agent review of the patch, commit locally when that review passes, then continue the next iteration without waiting for the user. Repeat until {count} reviewed fixes are committed, or until two consecutive search areas yield no real bug.

You do not have to stop after one bug. Pause only for that internal review, then continue. That is the intent of this script.

## Each iteration

1. Find one real functional or wiring bug: wrong result, a throw on a path the user can hit, a skipped link (UI or event never reaches the handler, or success is reported when a required step was skipped), or a dead setting. Skip style nits, drive-by refactors, and speculative guards that do not match a failure.
2. Apply the smallest fix that closes that failure. Follow this repo's theme, connectivity, and validation rules when the change touches them.
3. Self-review the patch before committing. The review passes only when all of these hold:
   - The change matches the failure you named.
   - A test or contract covers the fix when this repo has a harness for that layer.
   - Wiring audit: the chain from the user-visible action to the handler and the persisted or rendered result is actually called.
   - Only files for this fix are staged.
4. Commit locally with a message that says why. Do not push, open a pull request, or upload to a remote.
5. Start the next iteration immediately.

## Stop

Stop after {count} committed fixes, or after two consecutive areas with no real bug. Report the commits, what each one fixed, and any area you searched that had no bug. Do not invent work to fill the budget.
"""
    if not dual_lane:
        return base
    return (
        base
        + """
## This repo - dual-lane (phone + Z Fold)

Also follow `.cursor/rules/bug-hunt-dual-lane.mdc` and active Spec Kit FR-032-FR-034 / US7:

- Prefer **universal** fixes in shared layers (`services/search`, `core:data`, shared UI). Only touch fold shell for selection / two-pane / cover-to-unfold / width.
- Classify each committed fix: `universal` | `phone-wiring` | `fold-wiring`.
- Batch related findings when efficient; still self-review and commit before the next batch.
- Automated gate when possible: `services/search` pytest, Android unit tests, root pytest, `hive_planner ci-check`.
- Do not mark a hunt cycle release-ready if nav/fold wiring changed and only one device lane was exercised.
"""
    )


def render_cursor_rule() -> str:
    """Always-on trigger so a chat message of "bug hunt" (and typos) starts the installed script."""
    listed = ", ".join(f'"{p}"' for p in TRIGGER_PHRASES)
    return f"""---
description: Start the bug-hunt loop when the user types bug hunt, bug hun, bung hunt, or do a bug hunt in any chat in this repo
alwaysApply: true
---

# Bug hunt trigger

When the user asks to run a bug hunt in any chat on this repo - the message is or clearly requests {listed} - read `.cursor/commands/bug-hunt.md` and execute that script in this turn. If that file is missing, read `scripts/bug-hunt.md`. Start the loop. Do not reply with instructions for how to invoke the command.

A question about the command itself (whether it works, where the file is, how to install it) is not a start signal.
"""


def render_cursor_command(iterations: int = DEFAULT_ITERATIONS, *, dual_lane: bool = False) -> str:
    count = validate_iterations(iterations)
    body = render_agent_prompt(count, dual_lane=dual_lane)
    return (
        "---\n"
        "description: Continuous bug hunt — find, fix, self-review, commit locally, repeat.\n"
        "---\n\n"
        f"{body}"
    )


def install_bug_hunt(root: Path, iterations: int = DEFAULT_ITERATIONS) -> BugHuntInstall:
    count = validate_iterations(iterations)
    target = root.resolve()
    if not target.is_dir():
        raise BugHuntError(f"repo root is not a directory: {target}")

    dual_lane = (target / DUAL_LANE_REL).is_file()
    command_path = target / COMMAND_REL
    rule_path = target / RULE_REL
    packet_path = target / PACKET_REL
    scripts_path = target / SCRIPTS_REL
    command_path.parent.mkdir(parents=True, exist_ok=True)
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    scripts_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = render_agent_prompt(count, dual_lane=dual_lane)
    command_path.write_text(
        render_cursor_command(count, dual_lane=dual_lane),
        encoding="utf-8",
        newline="\n",
    )
    rule_path.write_text(render_cursor_rule(), encoding="utf-8", newline="\n")
    packet_path.write_text(prompt, encoding="utf-8", newline="\n")
    scripts_path.write_text(prompt, encoding="utf-8", newline="\n")
    return BugHuntInstall(
        root=target,
        iterations=count,
        command_path=command_path,
        rule_path=rule_path,
        packet_path=packet_path,
    )
