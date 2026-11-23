"""PP-T10b: personaplex_q8_local export contracts (CPU inspect, no 16.7 GB load)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest


def _load_script():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "personaplex_q8_local.py"
    spec = importlib.util.spec_from_file_location("personaplex_q8_local_t10b", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pp_t10b_main_lm_only_copy_missing_replace_once():
    mod = _load_script()
    src = inspect.getsource(mod.main)
    assert "hf_hub_download" not in src
    assert "fuse_lora" not in src
    assert "moshi_rag_q8_local" not in src
    assert "get_mimi" not in src
    assert "copy_missing_weights=True" in src
    assert "quantize=False" in src
    assert "replace_linear_with_qlinear(model)" in src
    assert src.count("replace_linear_with_qlinear(") == 1
    assert "torch.no_grad()" in src
    assert "model.eval()" in src
    assert "requires_grad_(False)" in src
    assert "q8_export_config" in src


def test_pp_t10b_config_quantize_true_nvidia_shape():
    mod = _load_script()
    cfg = mod.q8_export_config("model.q8.safetensors", "model.safetensors")
    assert cfg["quantize"] is True
    assert cfg["model_type"] == "personaplex"
    assert cfg["version"] == "7b-v1"
    assert "conditioners" not in cfg


def test_pp_t10b_refuse_cpu_device():
    mod = _load_script()
    with pytest.raises(SystemExit, match="cuda"):
        mod.require_export_device("cpu")
    assert mod.require_export_device("cuda") == "cuda"
    assert mod.require_export_device("cuda:1") == "cuda:1"


def test_pp_t10b_script_never_imports_rag_exporter():
    path = Path(__file__).resolve().parents[1] / "scripts" / "personaplex_q8_local.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
    assert "moshi_rag_q8_local" not in names
    assert "huggingface_hub" not in names
