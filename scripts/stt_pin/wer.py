"""Dependency-free helpers for the T033 / T042 STT pin (WER and file hashes)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def normalize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return text.split()


def word_edits(ref: list[str], hyp: list[str]) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
