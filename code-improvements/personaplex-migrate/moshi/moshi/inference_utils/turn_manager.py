# Copyright (c) Kyutai, all rights reserved.
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""RAG conversation context from duplex LM text tokens (PersonaPlex PP8).

Moshi-RAG fills `user:` lines from `stt/`. PersonaPlex has no STT in this path.
Until a VAD exists (PP14), speaker is the duplex text-token stream: attributed
pieces, or `user:` / `moshi:` prefixes inside decoded codebook text.
"""

from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

ROLE_PREFIX_MAPPING = {
    "model": "moshi: ",
    "user": "user: ",
}

# PersonaPlex / Moshi-family specials (server.py text_token_map).
_EPAD = 0
_BOS = 1
_EOS = 2
_PAD = 3
_SKIP_IDS = {_EPAD, _BOS, _PAD}


def _printable(text: str) -> str:
    return "".join(ch for ch in text if ch.isprintable())


def speaker_from_piece(piece: str) -> str | None:
    """Return `user` or `model` when the decoded piece names a Moshi-family role."""
    stripped = piece.replace("▁", " ").lstrip()
    if stripped.startswith("user:"):
        return "user"
    if stripped.startswith("moshi:"):
        return "model"
    return None


def strip_role_prefix(piece: str) -> str:
    text = piece.replace("▁", " ")
    stripped = text.lstrip()
    for prefix in ("user:", "moshi:"):
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].lstrip()
    return text


@dataclass
class TurnManager:
    """Accumulate `user:` / `moshi:` RAG context from LM text tokens. No VAD, no STT."""

    init_active_speaker: str = "model"
    active_speaker: str = "model"
    conversation_context: str = ""
    _line_open: bool = False
    _prev_speaker: str = "model"

    def __post_init__(self):
        self.active_speaker = self.init_active_speaker
        self._prev_speaker = self.init_active_speaker
        self.conversation_context = ""
        self._line_open = False

    def get_context(self) -> str:
        return self.conversation_context

    def last_user_line(self) -> str:
        """Completed last `user:` turn body; empty skips the LLM (PP8 / PP3)."""
        query = ""
        for line in self.conversation_context.split("\n"):
            if line.startswith("user:"):
                text = line.split("user:", 1)[1].strip()
                text = _printable(text).strip()
                if text:
                    query = text
        return query

    def set_active_speaker(self, speaker: str) -> bool:
        """Text-token speaker change. True on user → model (Rule B edge; trigger is PP-T6)."""
        if speaker not in ROLE_PREFIX_MAPPING:
            raise ValueError(f"Invalid speaker: {speaker}")
        prev = self.active_speaker
        if speaker == prev:
            return False
        self._close_line()
        self._prev_speaker = prev
        self.active_speaker = speaker
        logger.info("[State] text-token speaker %s -> %s", prev, speaker)
        return prev == "user" and speaker == "model"

    def feed_lm_piece(self, piece: str, speaker: str | None = None) -> bool:
        """Append one decoded codebook piece. Returns True on user → model change."""
        handed = False
        named = speaker_from_piece(piece)
        role = speaker or named
        if role is not None:
            handed = self.set_active_speaker(role)
        body = strip_role_prefix(piece) if named else piece.replace("▁", " ")
        body = _printable(body)
        if not body:
            return handed
        self._append_body(body)
        return handed

    def feed_token(self, token_id: int, piece: str, speaker: str | None = None) -> bool:
        """Consume one LM text-token id + decoded piece. PAD/EPAD/BOS are not lexical."""
        if token_id == _EOS:
            self._close_line()
            return False
        if token_id in _SKIP_IDS:
            return False
        return self.feed_lm_piece(piece, speaker=speaker)

    def _append_body(self, body: str) -> None:
        if not self._line_open:
            prefix = "\n" if self.conversation_context else ""
            self.conversation_context += prefix + ROLE_PREFIX_MAPPING[self.active_speaker]
            self._line_open = True
        self.conversation_context += body

    def _close_line(self) -> None:
        self._line_open = False

    def reset(self):
        self.__post_init__()
