"""PP-T10c: q8 get_moshi_lm dtype skip, fp16 remaining floats, no meta QLinear."""

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
    import importlib

    root = str(_MOSHI_ROOT)
    saved = {key: sys.modules[key] for key in list(sys.modules) if key == "moshi" or key.startswith("moshi.")}
    for key in saved:
        del sys.modules[key]
    saved_path = list(sys.path)
    while root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)
    importlib.invalidate_caches()
    try:
        yield
    finally:
        for key in list(sys.modules):
            if key == "moshi" or key.startswith("moshi."):
                del sys.modules[key]
        sys.modules.update(saved)
        sys.path[:] = saved_path


@pytest.fixture(autouse=True)
def _isolate_working_moshi():
    with _working_moshi():
        yield


def test_pp_t10c_cast_preserves_int8_uint8_scb():
    from moshi.models.loaders import _cast_loaded_tensor, _q8_serve_dtype

    dev = torch.device("cpu")
    i8 = torch.zeros(2, dtype=torch.int8)
    u8 = torch.zeros(2, dtype=torch.uint8)
    scb = torch.ones(2, dtype=torch.float32)
    bf = torch.ones(2, dtype=torch.bfloat16)
    assert _cast_loaded_tensor("blk.weight", i8, dev, torch.float16).dtype == torch.int8
    assert _cast_loaded_tensor("blk.weight", u8, dev, torch.float16).dtype == torch.uint8
    assert _cast_loaded_tensor("blk.weight_scb", scb, dev, torch.float16).dtype == torch.float32
    assert _cast_loaded_tensor("blk.weight", bf, dev, torch.float16).dtype == torch.float16
    assert _q8_serve_dtype(True, torch.bfloat16) == torch.float16
    assert _q8_serve_dtype(False, torch.bfloat16) == torch.bfloat16


def test_pp_t10c_get_moshi_lm_source_q8_order():
    from moshi.models.loaders import get_moshi_lm, _get_moshi_lm_with_offload

    src = inspect.getsource(get_moshi_lm)
    assert "quantize = True" in src
    assert "copy_missing_weights = False" in src
    assert "_q8_serve_dtype" in src
    assert "_cast_loaded_tensor" in src
    assert 'init_device = "meta" if filename is not None and not quantize else device' in src
    assert "cpu_offload is not supported with q8" in src
    off = inspect.getsource(_get_moshi_lm_with_offload)
    assert "_cast_loaded_tensor" in off


def test_pp_t10c_expand_refuses_int8():
    from moshi.models.loaders import _patch_depformer_self_attn_shapes

    class _M(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.depformer = torch.nn.Module()
            self.depformer.self_attn = torch.nn.Linear(4, 8, bias=False)

    state = {"depformer.self_attn.weight": torch.zeros(4, 4, dtype=torch.int8)}
    with pytest.raises(RuntimeError, match="quantized shape"):
        _patch_depformer_self_attn_shapes(_M(), state, False)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
def test_pp_t10c_qlinear_cuda_matmul_no_scb_crash():
    """G7: one GPU QLinear matmul. Full 7B LMGen.step waits on the q8 file (PP-T10d)."""
    pytest.importorskip("bitsandbytes")
    from moshi.utils.quantize import QLinear

    lin = torch.nn.Linear(8, 8, bias=False).to(device="cuda", dtype=torch.float16)
    q = QLinear(lin)
    x = torch.randn(2, 8, device="cuda", dtype=torch.float16)
    y = q(x)
    assert y is not None
    assert y.device.type == "cuda"
