"""SC-PP11 / PP-E1 judges. Missing live step rate is fail-closed. Not Voice_Bot G7."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SC_PP11_MIN_HZ = 12.5


def sc_pp11_holds(
    *,
    after_handshake: bool,
    step_hz: float | None,
    is_prefill: bool = False,
    stt_in_loop: bool = False,
    labeled_g7: bool = False,
) -> bool:
    """True only when duplex after 0x00 holds ≥12.5 Hz without STT-in-loop or prefill."""
    if labeled_g7 or stt_in_loop or is_prefill or not after_handshake:
        return False
    if step_hz is None:
        return False
    try:
        hz = float(step_hz)
    except (TypeError, ValueError):
        return False
    return hz >= SC_PP11_MIN_HZ


def pp_e1_holds(
    *,
    live_mic: bool,
    retrieve: bool,
    encoder: bool,
    streaming_sum: bool,
    consume_steps: int,
    step_hz: float | None,
    labeled_g7: bool = False,
    is_prefill: bool = False,
) -> bool:
    """Live RAG-conditioned Opus row. A G7 label or missing mic/sum/rate is not a pass."""
    if labeled_g7 or not live_mic or is_prefill:
        return False
    if not (retrieve and encoder and streaming_sum and int(consume_steps) >= 2):
        return False
    return sc_pp11_holds(
        after_handshake=True,
        step_hz=step_hz,
        is_prefill=False,
        stt_in_loop=False,
        labeled_g7=False,
    )


def verdict_from_record(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    sc = sc_pp11_holds(
        after_handshake=bool(data.get("after_handshake")),
        step_hz=data.get("step_hz"),
        is_prefill=bool(data.get("is_prefill")),
        stt_in_loop=bool(data.get("stt_in_loop")),
        labeled_g7=bool(data.get("labeled_g7")),
    )
    e1 = pp_e1_holds(
        live_mic=bool(data.get("live_mic")),
        retrieve=bool(data.get("retrieve")),
        encoder=bool(data.get("encoder")),
        streaming_sum=bool(data.get("streaming_sum")),
        consume_steps=int(data.get("consume_steps") or 0),
        step_hz=data.get("step_hz"),
        labeled_g7=bool(data.get("labeled_g7")),
        is_prefill=bool(data.get("is_prefill")),
    )
    return {"sc_pp11": sc, "pp_e1": e1, "holds": bool(sc and e1)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="personaplex_sc_pp11_judge")
    p.add_argument("--record", type=Path, required=True)
    args = p.parse_args(argv)
    row = verdict_from_record(args.record)
    print(json.dumps(row, indent=2))
    return 0 if row["holds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
