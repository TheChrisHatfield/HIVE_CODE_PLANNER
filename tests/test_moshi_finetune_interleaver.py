from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

SRC = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "moshi-finetune"
    / "finetune"
    / "data"
    / "interleaver.py"
)


def _mod():
    spec = importlib.util.spec_from_file_location("moshi_finetune_interleaver", SRC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _interleaver(rate: float):
    tokenizer = SimpleNamespace(bos_id=lambda: 1, eos_id=lambda: 2, encode=lambda *a, **k: [3])
    return _mod().Interleaver(
        tokenizer,
        audio_frame_rate=rate,
        text_padding=0,
        end_of_text_padding=4,
        zero_padding=5,
        device="cpu",
    )


def test_text_stream_uses_interleaver_rate_and_encoded_frame_count() -> None:
    this_num = 10
    mimi_rate = 12.5
    inter = _interleaver(25.0)
    old = inter.build_token_stream(None, this_num / mimi_rate)
    assert old.shape[-1] == 20
    duration = this_num / inter.audio_frame_rate
    tokens = inter.prepare_item(None, duration, num_frames=this_num)
    assert tokens.shape[-1] == this_num


def test_num_frames_stops_ceil_from_lengthening_the_text_stream() -> None:
    rate = 12.5
    n = next(
        i
        for i in range(1, 500)
        if math.ceil((i / rate) * rate) != i
    )
    inter = _interleaver(rate)
    drifted = inter.build_token_stream(None, n / rate)
    assert drifted.shape[-1] != n
    tokens = inter.prepare_item(None, n / rate, num_frames=n)
    assert tokens.shape[-1] == n


def test_window_keeps_a_word_that_overlaps_the_start() -> None:
    alignments = [
        ("hello", (0.8, 1.2), "SPEAKER_MAIN"),
        ("world", (1.2, 1.6), "SPEAKER_MAIN"),
    ]
    got = _mod().window_alignments(alignments, start_sec=1.0, duration_sec=1.0)
    assert [row[0] for row in got] == ["hello", "world"]
    assert got[0][1] == (0.8 - 1.0, 1.2 - 1.0)


def test_old_dicho_slice_dropped_the_overlapping_word() -> None:
    alignments = [
        ("hello", (0.8, 1.2), "SPEAKER_MAIN"),
        ("world", (1.2, 1.6), "SPEAKER_MAIN"),
    ]
    start_sec = 1.0
    duration_sec = 1.0
    start_i = _mod().dicho(alignments, start_sec)
    end_i = _mod().dicho(alignments, start_sec + duration_sec)
    assert [row[0] for row in alignments[start_i:end_i]] == ["world"]
