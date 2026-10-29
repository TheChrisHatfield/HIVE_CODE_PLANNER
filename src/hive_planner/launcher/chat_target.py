"""Chat-target adapter: resolve a display name and deliver one phrase.

The Controls Execute button calls this module. It does not read Cursor's
database and it does not submit a chat itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

OUTCOMES = ("sent", "not_found", "refused", "already_generating", "failed")

OUTCOME_TEXT = {
    "sent": "sent",
    "not_found": "not found",
    "refused": "refused",
    "already_generating": "already generating",
    "failed": "failed",
}

# Command on the block does not change these phrases.
EXECUTE_PHRASES = {
    "Bug hunt": "bug hunt",
    "CodeSpec": "code spec",
    "Agnostic loop": "agnostic loop",
}


class ChatTarget(Protocol):
    def deliver(self, name: str, repo: Path, phrase: str) -> str:
        """Return one outcome from OUTCOMES."""


def execute_controls(loop: str, name: str, repo: Path, adapter: ChatTarget) -> str:
    """Map the selected loop to its start phrase and return the adapter outcome."""
    phrase = EXECUTE_PHRASES.get(loop)
    if phrase is None:
        return "failed"
    outcome = adapter.deliver(name, repo, phrase)
    if outcome not in OUTCOME_TEXT:
        return "failed"
    return outcome


def outcome_text(outcome: str) -> str:
    return OUTCOME_TEXT.get(outcome, OUTCOME_TEXT["failed"])
