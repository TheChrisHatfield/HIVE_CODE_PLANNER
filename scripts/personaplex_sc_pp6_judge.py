"""PP-T10e / SC-PP6 text-token judge (R49/R50 split).

Same prompt/WAV: bf16 offline vs q8 offline, then q8 live. A quality-gap *note*
is not a pass (G12). moshika-rag speech weights, moshi_rag_q8_local, and
cpu-offload cannot pass.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_MIN_WORDS = 3


def tokens_look_intelligible(text: str | None) -> bool:
    if text is None:
        return False
    return len(_WORD_RE.findall(str(text))) >= _MIN_WORDS


def sc_pp6_quality_holds(
    *,
    prompt_id: str,
    wav_id: str,
    bf16_offline_text: str,
    q8_offline_text: str,
    q8_live_text: str | None,
    same_prompt: bool,
    same_wav: bool,
    used_moshika_rag_weights: bool = False,
    used_moshi_rag_q8_local: bool = False,
    cpu_offload: bool = False,
    gap_note_only: bool = False,
) -> bool:
    """True only when the R49/R50 ladder is a real pass, not a written gap."""
    if gap_note_only:
        return False
    if used_moshika_rag_weights or used_moshi_rag_q8_local or cpu_offload:
        return False
    if not same_prompt or not same_wav:
        return False
    if not prompt_id or not wav_id:
        return False
    if not tokens_look_intelligible(bf16_offline_text):
        return False
    if not tokens_look_intelligible(q8_offline_text):
        return False
    if not tokens_look_intelligible(q8_live_text):
        return False
    return True


def verdict_from_record(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    holds = sc_pp6_quality_holds(
        prompt_id=str(data.get("prompt_id") or ""),
        wav_id=str(data.get("wav_id") or ""),
        bf16_offline_text=str(data.get("bf16_offline_text") or ""),
        q8_offline_text=str(data.get("q8_offline_text") or ""),
        q8_live_text=data.get("q8_live_text"),
        same_prompt=bool(data.get("same_prompt")),
        same_wav=bool(data.get("same_wav")),
        used_moshika_rag_weights=bool(data.get("used_moshika_rag_weights")),
        used_moshi_rag_q8_local=bool(data.get("used_moshi_rag_q8_local")),
        cpu_offload=bool(data.get("cpu_offload")),
        gap_note_only=bool(data.get("gap_note_only")),
    )
    return {"holds": holds, "sc_pp6": "pass" if holds else "fail"}


def main() -> None:
    parser = argparse.ArgumentParser("personaplex_sc_pp6_judge")
    parser.add_argument("--record", type=Path, required=True, help="JSON with the four-way transcripts")
    args = parser.parse_args()
    out = verdict_from_record(args.record)
    print(json.dumps(out, indent=2))
    if not out["holds"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
