"""PP-T10d: CUDA graphs take streaming_sum as an argument; NO_CUDA_GRAPH disables."""

from __future__ import annotations

import inspect
import os
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


def test_pp_t10d_graphed_main_takes_streaming_sum_arg():
    from moshi.models.lm import LMGen

    src = inspect.getsource(LMGen.step)
    assert "state.graphed_main(input_, streaming_sum)" in src
    init = inspect.getsource(LMGen._init_streaming_state)
    assert "cuda_graphs_enabled" in init


def test_pp_t10d_no_cuda_graph_env(monkeypatch):
    from moshi.utils.compile import cuda_graphs_enabled, step_meets_12_5_hz

    monkeypatch.setenv("NO_CUDA_GRAPH", "1")
    assert cuda_graphs_enabled() is False
    monkeypatch.setenv("NO_CUDA_GRAPH", "0")
    assert cuda_graphs_enabled() is True
    monkeypatch.delenv("NO_CUDA_GRAPH", raising=False)
    assert cuda_graphs_enabled() is True
    assert step_meets_12_5_hz(0.080) is True
    assert step_meets_12_5_hz(0.081) is False


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
def test_pp_t10d_graphs_see_updated_streaming_sum(monkeypatch):
    """Live sum is a CUDAGraphed argument (G170). Graphs on: new SCB-sized add is visible."""
    monkeypatch.setenv("NO_CUDA_GRAPH", "0")
    from moshi.utils.compile import CUDAGraphed, cuda_graphs_enabled

    assert cuda_graphs_enabled() is True

    def add_sum(seq: torch.Tensor, streaming_sum: torch.Tensor) -> torch.Tensor:
        return seq + streaming_sum

    graphed = CUDAGraphed(add_sum, warmup_steps=1, disable=False)
    seq = torch.zeros(2, 4, device="cuda")
    s1 = torch.ones(2, 4, device="cuda")
    s2 = torch.full((2, 4), 3.0, device="cuda")
    out0 = graphed(seq, s1)
    assert torch.allclose(out0, s1)
    out1 = graphed(seq, s1)
    assert torch.allclose(out1, s1)
    out2 = graphed(seq, s2)
    assert torch.allclose(out2, s2), "replay must copy_ new streaming_sum into the graph"


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
def test_pp_t10d_no_cuda_graph_eager_sum(monkeypatch):
    monkeypatch.setenv("NO_CUDA_GRAPH", "1")
    from moshi.utils.compile import CUDAGraphed

    def add_sum(seq: torch.Tensor, streaming_sum: torch.Tensor) -> torch.Tensor:
        return seq + streaming_sum

    graphed = CUDAGraphed(add_sum, warmup_steps=0, disable=False)
    seq = torch.zeros(2, 4, device="cuda")
    s = torch.ones(2, 4, device="cuda") * 4
    out = graphed(seq, s)
    assert graphed._graph is None
    assert torch.allclose(out, s)
