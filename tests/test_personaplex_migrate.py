"""PP-T12 / SC-PP2: pending streaming_sum must be consumed on ≥2 LMGen.step calls."""

from __future__ import annotations

import inspect
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

_MOSHI_ROOT = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "personaplex-migrate"
    / "moshi"
)


@contextmanager
def _working_moshi():
    """Load the PersonaPlex working copy even if another moshi is already imported."""
    root = str(_MOSHI_ROOT)
    saved = {key: sys.modules[key] for key in list(sys.modules) if key == "moshi" or key.startswith("moshi.")}
    for key in saved:
        del sys.modules[key]
    inserted = root not in sys.path
    if inserted:
        sys.path.insert(0, root)
    try:
        yield
    finally:
        for key in list(sys.modules):
            if key == "moshi" or key.startswith("moshi."):
                del sys.modules[key]
        sys.modules.update(saved)
        if inserted:
            try:
                sys.path.remove(root)
            except ValueError:
                pass


def test_lmgen_step_source_applies_pending_before_graphed_main():
    with _working_moshi():
        from moshi.models import lm as lm_mod

        src = inspect.getsource(lm_mod.LMGen.step)
        apply_at = src.find("apply_pending_streaming_sum_condition")
        graphed_at = src.find("graphed_main")
        assert apply_at != -1, "LMGen.step must call apply_pending_streaming_sum_condition"
        assert graphed_at != -1
        assert apply_at < graphed_at, "apply_pending must run before graphed_main (G171)"
        assert "streaming_sum" in src, "graphed_main must take streaming_sum (G170)"
        assert "pin_kv_prefix" not in src, "RAG step must not re-pin (SC-PP3 / G80)"


def test_sum_update_and_apply_do_not_call_pin():
    with _working_moshi():
        from moshi.models import lm as lm_mod

        update_src = inspect.getsource(lm_mod.LMGen.update_streaming_sum_tensors)
        apply_src = inspect.getsource(lm_mod.LMGen.apply_pending_streaming_sum_condition)
        assert "pin_kv_prefix" not in update_src
        assert "pin_kv_prefix" not in apply_src


def test_sc_pp3_pinned_frame_count_unchanged_after_first_sum():
    """G280: pinned KV frame count before vs after first apply_pending is the same integer."""
    with _working_moshi():
        from moshi.models.lm import LMGen, _LMGenState
        from moshi.modules.transformer import PinnedRingKVCache

        device = torch.device("cpu")
        cache = PinnedRingKVCache(
            1,
            1,
            4,
            capacity=16,
            max_pinned=8,
            max_period=10000.0,
            device=device,
            dtype=torch.float32,
        )
        cache.cache[0, :, :, :4].fill_(1)
        cache.cache[1, :, :, :4].fill_(1)
        cache.end_offset.fill_(4)
        cache.pin(4)
        before = int(cache.pinned_n.item())

        class _DummyLM:
            dim = 8
            dtype = torch.float32
            device = torch.device("cpu")

        gen = LMGen.__new__(LMGen)
        gen.lm_model = _DummyLM()
        gen.cfg_coef = 1.0
        gen._streaming_state = _LMGenState(
            cache=torch.zeros(1, 1, 1),
            provided=torch.zeros(1, 1, 1, dtype=torch.bool),
            initial=torch.zeros(1, 1, 1),
            graphed_main=None,  # type: ignore[arg-type]
            graphed_embeddings=None,  # type: ignore[arg-type]
            graphed_depth=None,  # type: ignore[arg-type]
            condition_streaming_sum=torch.zeros(1, 1, 8),
            pending_streaming_sums=[None],
        )
        gen.update_streaming_sum_tensors([torch.arange(16, dtype=torch.float32).reshape(1, 2, 8)])
        gen.apply_pending_streaming_sum_condition()
        after = int(cache.pinned_n.item())
        assert before == 4
        assert after == before


def test_step_embeddings_does_not_add_rag():
    with _working_moshi():
        from moshi.models import lm as lm_mod

        src = inspect.getsource(lm_mod.LMGen.step_embeddings)
        assert "apply_pending_streaming_sum_condition" not in src
        assert "streaming_sum" not in src


def test_forward_codes_takes_streaming_sum_argument():
    with _working_moshi():
        from moshi.models.lm import LMModel

        params = inspect.signature(LMModel.forward_codes).parameters
        assert "streaming_sum" in params


def test_update_squeezes_and_apply_pending_consumes_two_frames():
    """SC-PP2: consume on ≥2 apply_pending calls; update-without-consume is not a pass."""
    with _working_moshi():
        from moshi.models.lm import LMGen, _LMGenState

        class _DummyLM:
            dim = 8
            dtype = torch.float32
            device = torch.device("cpu")

        gen = LMGen.__new__(LMGen)
        gen.lm_model = _DummyLM()
        gen.cfg_coef = 1.0
        pending_buf = torch.zeros(1, 1, 8)
        state = _LMGenState(
            cache=torch.zeros(1, 1, 1),
            provided=torch.zeros(1, 1, 1, dtype=torch.bool),
            initial=torch.zeros(1, 1, 1),
            graphed_main=None,  # type: ignore[arg-type]
            graphed_embeddings=None,  # type: ignore[arg-type]
            graphed_depth=None,  # type: ignore[arg-type]
            condition_streaming_sum=pending_buf,
            pending_streaming_sums=[None],
        )
        gen._streaming_state = state

        encoder = torch.arange(16, dtype=torch.float32).reshape(1, 2, 8)
        gen.update_streaming_sum_tensors([encoder])
        pending = state.pending_streaming_sums[0]
        assert pending is not None
        assert pending.shape == (2, 8)

        gen.apply_pending_streaming_sum_condition()
        assert state.apply_pending_count == 1
        assert torch.equal(state.condition_streaming_sum[0, 0], encoder[0, 0])

        gen.apply_pending_streaming_sum_condition()
        assert state.apply_pending_count == 2
        assert torch.equal(state.condition_streaming_sum[0, 0], encoder[0, 1])

        gen.apply_pending_streaming_sum_condition()
        assert torch.equal(state.condition_streaming_sum[0, 0], torch.zeros(8))


def test_update_refuses_cfg_not_one():
    with _working_moshi():
        from moshi.models.lm import LMGen

        gen = LMGen.__new__(LMGen)
        gen.cfg_coef = 1.1
        gen._streaming_state = object()
        with pytest.raises(RuntimeError, match="cfg_coef"):
            gen.update_streaming_sum_tensors([None])


def test_update_fail_closed_on_dim_mismatch():
    with _working_moshi():
        from moshi.models.lm import LMGen, _LMGenState

        class _DummyLM:
            dim = 8
            dtype = torch.float32
            device = torch.device("cpu")

        gen = LMGen.__new__(LMGen)
        gen.lm_model = _DummyLM()
        gen.cfg_coef = 1.0
        gen._streaming_state = _LMGenState(
            cache=torch.zeros(1, 1, 1),
            provided=torch.zeros(1, 1, 1, dtype=torch.bool),
            initial=torch.zeros(1, 1, 1),
            graphed_main=None,  # type: ignore[arg-type]
            graphed_embeddings=None,  # type: ignore[arg-type]
            graphed_depth=None,  # type: ignore[arg-type]
            condition_streaming_sum=torch.zeros(1, 1, 8),
            pending_streaming_sums=[None],
        )
        with pytest.raises(RuntimeError, match="dim"):
            gen.update_streaming_sum_tensors([torch.zeros(2, 7)])


def test_working_copy_lm_not_shadowed_by_other_moshi():
    import types

    keys = ("moshi", "moshi.models", "moshi.models.lm")
    prior = {key: sys.modules.get(key) for key in keys}
    fake_lm = types.ModuleType("moshi.models.lm")

    class LMGen:
        def step(self) -> None:
            return None

    fake_lm.LMGen = LMGen
    sys.modules["moshi"] = types.ModuleType("moshi")
    sys.modules["moshi.models"] = types.ModuleType("moshi.models")
    sys.modules["moshi.models.lm"] = fake_lm
    try:
        test_lmgen_step_source_applies_pending_before_graphed_main()
    finally:
        for key, module in prior.items():
            if module is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = module


def test_encoder_packages_ported_into_working_copy():
    root = _MOSHI_ROOT / "moshi"
    assert (root / "conditioners" / "base.py").is_file()
    assert (root / "server_conditioner.py").is_file()
    assert (root / "inference_utils" / "utils.py").is_file()
    src = (root / "inference_utils" / "utils.py").read_text(encoding="utf-8")
    assert "squeeze(0)" in src


def test_pp_t3_rag_context_from_duplex_text_tokens_not_stt():
    with _working_moshi():
        from moshi.inference_utils import turn_manager as tm_mod
        from moshi.inference_utils.turn_manager import TurnManager
        import moshi.inference_utils as inf

        tm_src = Path(tm_mod.__file__).read_text(encoding="utf-8")
        init_src = Path(inf.__file__).read_text(encoding="utf-8")
        assert "import" not in tm_src or "stt" not in [
            line.split()[1] if line.startswith("import ") else ""
            for line in tm_src.splitlines()
        ]
        assert "from moshi.stt" not in tm_src
        assert "from .stt" not in tm_src
        assert "from .channel" not in init_src
        assert "AudioProcessor" not in init_src

        tm = TurnManager()
        assert tm.get_context() == ""
        assert tm.last_user_line() == ""

        tm.feed_lm_piece("what is X", speaker="user")
        tm.feed_lm_piece("I think Y", speaker="model")
        ctx = tm.get_context()
        assert ctx.startswith("user: what is X")
        assert "moshi: I think Y" in ctx
        assert tm.last_user_line() == "what is X"

        prefixed = TurnManager()
        prefixed.feed_lm_piece("user: hello")
        prefixed.feed_lm_piece("moshi: hi")
        assert prefixed.last_user_line() == "hello"
        assert "moshi: hi" in prefixed.get_context()

        handed = TurnManager()
        handed.feed_lm_piece("query", speaker="user")
        assert handed.set_active_speaker("model") is True
        assert handed.set_active_speaker("model") is False

        skipped = TurnManager()
        skipped.feed_token(3, "PAD", speaker="user")
        skipped.feed_token(0, "EPAD", speaker="user")
        skipped.feed_token(1, "BOS", speaker="user")
        assert skipped.get_context() == ""
        skipped.feed_token(42, "▁hello", speaker="user")
        assert skipped.last_user_line() == "hello"


def test_pp_t4_llm_reference_port_and_install_from_env(tmp_path):
    import asyncio
    import json

    from hive_planner.voice_moshi_retrieval import BLOCK_LABEL, install_from_env
    from hive_planner.voice_retrieval import SOURCES_ENV

    llm_dir = _MOSHI_ROOT / "moshi" / "llm"
    ref_dir = _MOSHI_ROOT / "moshi" / "reference"
    assert (llm_dir / "reference_prompt_template.txt").is_file()
    assert (llm_dir / "reference_prompt_template_simplified.txt").is_file()
    assert (llm_dir / "reference_summarization_prompt_template.txt").is_file()
    assert (llm_dir / "client.py").is_file()
    assert (ref_dir / "llm_reference_generator.py").is_file()
    assert not (
        Path(__file__).resolve().parents[1] / "scripts" / "personaplex_server.py"
    ).exists()

    with _working_moshi():
        from moshi.reference.llm_reference_generator import (
            LLMReferenceGenerator,
            clean_reference_text,
        )

        assert clean_reference_text("Reference: Paris is the capital") == "Paris is the capital"
        assert clean_reference_text("Human: what is X") == ""
        assert clean_reference_text(None) == ""

        gen = object.__new__(LLMReferenceGenerator)
        gen.summarization = False
        gen.retrieval_profiles = []
        gen._llm_by_id = {}
        gen._default_profile_id = None

        class _StubLLM:
            prompt = ""
            model_name = "stub"

            def generate(self, prompt, context, max_new_tokens=512, **kwargs):
                raise AssertionError("empty context must skip the LLM")

        gen.llm = _StubLLM()
        processed, text, turns, name = asyncio.run(gen.generate_reference_text("", []))
        assert text == ""
        assert turns == 0
        assert name == ""

        processed, text, turns, name = asyncio.run(
            gen.generate_reference_text("user:   \nmoshi: hi", [])
        )
        assert text == ""

        calls: list[str] = []

        class _ReplyLLM:
            prompt = "PROMPT"
            model_name = "stub"

            def generate(self, prompt, context, max_new_tokens=512, **kwargs):
                calls.append(context)
                return "Reference: the moon is a satellite"

        gen.llm = _ReplyLLM()
        orig_generate = LLMReferenceGenerator.generate_reference_text
        orig_process = LLMReferenceGenerator.process_reference_text
        wrapped = getattr(LLMReferenceGenerator, "_hive_retrieval_wrapped", False)
        (tmp_path / "note.md").write_text("the moon is a satellite of earth\n", encoding="utf-8")
        env = {
            SOURCES_ENV: json.dumps(
                [{"name": "kb", "kind": "docs", "target": str(tmp_path), "enabled": True}]
            )
        }
        try:
            if wrapped:
                LLMReferenceGenerator.generate_reference_text = orig_generate
                LLMReferenceGenerator.process_reference_text = orig_process
                LLMReferenceGenerator._hive_retrieval_wrapped = False
            assert install_from_env(LLMReferenceGenerator, env) is True
            processed, text, turns, name = asyncio.run(
                gen.generate_reference_text("user: what is the moon\nmoshi:", [])
            )
        finally:
            LLMReferenceGenerator.generate_reference_text = orig_generate
            LLMReferenceGenerator.process_reference_text = orig_process
            LLMReferenceGenerator._hive_retrieval_wrapped = False

        assert turns >= 1
        assert text == "the moon is a satellite"
        assert processed.startswith(BLOCK_LABEL)
        assert "the moon is a satellite of earth" in processed
        assert calls, "LLM must run after retrieve prepend"


def test_pp_t3_opus_loop_feeds_turn_manager():
    server_py = _MOSHI_ROOT / "moshi" / "server.py"
    src = server_py.read_text(encoding="utf-8")
    assert "TurnManager" in src
    assert "turn_manager.feed_token" in src
    assert "turn_manager.reset()" in src
    assert "from moshi.stt" not in src
    assert "install_stt" not in src


def test_pp_t5_async_update_reference_consumes_two_steps(monkeypatch):
    import asyncio

    with _working_moshi():
        from moshi.inference_utils.reference_update import async_update_reference
        from moshi.models.lm import LMGen, _LMGenState

        src = (_MOSHI_ROOT / "moshi" / "server.py").read_text(encoding="utf-8")
        assert "async_update_reference" in src
        assert "_async_update_reference" in src
        assert "\\x07" not in src
        assert "referencetext" not in src

        class _DummyLM:
            dim = 8
            dtype = torch.float32
            device = torch.device("cpu")

        gen = LMGen.__new__(LMGen)
        gen.lm_model = _DummyLM()
        gen.cfg_coef = 1.0
        pending_buf = torch.zeros(1, 1, 8)
        gen._streaming_state = _LMGenState(
            cache=torch.zeros(1, 1, 1),
            provided=torch.zeros(1, 1, 1, dtype=torch.bool),
            initial=torch.zeros(1, 1, 1),
            graphed_main=None,  # type: ignore[arg-type]
            graphed_embeddings=None,  # type: ignore[arg-type]
            graphed_depth=None,  # type: ignore[arg-type]
            condition_streaming_sum=pending_buf,
            pending_streaming_sums=[None],
        )
        encoder = torch.arange(16, dtype=torch.float32).reshape(2, 8)

        async def _fake_embed(text, encoder_url="http://localhost:8001", timeout=30.0):
            assert text == "Paris is the capital"
            assert encoder_url == "http://127.0.0.1:8011"
            return encoder

        monkeypatch.setenv("HIVE_REF_HOLD_FACTOR", "1")
        monkeypatch.setattr(
            "moshi.inference_utils.reference_update.get_conditioning_remote_async",
            _fake_embed,
        )
        asyncio.run(
            async_update_reference(
                gen, "Paris is the capital", encoder_url="http://127.0.0.1:8011"
            )
        )
        pending = gen._streaming_state.pending_streaming_sums[0]
        assert pending is not None
        assert pending.shape == (2, 8)
        gen.apply_pending_streaming_sum_condition()
        gen.apply_pending_streaming_sum_condition()
        assert gen._streaming_state.apply_pending_count == 2
        assert torch.equal(gen._streaming_state.condition_streaming_sum[0, 0], encoder[1])

        async def _boom(text, encoder_url="http://localhost:8001", timeout=30.0):
            raise RuntimeError("encoder down")

        monkeypatch.setattr(
            "moshi.inference_utils.reference_update.get_conditioning_remote_async",
            _boom,
        )
        asyncio.run(async_update_reference(gen, "still posts empty", encoder_url="http://x"))
        asyncio.run(async_update_reference(gen, "no url", encoder_url=""))
