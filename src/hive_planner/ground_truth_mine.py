"""Ground-truth mine agent script (hook: planning.rosetta).

The stones, cartridges, and PDFs are a training distribution for one inference.
They pin a temporary ground truth. They are not a single deterministic label.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

COMMAND_REL = Path(".cursor") / "commands" / "ground-truth-on-mine.md"
RULE_REL = Path(".cursor") / "rules" / "ground-truth-on-mine.mdc"
PACKET_REL = Path(".hive") / "ground-truth-on-mine" / "AGENT_PROMPT.md"
SCRIPTS_REL = Path("scripts") / "ground-truth-on-mine.md"
OVERLAY_REL = Path(".hive") / "ground-truth-on-mine" / "repo-overlay.md"

TRIGGER_PHRASES = (
    "okay runner ground truth on mine",
    "ok runner ground truth on mine",
    "runner ground truth on mine",
    "ground truth on mine",
    "run ground truth on mine",
    "runner ground truth mine",
    "/ground-truth-on-mine",
    "/runner-ground-truth-on-mine",
)

_COMMAND_QUESTION = re.compile(
    r"(?i)^\s*(how\s+(do\s+i|does|to)|where\s+(is|does)|what\s+(is|does)|does)\b"
)
_DOCS_QUESTION = re.compile(
    r"(?i)\b(?:how\s+(?:do\s+i|does|to)|where\s+(?:is|does)|what\s+(?:is|does))\b.{0,80}?\bground\s+truth\b"
)
_SLASH = re.compile(r"(?i)(?:^|\s)/(?:runner-)?ground-truth-on-mine\b")
_CALL = re.compile(
    r"(?i)\brunner\s+ground\s+truth(?:\s+on\s+mine|\s+mine)?\b"
    r"|\bground\s+truth\s+on\s+mine\b"
    r"|\brun\s+(?:the\s+)?ground\s+truth\s+mine\b"
)


class GroundTruthMineError(Exception):
    """Ground-truth mine install failed."""


@dataclass
class GroundTruthMineInstall:
    root: Path
    command_path: Path
    rule_path: Path
    packet_path: Path
    files_written: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "command": COMMAND_REL.as_posix(),
            "rule": RULE_REL.as_posix(),
            "packet": PACKET_REL.as_posix(),
            "scripts": SCRIPTS_REL.as_posix(),
            "overlay": OVERLAY_REL.as_posix(),
            "files_written": list(self.files_written),
        }


def is_ground_truth_mine_request(text: str) -> bool:
    """True when chat text asks to run the mine, not when it asks how the command works."""
    if not text or not str(text).strip():
        return False
    raw = str(text).strip()
    has_signal = bool(_SLASH.search(raw) or _CALL.search(raw))
    if not has_signal:
        return False
    if _COMMAND_QUESTION.search(raw) or _DOCS_QUESTION.search(raw):
        return False
    return True


def resolve_ground_truth_root(root: Path) -> Path:
    """Directory that receives mine files. Workspace files resolve to their folder."""
    target = Path(root).resolve()
    if target.is_file() and target.suffix.lower() == ".code-workspace":
        from hive_planner.launcher.service import resolve_linked_project_root

        folder = resolve_linked_project_root(target)
        if folder is None:
            raise GroundTruthMineError(f"workspace has no folder on disk: {target}")
        target = folder
    if not target.is_dir():
        raise GroundTruthMineError(f"repo root is not a directory: {target}")
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


def render_agent_prompt(*, overlay: str = "") -> str:
    """The mine script agents execute. One pass, then stop. The repo stays unchanged."""
    base = """Execute one ground-truth mine on the active question. Treat the Rosetta stones, the cartridges, and the PDF sources as a training distribution you condition on for this inference. They are a sounding board and a temporary ground truth. They are not a single deterministic label, and they do not authorize edits by themselves.

Bootstrap from what you already know about this repo, then pin that prior against the sources. Search when the sources disagree or stop. Report the temporary reading and stop. Do not write the result into `AGENTS.md`, the spec, the cartridges, or code unless the same user message asked you to record it.

## Call

The user starts this by saying **okay runner ground truth on mine**, or a close form of that phrase. The rest of their message is the question to mine. If they name no question, mine the open unknowns on the active feature.

## Stance

A trained network fits a distribution. Read the stones and cartridges the same way. A claim can be a real sample from the sources and still not be the only valid reading. Keep derived information provisional. Do not finish a truncated hook, a missing stone, or a cut-off sentence from guesswork.

## Sources, in this order

1. **Prior (bootstrap, not evidence).** `docs/planning-rosetta-stone.md`, `AGENTS.md`, the active feature named there or in `.hive/project.json`, `docs/delta/20_micro/<feature>.md`, and `docs/specs/<feature>/spec.md`. Use only the slices the question needs.
2. **Stones (index, not the body).** Search `context-library/sources/imported/` for the note that maps each cartridge file to its own Rosetta Stone. A cut-off at the end of a file is an export boundary.
3. **Cartridges (the conversation).** The file the stone names, at the span the stone names. Do not treat a stage banner as the hook map.
4. **PDFs (paper distribution).** `context-library/indexes/document-index.json` and the files under `context-library/sources/`. Start with the paper the question is about. Reference repos stay external evidence. They do not raise empirical fidelity by themselves.

Repo-specific pins, when this project has them, are appended below. Edit `.hive/ground-truth-on-mine/repo-overlay.md` and refresh with `py -3.11 -m hive_planner ground-truth-on-mine`.

## Temporary feedback loop

Run this loop until the temporary ground truth is stable for this turn, or until two searches add nothing the sources already said.

1. State the question in one sentence.
2. Write the prior in a few lines. Label it prior.
3. Pin it with the stone that indexes the relevant span, then with the cartridge lines that stone points at.
4. Pin it with the PDF passage that speaks to the same claim. A cartridge line the PDF does not support stays provisional.
5. Write the **temporary ground truth**: the overlap of prior, stone, cartridge, and PDF for this inference only. Name what would falsify it.
6. Where they disagree, or where a stone is cut off, search the indexed sources. A new hit updates the temporary reading. It does not overwrite the PDF or the cartridges.
7. Stop when the next search would only repeat a source you already used.

## Report

- **Temporary ground truth** — the conditioned reading for this turn, with the file and the spot that pins it.
- **Distribution** — other readings the same sources still allow.
- **Hypothesis** — what you derived. Mark it as derived.
- **Unresolved** — truncated hooks, missing stone text, unpublished steps, or PDF silence.
- **Searches** — what you opened after the first pin, and whether it moved the reading.

Leave the repo unchanged. The live spec remains the build authorization. The stones do not authorize implementation.
"""
    extra = ""
    if overlay:
        extra += overlay if overlay.startswith("\n") else f"\n{overlay}\n"
    return base + extra


def render_cursor_rule() -> str:
    """Always-on trigger so the call phrase starts the installed script."""
    listed = ", ".join(f'"{phrase}"' for phrase in TRIGGER_PHRASES)
    return f"""---
description: Start the ground-truth mine when the user says okay runner ground truth on mine
alwaysApply: true
---

# Runner ground truth on mine

**Hook:** `planning.rosetta`

When the user asks to run this mine in any chat on this repo — the message is or clearly requests it, including {listed} — read `.cursor/commands/ground-truth-on-mine.md` and execute that script in this turn. If that file is missing, read `scripts/ground-truth-on-mine.md`. Start the mine in this turn. Do not reply with instructions for how to invoke the command. Do not paste the script back. Do not write findings into `AGENTS.md`, the spec, the cartridges, or code unless the same message asked you to record them.

Match intent, not only an exact string: "okay, runner, ground truth on mine" or "run the ground truth mine" are start signals. A question about the command itself (whether it works, where the file is, how to call it) is not a start signal.
"""


def render_cursor_command(*, overlay: str = "") -> str:
    body = render_agent_prompt(overlay=overlay)
    return (
        "---\n"
        "description: Mine Rosetta stones, cartridges, and PDF sources as a temporary "
        "ground-truth distribution (okay runner ground truth on mine).\n"
        "---\n\n"
        f"{body}"
    )


def preview_agent_prompt(root: Path) -> str:
    """Same script text install would write, including the repo overlay, without writing files."""
    try:
        target = resolve_ground_truth_root(root)
    except GroundTruthMineError:
        target = Path(root).resolve()
    return render_agent_prompt(overlay=_read_repo_overlay(target))


def _write_if_needed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return True


def missing_ground_truth_mine_artifacts(root: Path) -> list[str]:
    """Relative paths that must exist after a successful install."""
    try:
        target = resolve_ground_truth_root(root)
    except GroundTruthMineError:
        target = Path(root).resolve()
    missing: list[str] = []
    for rel in (COMMAND_REL, RULE_REL, PACKET_REL, SCRIPTS_REL):
        if not (target / rel).is_file():
            missing.append(rel.as_posix())
    return missing


def install_ground_truth_mine(root: Path, *, force: bool = True) -> GroundTruthMineInstall:
    target = resolve_ground_truth_root(root)
    overlay = _read_repo_overlay(target)
    prompt = render_agent_prompt(overlay=overlay)
    command_path = target / COMMAND_REL
    rule_path = target / RULE_REL
    packet_path = target / PACKET_REL
    scripts_path = target / SCRIPTS_REL
    written: list[str] = []
    pairs = (
        (command_path, render_cursor_command(overlay=overlay), COMMAND_REL),
        (rule_path, render_cursor_rule(), RULE_REL),
        (packet_path, prompt, PACKET_REL),
        (scripts_path, prompt, SCRIPTS_REL),
    )
    for path, content, rel in pairs:
        if _write_if_needed(path, content, force=force):
            written.append(rel.as_posix())
    return GroundTruthMineInstall(
        root=target,
        command_path=command_path,
        rule_path=rule_path,
        packet_path=packet_path,
        files_written=written,
    )
