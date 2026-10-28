"""Continuous bug-hunt agent script (hook: change.bugfix_mode, integration.wiring_audit)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ITERATIONS = 50
DEFAULT_PAUSE_SECONDS = 10
MIN_ITERATIONS = 1
MAX_ITERATIONS = 200

COMMAND_REL = Path(".cursor") / "commands" / "bug-hunt.md"
RULE_REL = Path(".cursor") / "rules" / "bug-hunt.mdc"
PACKET_REL = Path(".hive") / "bug-hunt" / "AGENT_PROMPT.md"
DUAL_LANE_REL = Path(".cursor") / "rules" / "bug-hunt-dual-lane.mdc"
SCRIPTS_REL = Path("scripts") / "bug-hunt.md"
CONTINUE_HOOK_REL = Path(".cursor") / "hooks" / "bug_hunt_continue.py"
HOOKS_JSON_REL = Path(".cursor") / "hooks.json"
CONTINUE_HOOK_COMMAND = "py -3.11 .cursor/hooks/bug_hunt_continue.py"
CONTINUE_HOOK_TIMEOUT = 86400
CONTINUE_HOOK_LOOP_LIMIT = 210
OVERLAY_REL = Path(".hive") / "bug-hunt" / "repo-overlay.md"

# Explicit phrases plus common typos (also listed in the always-on Cursor rule).
TRIGGER_PHRASES = (
    "bug hunt",
    "bu hunt",
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
    "hunt some bugs",
    "hunting for more bugs",
    "run another loop to fix bugs",
    "loop to fix bugs",
)

_COMMAND_QUESTION = re.compile(
    r"(?i)^\s*(how\s+(do\s+i|does|to)|where\s+(is|does)|what\s+(is|does)|does)\b"
)
_DOCS_QUESTION = re.compile(
    r"(?i)\b(?:how\s+(?:do\s+i|does|to)|where\s+(?:is|does)|what\s+(?:is|does))\b.{0,80}?\bbu[gn]g?"
)
# Negations, stop requests, and review-only wording near the hunt phrase are not
# start signals. They must not restart a loop the user is trying to end or inspect.
_HUNT_NAME = r"(?:bu[gn]g?\s*-?\s*hun(?:t(?:s|ing)?)?|bughunt|hunt(?:ing)?\s+for\s+bugs)"
_NEGATED_START = re.compile(
    rf"(?i)(?:\b(?:do\s*n'?t|do\s+not|dont)\s+(?:run|start|begin|launch|perform|want)\s+"
    rf"(?:the\s+|a\s+|another\s+|this\s+)?{_HUNT_NAME}"
    rf"|\bnever\s+(?:(?:run|start|begin|launch|perform)\s+)?"
    rf"(?:the\s+|a\s+|another\s+|this\s+)?{_HUNT_NAME}"
    rf"|\bwithout\s+(?:running|starting|beginning)\s+(?:the\s+|a\s+|another\s+|this\s+)?{_HUNT_NAME}"
    rf"|\b(?:do\s*n'?t|do\s+not|dont|never)\s+(?:run\s+)?(?:another\s+)?loop\s+to\s+fix\s+bugs)"
)
_STOP_REQUEST = re.compile(
    rf"(?i)(?:\b(?:stop|quit|cancel|abort|pause|halt|skip|disable|kill)\s+"
    rf"(?:the\s+|this\s+|that\s+|a\s+)?{_HUNT_NAME}"
    rf"|(?<!to[\s-])\bend\s+(?:the\s+|this\s+|that\s+|a\s+)?{_HUNT_NAME}"
    rf"|\b(?:wait\s+for|turn\s+off)\s+(?:the\s+|this\s+|that\s+|a\s+)?{_HUNT_NAME})"
)
_REVIEW_ONLY = re.compile(
    r"(?i)^\s*(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?"
    r"(?:review|check|look\s+(?:at|over)|audit|go\s+over|read|examine|"
    r"summarize|summarise|describe|explain|tell\s+me\s+about|walk\s+me\s+through|analyze|analyse|"
    r"inspect|fix\s+(?:the|those|these|this)\s+bugs?\s+in)\b"
)
_REVIEW_THEN_START = re.compile(
    r"(?i)\b(?:then|and)\s+(?:run|start|begin|perform|do|execute)\b.{0,40}?"
    r"(?:bu[gn]g?\s*-?\s*hun|bughunt|hunt(?:ing)?\s+for\s+bugs|loop\s+to\s+fix\s+bugs)"
)
_ABOUT_HUNT = re.compile(
    r"(?i)^\s*(?:the|this|that|our|your)\s+bu[gn]g?\s*-?\s*hun"
)
_HUNT_BUGS = re.compile(
    r"(?i)\bhunt(?:ing)?(?:\s+(?:for|some|those|these|more|any|the))*\s+bugs?\b"
)
_LOOP_FIX_BUGS = re.compile(
    r"(?i)\b(?:run\s+)?(?:another\s+)?loop\s+to\s+fix\s+bugs\b"
)
_BUG_HUNT = re.compile(r"(?i)\bbu(?:g|ng|n)?\s*-?\s*hun(?:t(?:s|ing)?)?\b")
_SLASH = re.compile(r"(?i)(?:^|\s)/bug-?hunt\b")
_COMPOUND = re.compile(r"(?i)\bbughunt\b")
_ENABLED_QUESTION = re.compile(
    r"(?i)\b(?:is|whether)\b.{0,80}\b(?:enabled|installed)\b"
)


class BugHuntError(Exception):
    """Bug-hunt install failed."""


@dataclass
class BugHuntInstall:
    root: Path
    iterations: int
    command_path: Path
    rule_path: Path
    packet_path: Path
    pause_seconds: int = DEFAULT_PAUSE_SECONDS
    files_written: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "iterations": self.iterations,
            "pause_seconds": self.pause_seconds,
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


def parse_iterations(raw: str | None) -> int:
    text = str(raw or "").strip()
    if not text:
        return DEFAULT_ITERATIONS
    try:
        value = int(text)
    except ValueError:
        try:
            number = float(text)
        except ValueError as exc:
            raise BugHuntError("iterations must be a whole number") from exc
        if not number.is_integer():
            raise BugHuntError("iterations must be a whole number")
        value = int(number)
    return validate_iterations(value)


def validate_pause_seconds(pause: int | None) -> int:
    """Blank means 10 seconds. Zero skips the wait. Any other whole number is the wait."""
    from hive_planner.bug_hunt_continue import MAX_SLEEP_SECONDS

    if pause is None:
        return DEFAULT_PAUSE_SECONDS
    if isinstance(pause, bool) or not isinstance(pause, int):
        raise BugHuntError(f"pause seconds must be a whole number, got {pause!r}")
    if pause < 0:
        raise BugHuntError(f"pause seconds must be 0 or greater, got {pause}")
    if pause > MAX_SLEEP_SECONDS:
        raise BugHuntError(
            f"pause seconds must be {MAX_SLEEP_SECONDS} or less, got {pause}"
        )
    return pause


def parse_pause_seconds(raw: str | None) -> int:
    text = str(raw or "").strip()
    if not text:
        return DEFAULT_PAUSE_SECONDS
    try:
        value = int(text)
    except ValueError:
        try:
            number = float(text)
        except ValueError as exc:
            raise BugHuntError("pause seconds must be a whole number") from exc
        if not number.is_integer():
            raise BugHuntError("pause seconds must be a whole number")
        value = int(number)
    return validate_pause_seconds(value)


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
        or _LOOP_FIX_BUGS.search(raw)
    )
    if not has_signal:
        return False
    if _COMMAND_QUESTION.search(raw) or _DOCS_QUESTION.search(raw):
        return False
    if _ENABLED_QUESTION.search(raw):
        return False
    if _NEGATED_START.search(raw) or _STOP_REQUEST.search(raw):
        return False
    if _REVIEW_ONLY.search(raw) and not _REVIEW_THEN_START.search(raw):
        return False
    if _ABOUT_HUNT.search(raw) and not raw.rstrip().endswith("?"):
        # A sentence about a hunt ("the bug hunts of yesterday") is not a start signal.
        if re.search(
            r"(?i)\b(?:of|was|were|is|did|went|stopped|finished)\b",
            raw,
        ):
            return False
    return True


def resolve_bug_hunt_root(root: Path) -> Path:
    """Directory that receives hunt files. Workspace files resolve to their folder."""
    target = Path(root).resolve()
    if target.is_file() and target.suffix.lower() == ".code-workspace":
        from hive_planner.launcher.service import resolve_linked_project_root

        folder = resolve_linked_project_root(target)
        if folder is None:
            raise BugHuntError(f"workspace has no folder on disk: {target}")
        target = folder
    if not target.is_dir():
        raise BugHuntError(f"repo root is not a directory: {target}")
    return target


def _read_repo_overlay(root: Path) -> str:
    path = Path(root) / OVERLAY_REL
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""
    return f"\n{text}\n" if text else ""


def _prompt_options(root: Path) -> tuple[bool, str]:
    try:
        target = resolve_bug_hunt_root(root)
    except BugHuntError:
        target = Path(root).resolve()
    return (target / DUAL_LANE_REL).is_file(), _read_repo_overlay(target)


def preview_agent_prompt(
    root: Path,
    iterations: int = DEFAULT_ITERATIONS,
    pause_seconds: int | None = None,
) -> str:
    """Same script text install would write (overlay + dual-lane), without writing files."""
    dual_lane, overlay = _prompt_options(root)
    return render_agent_prompt(
        iterations,
        pause_seconds=pause_seconds,
        dual_lane=dual_lane,
        overlay=overlay,
    )


render_prompt_for_root = preview_agent_prompt


def _pause_section(seconds: int, count: int) -> str:
    if seconds == 0:
        wait = "This run's pause is 0 seconds, so do not wait between passes. The stop hook does not wait."
        sequence = "The hook sets active to false, then starts the next inference pass."
    else:
        wait = (
            f"This run's pause is {seconds} seconds. That wait is not skippable. "
            f"The stop hook waits {seconds} seconds."
        )
        sequence = "The hook waits, then sets active to false, then starts the next inference pass."
    return (
        "Each iteration is its own inference pass. "
        f"{wait} "
        "After the outcome row is written, write `.hive/bug-hunt/continue.json` with these keys and end this turn: "
        f'"active" true, "pause_seconds" {seconds}, "ceiling" {count}, '
        '"committed" the number of committed fixes this hunt has made so far, and '
        '"consecutive_empty" the current run of empty outcomes in a row. '
        "A committed, skipped, or review-failed outcome resets consecutive_empty to 0. "
        "Valid JSON only — no placeholders, no comments. "
        "The hook also stops on those counters, so a pass that ended mid-write does not restart. "
        "Do not start the next bug in this pass. Do not ask the user whether to continue. "
        f"{sequence} "
        "Active false at the start of a pass means the token was used, not that the hunt is over. "
        "Do the iteration. Ending the turn does not stop the hunt when you wrote active true. "
        "When a stop condition is met, write the same file with "
        '"active" false instead. '
        "The hook will not start another pass."
    )


def render_agent_prompt(
    iterations: int = DEFAULT_ITERATIONS,
    *,
    pause_seconds: int | None = None,
    dual_lane: bool = False,
    overlay: str = "",
) -> str:
    """The bug-hunt script. One iteration is one inference pass, then the run's pause."""
    count = validate_iterations(iterations)
    pause = validate_pause_seconds(pause_seconds)
    pause_text = _pause_section(pause, count)
    base = f"""Stop after two consecutive empty searches, or when no unopened location still qualifies. A record-and-skip is not an empty search. A committed, skipped, or review-failed outcome resets the empty-search count. {count} committed fixes is the ceiling, not a quota. Until a stop condition is met, deep-dive into code logic and functional issues, apply a fix, self-review, commit locally when that review passes, and repeat across separate inference passes.

{pause_text} This is a {count}-iteration ceiling.

## Where to look

Rank locations before editing. Open the highest score that still qualifies and that this run has not already opened. One location per iteration. Before 30 rows exist, or when the regression cannot be fit, qualifying means any weighted-sum signal. When the regression is fit, qualifying means probability at least 0.35. The ranker chooses the queue only. It does not write the patch, choose the commit message, or override the stop rule.

Score each candidate with this weighted sum until 30 completed rows exist: recent bug-fix commits in the file × 3, a failing or thin test on that path × 5 (count that test once), a wiring hop with no call site (UI or event → handler → persisted or rendered result) × 5, a setting or flag with no reader × 4, the file appears in a reverted commit × 4, two call sites read the same fact through different stores × 4. Line churn is a tie-break only. Do not open a file because it looks complex or because the style is inconsistent. Before those 30 rows exist, there is no floor: open a location that has any of those signals.

The weighted sum is not a probability. Do not compare it to 0.35. Fit a logistic regression only after at least 30 completed rows, and only when those rows include at least one committed outcome and one other outcome. Otherwise keep the weighted sum and treat any signal as qualifying. When the regression is fit, use its probability as the score. The floor is 0.35, and it applies only to that probability. Leave locations under that floor unopened.

One row per opened location, written once, after the outcome is known: file, signals, scenario, outcome (`committed`, `skipped`, `empty`, or `review-failed`). Append that row to `.hive/bug-hunt/rank-rows.jsonl`. Do not append a second row for the same location in this run. A later hunt may append a new row for that location. Rows from earlier hunts count toward the 30. An unopened location is not an empty search. The location model treats only `committed` as positive. The classifier treats `committed` and `review-failed` as a real bug.

Before scoring, read `.hive/bug-hunt/rank-rows.jsonl` and mark this run's opened set. Each continue pass adds its row to that set: a file named by any row already written during this hunt is opened, and the queue excludes it. A hunt starts after `active` was written false for a stop condition, and its opened set begins empty. Rows from earlier hunts count toward the 30 but do not close a location.

## Each iteration

1. Review the next ranked location for a bug you can fix this iteration. A bug qualifies when the code, given a concrete action and state, produces a wrong result.
   - Confirmed: it fails on a path the user can hit now. Wrong result, a throw, a skipped link (UI or event never reaches the handler), success reported when a required step was skipped, or a dead setting.
   - Potential: it has not failed in this session, but you can name the action, the state, and the wrong outcome, and that outcome follows from the code as written. Count these: two readers of the same fact disagree (a live value versus a cache, a remembered path versus the folder the other app polls); a first observation swallows a later event; success is returned before a required step; a value that must be per host, per project, or per file is shared; a stamp, flag, or fingerprint sticks and changes the next run.
   Skip style nits, drive-by refactors, and a guard that does not change a result. "I did not reproduce it this session" is not a reason to skip a potential bug that meets that bar.
2. Classify the named scenario before editing. A confirmed bug that meets the step 1 bar is **fix**, including when the harness is missing. The missing harness is handled at review, not by skipping the edit. A potential bug that needs a product decision, touches a secret, or has no harness is **record-and-skip** before any edit. Any other potential bug is **fix**. Style, complexity, or a scenario the code does not produce is **empty**. Fit a classifier only after at least 30 completed rows in `.hive/bug-hunt/rank-rows.jsonl`, and only when those rows include at least one real-bug outcome (`committed` or `review-failed`) and one other outcome. Otherwise use the rules above and do not invent a probability. When it is fit, it may score P(real bug): at least 0.65 means **fix**, from 0.35 up to 0.65 means **record-and-skip**, below 0.35 means **empty**. That score must not move a confirmed bug off **fix**, and it must not move a potential-bug secret, product decision, or missing harness off **record-and-skip**. The class gates step 3. It does not write the patch.
3. Apply the smallest fix that closes that failure when the class is fix. Follow this repo's theme, connectivity, and validation rules when the change touches them. On record-and-skip or empty, do not edit and do not run the self-review.
4. When a patch exists, self-review it before committing. Do not commit the first draft. This review is not a wait between passes, including when the pause is 0. Finish the review, then choose the outcome. Simulate the user-visible behavior this code already had, including behavior the patch was not meant to change. Walk the call chain from the action that used to work through every function the patch edits, using the same inputs that used to succeed. Example: creating extra command-strip tabs must still show the overflow slider; a follow-up layout pass must not hide it. The review fails if the patch removes, skips, caches off, or permanently replaces that behavior. Rank which tests to run from past diffs that touched the same files and which tests failed. Run the top of that list. The ranker orders the harness. It does not pass this review. The review passes only when all of these hold:
   - The change matches the failure you named.
   - The simulation shows the previous behavior still happens on the path that used to perform it.
   - A test or contract covers the fix when this repo has a harness for that layer, and covers the behavior you had to keep.
   - Wiring audit: the chain from the user-visible action to the handler and the persisted or rendered result is actually called.
   - Only files for this fix are staged.
5. Choose exactly one outcome, in this order. A **record-and-skip**, a product decision, or a secret does not commit. If that case has a patch, restore only this iteration's uncommitted edits. The outcome is `skipped`, including when the review also fails or the patch cannot be covered. Otherwise an **empty** class does not commit. If that case has edits, restore only this iteration's uncommitted edits. The outcome is `empty`. Otherwise if the review fails, or the patch cannot be covered, restore only this iteration's uncommitted edits and do not commit. The outcome is `review-failed`. Otherwise commit locally with a message that says why. The outcome is `committed`. If that commit fails, restore only this iteration's uncommitted edits and use `review-failed` instead. A failed review is not an empty search. It is `skipped` only when this step already chose `skipped`. Every other failed review is `review-failed`. Do not push, open a pull request, or upload to a remote.
6. Write the outcome row. Then write `.hive/bug-hunt/continue.json` as the pause section says: active true when the hunt should continue, active false when a stop condition is met. If this pass began with active false, that only means the hook already used the previous token. End this turn. Do not start the next iteration in this pass. Do not ask the user whether to continue. The stop hook waits the pause (0 means it does not wait) and starts the next inference pass when you wrote active true. An empty search is an opened location classified **empty**, or an opened location with neither a confirmed bug nor a potential bug. Record-and-skip is not an empty search. A committed, skipped, or review-failed outcome resets the empty-search count. Drop the location from the queue. That outcome is the one written to `.hive/bug-hunt/rank-rows.jsonl`.

## Stop

Stop after {count} committed fixes, after two consecutive empty searches, or when no unopened location still qualifies (a real signal when there is no fitted model, or probability at least 0.35 when the regression is fit). Two consecutive empty searches means two empty outcomes in a row. A committed, skipped, or review-failed outcome resets that count. Report the commits, what each one fixed (confirmed or potential, and the scenario), anything you recorded and skipped, and any opened location that had neither a confirmed bug nor a potential bug. Do not invent a scenario the code does not actually produce. Do not push.
"""
    extra = ""
    if dual_lane:
        extra += """
## This repo - dual-lane (phone + Z Fold)

Also follow `.cursor/rules/bug-hunt-dual-lane.mdc` and active Spec Kit FR-032-FR-034 / US7:

- Prefer **universal** fixes in shared layers (`services/search`, `core:data`, shared UI). Only touch fold shell for selection / two-pane / cover-to-unfold / width.
- Classify each committed fix: `universal` | `phone-wiring` | `fold-wiring`.
- One location per iteration still holds. Self-review and commit that one fix, then end the turn. Do not start a second bug in this pass.
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

When the user asks to run a bug hunt in any chat on this repo — the message is or clearly requests a bug hunt, including typos and derivatives such as {listed} — read `.cursor/commands/bug-hunt.md` and do one iteration of that script in this turn, then end the turn. If that file is missing, read `scripts/bug-hunt.md`. One iteration is one inference pass. After the outcome row is written, write the continue file named in that script and end the turn. The stop hook waits the script's pause: a positive number of seconds is not skippable, and 0 means it does not wait. Then the hook starts the next inference pass. Do not ask the user to continue. Do not stop after one bug by starting the next bug in this same turn. End the turn after the iteration. The hook starts the next pass unless a stop condition in the script is met. Do not reply with instructions for how to invoke the command.

Match intent, not only an exact string: "please hunt for bugs", "start hunting bugs", "run a bug-hunt", or "/bug-hunt" are start signals. A question about the command itself (whether it works, where the file is, how to install it) is not a start signal. A request to stop, cancel, pause, skip, disable, or wait for the hunt is not a start signal. A request to review, summarize, audit, or explain the bug hunt script is not a start signal. "end to end bug hunt" and a start after another clause ("stop explaining and run a bug hunt") are start signals.
"""


def render_cursor_command(
    iterations: int = DEFAULT_ITERATIONS,
    *,
    pause_seconds: int | None = None,
    dual_lane: bool = False,
    overlay: str = "",
) -> str:
    count = validate_iterations(iterations)
    body = render_agent_prompt(
        count,
        pause_seconds=pause_seconds,
        dual_lane=dual_lane,
        overlay=overlay,
    )
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
    normalized = content.replace("\r\n", "\n")
    if path.is_file():
        try:
            current = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeDecodeError):
            current = None
        if current == normalized:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(normalized, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return True


def missing_bug_hunt_artifacts(root: Path) -> list[str]:
    """Relative paths that must exist after a successful install."""
    try:
        target = resolve_bug_hunt_root(root)
    except BugHuntError:
        target = Path(root).resolve()
    missing: list[str] = []
    for rel in (COMMAND_REL, RULE_REL, PACKET_REL, SCRIPTS_REL, CONTINUE_HOOK_REL):
        if not (target / rel).is_file():
            missing.append(rel.as_posix())
    if not _continue_hook_registered(target):
        missing.append(f"{HOOKS_JSON_REL.as_posix()}#stop:{CONTINUE_HOOK_COMMAND}")
    return missing


def render_continue_hook() -> str:
    """Standalone stop-hook source. Same file the package runs."""
    source = Path(__file__).with_name("bug_hunt_continue.py")
    return source.read_text(encoding="utf-8")


def _continue_hook_registered(root: Path) -> bool:
    path = Path(root) / HOOKS_JSON_REL
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    hooks = data.get("hooks") if isinstance(data, dict) else None
    stop = hooks.get("stop") if isinstance(hooks, dict) else None
    if not isinstance(stop, list):
        return False
    return any(
        isinstance(item, dict) and item.get("command") == CONTINUE_HOOK_COMMAND for item in stop
    )


def _hooks_document(root: Path) -> dict:
    """Parse hooks.json. A broken file raises before any install write."""
    path = Path(root) / HOOKS_JSON_REL
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BugHuntError(f"existing hooks.json is not valid JSON: {path}") from exc
    else:
        data = {"version": 1, "hooks": {}}
    if not isinstance(data, dict):
        raise BugHuntError(f"existing hooks.json is not a JSON object: {path}")
    return data


def ensure_continue_hook(root: Path, *, pause_seconds: int = 0) -> bool:
    """Add the bug-hunt stop hook without removing other hook events. True if the file changed."""
    path = Path(root) / HOOKS_JSON_REL
    data = _hooks_document(root)
    data.setdefault("version", 1)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    stop = hooks.get("stop")
    if not isinstance(stop, list):
        stop = []
        hooks["stop"] = stop
    needed_timeout = max(CONTINUE_HOOK_TIMEOUT, max(0, pause_seconds) + 30)
    entry = {
        "command": CONTINUE_HOOK_COMMAND,
        "timeout": needed_timeout,
        "loop_limit": CONTINUE_HOOK_LOOP_LIMIT,
    }
    for item in stop:
        if isinstance(item, dict) and item.get("command") == CONTINUE_HOOK_COMMAND:
            changed = False
            current = item.get("timeout")
            if not isinstance(current, int) or isinstance(current, bool) or current < needed_timeout:
                item["timeout"] = needed_timeout
                changed = True
            if item.get("loop_limit") != CONTINUE_HOOK_LOOP_LIMIT:
                item["loop_limit"] = CONTINUE_HOOK_LOOP_LIMIT
                changed = True
            if not changed:
                return False
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
            tmp.replace(path)
            return True
    stop.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)
    return True


def install_bug_hunt(
    root: Path,
    iterations: int = DEFAULT_ITERATIONS,
    *,
    pause_seconds: int | None = None,
    force: bool = True,
) -> BugHuntInstall:
    count = validate_iterations(iterations)
    pause = validate_pause_seconds(pause_seconds)
    target = resolve_bug_hunt_root(root)
    _hooks_document(target)

    dual_lane, overlay = _prompt_options(target)
    prompt = render_agent_prompt(
        count,
        pause_seconds=pause,
        dual_lane=dual_lane,
        overlay=overlay,
    )
    command_path = target / COMMAND_REL
    rule_path = target / RULE_REL
    packet_path = target / PACKET_REL
    scripts_path = target / SCRIPTS_REL
    written: list[str] = []
    pairs = (
        (
            command_path,
            render_cursor_command(count, pause_seconds=pause, dual_lane=dual_lane, overlay=overlay),
            COMMAND_REL,
        ),
        (rule_path, render_cursor_rule(), RULE_REL),
        (packet_path, prompt, PACKET_REL),
        (scripts_path, prompt, SCRIPTS_REL),
    )
    for path, content, rel in pairs:
        if _write_if_needed(path, content, force=force):
            written.append(rel.as_posix())
    hook_path = target / CONTINUE_HOOK_REL
    if _write_if_needed(hook_path, render_continue_hook(), force=force):
        written.append(CONTINUE_HOOK_REL.as_posix())
    if ensure_continue_hook(target, pause_seconds=pause):
        written.append(HOOKS_JSON_REL.as_posix())
    return BugHuntInstall(
        root=target,
        iterations=count,
        pause_seconds=pause,
        command_path=command_path,
        rule_path=rule_path,
        packet_path=packet_path,
        files_written=written,
    )
