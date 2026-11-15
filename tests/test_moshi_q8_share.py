"""R37 share point (15d): the q8 launcher loads each speech-to-text LM once, not once per session.

Pure cache test. It imports the launcher module (torch and safetensors are needed) but loads no
checkpoint: the wrapped `get_moshi` is a counting fake.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "moshi_q8_server.py"


def _launcher():
    spec = importlib.util.spec_from_file_location("moshi_q8_server", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _checkpoint(weights: str) -> SimpleNamespace:
    return SimpleNamespace(moshi_weights=weights, lora_weights=None)


def test_two_sessions_on_one_checkpoint_load_the_lm_once():
    launcher = _launcher()
    loads: list[str] = []

    def fake_get_moshi(self, *args, **kwargs):
        loads.append(self.moshi_weights)
        return object()  # one fresh model per real load

    shared = launcher.share_loaded_models(fake_get_moshi)
    stt = _checkpoint("stt.safetensors")

    first = shared(stt, device="cuda:0", dtype="bf16")
    second = shared(stt, device="cuda:0", dtype="bf16")  # second websocket session

    assert first is second
    assert loads == ["stt.safetensors"]


class _StreamingLM:
    """Mimics moshi's StreamingModule: streaming_forever asserts when state is already set."""

    def __init__(self) -> None:
        self._streaming_state = None

    def streaming_forever(self) -> None:
        assert self._streaming_state is None, "lm is already streaming!"
        self._streaming_state = object()

    def _stop_streaming(self) -> None:
        self._streaming_state = None


def test_second_session_can_start_streaming_on_the_shared_lm():
    """Regression for the 15d live rerun: session 1 never stops streaming, session 2 must still start."""
    launcher = _launcher()
    shared = launcher.share_loaded_models(lambda self, *a, **k: _StreamingLM())
    stt = _checkpoint("stt.safetensors")

    first_session = shared(stt, device="cuda:0")
    first_session.streaming_forever()  # LocalSpeechToText.__init__ on session 1; never stopped

    second_session = shared(stt, device="cuda:0")  # session 2 gets the same LM back
    assert second_session is first_session
    second_session.streaming_forever()  # must not raise "already streaming"


def test_stt_shutdown_returns_at_once_without_a_consumer():
    """R37 15e: upstream LocalSpeechToText.shutdown waits 2 s for an iterator that the channel
    already cancelled, which holds the one slot after every close. The launcher patch must not wait."""
    import asyncio
    import time

    launcher = _launcher()

    class FakeStt:
        pass

    launcher.apply_fast_stt_shutdown(FakeStt)

    async def run() -> float:
        stt = FakeStt()
        stt._out_queue = asyncio.Queue()
        stt.shutdown_complete = asyncio.Event()
        stt.shutdown_complete.clear()  # state after start_up(); no __aiter__ consumer is running
        started = time.monotonic()
        await stt.shutdown()
        assert stt.shutdown_complete.is_set()
        assert stt._out_queue.get_nowait() is None
        return time.monotonic() - started

    elapsed = asyncio.run(run())
    assert elapsed < 0.5, f"shutdown waited {elapsed:.2f}s; the slot would stay held"


def test_different_checkpoints_or_args_are_not_shared():
    launcher = _launcher()
    loads: list[str] = []

    def fake_get_moshi(self, *args, **kwargs):
        loads.append(self.moshi_weights)
        return object()

    shared = launcher.share_loaded_models(fake_get_moshi)

    a = shared(_checkpoint("main.safetensors"), device="cuda:0")
    b = shared(_checkpoint("stt.safetensors"), device="cuda:0")
    c = shared(_checkpoint("stt.safetensors"), device="cpu")

    assert a is not b and b is not c
    assert loads == ["main.safetensors", "stt.safetensors", "stt.safetensors"]
