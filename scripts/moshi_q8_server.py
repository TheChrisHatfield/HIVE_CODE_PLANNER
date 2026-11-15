"""Launch upstream `moshi.server` on a local q8 checkpoint (A3c, 2026-11-15).

Hive starts this file as a child process when `moshi_autostart` is true and the four q8 keys in
`.hive/voice-bot/config.json` are set (`moshi_q8_weights`, `moshi_mimi_weights`, `moshi_tokenizer`,
`moshi_model_config`). HIVE never imports the model; this child does.

It carries the three Windows/inference fixes found in the A3 spike. It does not edit the Moshi
source tree:
  1. `safetensors.load_file` is replaced by a streaming reader that honors `device`. Upstream loads
     every LM tensor on CPU otherwise. This must run before `moshi` is imported.
  2. `AbstractEventLoop.add_signal_handler` is a no-op on Windows (no SIGTERM handler there).
  3. Mimi and LM are `eval()` with `requires_grad=False`, or `pcm.numpy()` fails in the output loop.

Env the caller must set (upstream exits without them): `REFERENCE_ENCODER_URL` and `LLM_BASE_URL`
(+ `LLM_API_KEY`, `LLM_MODEL_NAME`). `NO_TORCH_COMPILE=1` and `NO_CUDA_GRAPH=1` are recommended on
Windows. `PYTHONPATH` must include the moshi-rag source (with the q8 `quantize.py` fix) and the
xformers shim.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
from pathlib import Path

import safetensors.torch as st
import torch

_DT = {
    "F32": torch.float32,
    "BF16": torch.bfloat16,
    "F16": torch.float16,
    "I8": torch.int8,
    "U8": torch.uint8,
    "I32": torch.int32,
    "I64": torch.int64,
}


def stream_load(filename, device="cpu"):
    """Read a .safetensors file tensor by tensor and place each tensor on `device`."""
    out = {}
    with open(filename, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))
        base = 8 + n
        header.pop("__metadata__", None)
        for key, meta in header.items():
            start, end = meta["data_offsets"]
            f.seek(base + start)
            raw = bytearray(f.read(end - start))
            if not raw:
                t = torch.empty(meta["shape"], dtype=_DT[meta["dtype"]])
            else:
                t = torch.frombuffer(raw, dtype=_DT[meta["dtype"]]).reshape(meta["shape"]).clone()
            out[key] = t.to(device) if str(device) != "cpu" else t
    return out


def share_loaded_models(get_moshi):
    """Wrap `CheckpointInfo.get_moshi` so each distinct load happens once (R37 share point, 15d).

    Every websocket session builds its own speech-to-text LM through `get_moshi`. On a 16 GiB card
    the second copy runs out of memory. The key is the checkpoint weights, lora, and the call args,
    so different checkpoints never share an entry. Sessions run one at a time (slot limit 1), so
    the one shared LM is never driven by two streams at once.
    """
    cache: dict = {}

    def shared(self, *args, **kwargs):
        key = (
            str(getattr(self, "moshi_weights", "")),
            str(getattr(self, "lora_weights", "")),
            repr(args),
            repr(sorted(kwargs.items(), key=lambda item: item[0])),
        )
        if key not in cache:
            cache[key] = get_moshi(self, *args, **kwargs)
        else:
            # The previous session's LMGen left streaming state on this LM and never stopped it.
            # Clear it so the next session can start streaming (moshi asserts "already streaming").
            stop = getattr(cache[key], "_stop_streaming", None)
            if callable(stop):
                stop()
        return cache[key]

    shared.cache = cache  # exposed for tests
    return shared


async def no_wait_stt_shutdown(self) -> None:
    """Replacement for `LocalSpeechToText.shutdown` (R37 slot race, 15e).

    Upstream queues an end marker, then waits up to 2 s for the transcript iterator to consume it.
    `Channel.run()` cancels that iterator when the client closes, so nothing consumes the marker and
    every close holds the server's one batch slot for the full 2 s. Here the marker is queued, the
    iterator is not awaited, and the completion event is set at once. The slot frees on close.
    """
    await self._out_queue.put(None)
    self.shutdown_complete.set()


def apply_fast_stt_shutdown(stt_cls) -> None:
    """Install `no_wait_stt_shutdown` on the speech-to-text class (launcher-only, no upstream edit)."""
    stt_cls.shutdown = no_wait_stt_shutdown


def _parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="moshi_q8_server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8998)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--q8", type=Path, required=True, help="model.q8.safetensors")
    p.add_argument("--mimi", type=Path, required=True, help="bf16 Mimi tokenizer checkpoint")
    p.add_argument("--tokenizer", type=Path, required=True, help="sentencepiece model")
    p.add_argument("--config", type=Path, required=True, help="moshi model config json")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse(sys.argv[1:] if argv is None else argv)
    for label, path in (("q8", args.q8), ("mimi", args.mimi), ("tokenizer", args.tokenizer), ("config", args.config)):
        if not path.is_file():
            raise SystemExit(f"moshi_q8_server: {label} file not found: {path}")

    # Patch before `moshi` is imported: moshi binds load_file at import time.
    st.load_file = stream_load

    from moshi import server  # noqa: E402
    from moshi.models import loaders  # noqa: E402
    from moshi.stt.local_stt import LocalSpeechToText  # noqa: E402

    asyncio.events.AbstractEventLoop.add_signal_handler = lambda self, sig, cb, *a: None
    apply_fast_stt_shutdown(LocalSpeechToText)  # R37 15e: slot frees on close, no 2 s wait

    def _frozen(model):
        model.eval()
        for param in model.parameters():
            param.requires_grad_(False)
        return model

    orig_mimi = loaders.CheckpointInfo.get_mimi
    orig_moshi = loaders.CheckpointInfo.get_moshi
    shared_moshi = share_loaded_models(orig_moshi)
    loaders.CheckpointInfo.get_mimi = lambda self, *a, **k: _frozen(orig_mimi(self, *a, **k))
    loaders.CheckpointInfo.get_moshi = lambda self, *a, **k: _frozen(shared_moshi(self, *a, **k))

    sys.argv = [
        "moshi.server",
        "--host", args.host,
        "--port", str(args.port),
        "--device", args.device,
        "--config", str(args.config),
        "--moshi-weight", str(args.q8),
        "--mimi-weight", str(args.mimi),
        "--tokenizer", str(args.tokenizer),
        "--batch-size", "1",
        "--log-level", "INFO",
    ]
    server.main()


if __name__ == "__main__":
    main()
