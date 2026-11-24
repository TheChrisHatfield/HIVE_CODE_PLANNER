"""Launch the PersonaPlex working-copy `moshi.server` (PP-T8).

Hive starts this file when `speech_child=personaplex`. Do not edit `moshi_q8_server.py`.
NVIDIA argv only: no `--q8`, `--config`, or `--max-reference-tokens`. No STT / loop probe.
Keep log prefixes `q8 step` / `q8 recv` for hive_inspect_audio (G180).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
from pathlib import Path

_DT = None


def _torch_dtypes():
    global _DT
    import torch

    if _DT is None:
        _DT = {
            "F32": torch.float32,
            "BF16": torch.bfloat16,
            "F16": torch.float16,
            "I8": torch.int8,
            "U8": torch.uint8,
            "I32": torch.int32,
            "I64": torch.int64,
        }
    return torch, _DT


def stream_load(filename, device="cpu"):
    """Read a .safetensors file tensor by tensor and place each tensor on `device`."""
    torch, dtypes = _torch_dtypes()
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
                t = torch.empty(meta["shape"], dtype=dtypes[meta["dtype"]])
            else:
                t = torch.frombuffer(raw, dtype=dtypes[meta["dtype"]]).reshape(meta["shape"]).clone()
            out[key] = t.to(device) if str(device) != "cpu" else t
    return out


def share_get_moshi_lm(get_moshi_lm):
    cache: dict = {}

    def shared(*args, **kwargs):
        key = (repr(args), repr(sorted(kwargs.items(), key=lambda item: item[0])))
        if key not in cache:
            cache[key] = get_moshi_lm(*args, **kwargs)
        else:
            stop = getattr(cache[key], "_stop_streaming", None)
            if callable(stop):
                stop()
        return cache[key]

    shared.cache = cache
    return shared


def enable_cuda_tf32(torch_mod) -> None:
    try:
        if not bool(torch_mod.cuda.is_available()):
            return
        torch_mod.backends.cuda.matmul.allow_tf32 = True
        torch_mod.backends.cudnn.allow_tf32 = True
        if hasattr(torch_mod, "set_float32_matmul_precision"):
            torch_mod.set_float32_matmul_precision("high")
    except (AttributeError, RuntimeError, TypeError):
        return


def _parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="personaplex_server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8998)
    p.add_argument("--device", default="cuda")
    p.add_argument("--moshi-weight", type=Path, required=True)
    p.add_argument("--mimi-weight", type=Path, required=True)
    p.add_argument("--tokenizer", type=Path, required=True)
    p.add_argument("--static", default="none")
    p.add_argument("--voice-prompt-dir", type=str, default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse(sys.argv[1:] if argv is None else argv)
    for label, path in (
        ("moshi-weight", args.moshi_weight),
        ("mimi-weight", args.mimi_weight),
        ("tokenizer", args.tokenizer),
    ):
        if not path.is_file():
            raise SystemExit(f"personaplex_server: {label} file not found: {path}")

    import safetensors.torch as st  # noqa: E402

    torch, _ = _torch_dtypes()
    enable_cuda_tf32(torch)
    st.load_file = stream_load

    from moshi import server  # noqa: E402
    from moshi.models import loaders  # noqa: E402

    asyncio.events.AbstractEventLoop.add_signal_handler = lambda self, sig, cb, *a: None

    def _frozen(model):
        model.eval()
        for param in model.parameters():
            param.requires_grad_(False)
        return model

    orig_lm = loaders.get_moshi_lm
    orig_mimi = loaders.get_mimi
    shared_lm = share_get_moshi_lm(orig_lm)
    loaders.get_moshi_lm = lambda *a, **k: _frozen(shared_lm(*a, **k))
    loaders.get_mimi = lambda *a, **k: _frozen(orig_mimi(*a, **k))

    import os  # noqa: E402

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

    from moshi.llm.client import LLMClient  # noqa: E402
    from hive_planner.voice_moshi_generation import REFERENCE_MAX_TOKENS, install_llm_temperature  # noqa: E402

    install_llm_temperature(LLMClient)

    from moshi.inference_utils.rag_manager import RAGManager  # noqa: E402

    if not getattr(RAGManager, "_hive_max_tokens_wrapped", False):
        _orig_rag_init = RAGManager.__init__

        def _rag_init(self, reference_generator, rag_timeout=1.5, max_tokens=512, gt_reference_text=None):
            _orig_rag_init(
                self,
                reference_generator,
                rag_timeout,
                REFERENCE_MAX_TOKENS,
                gt_reference_text,
            )

        RAGManager.__init__ = _rag_init
        RAGManager._hive_max_tokens_wrapped = True

    from moshi.reference.llm_reference_generator import LLMReferenceGenerator  # noqa: E402

    if os.environ.get("HIVE_RETRIEVAL_SOURCES", "").strip():
        from hive_planner.voice_moshi_retrieval import install_from_env  # noqa: E402

        install_from_env(LLMReferenceGenerator, os.environ)

    from hive_planner.voice_moshi_generation import install_empty_turn_seed  # noqa: E402

    install_empty_turn_seed(LLMReferenceGenerator)

    if os.environ.get("HIVE_RETRIEVAL_ENABLED", "1").strip() == "0":
        from hive_planner.voice_moshi_generation import install_retrieval_off  # noqa: E402

        install_retrieval_off(LLMReferenceGenerator)

    from moshi.models.lm import LMGen  # noqa: E402
    from hive_planner.voice_moshi_generation import install_step_counter  # noqa: E402

    install_step_counter(LMGen)

    import sphn  # noqa: E402
    from hive_planner.voice_moshi_generation import install_recv_counter  # noqa: E402

    install_recv_counter(sphn.OpusStreamReader)

    child_argv = [
        "moshi.server",
        "--host", str(args.host),
        "--port", str(args.port),
        "--device", str(args.device),
        "--moshi-weight", str(args.moshi_weight),
        "--mimi-weight", str(args.mimi_weight),
        "--tokenizer", str(args.tokenizer),
        "--static", str(args.static or "none"),
    ]
    if args.voice_prompt_dir:
        child_argv.extend(["--voice-prompt-dir", str(args.voice_prompt_dir)])
    sys.argv = child_argv
    server.main()


if __name__ == "__main__":
    main()
