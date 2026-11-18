from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import torch

SRC = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "huggingface_guess"
    / "huggingface_guess"
    / "diffusers_convert.py"
)


def _mod():
    spec = importlib.util.spec_from_file_location("huggingface_guess_diffusers_convert", SRC)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_convert_unet_state_dict_converts_present_keys_without_the_static_map():
    mod = _mod()
    weight = torch.ones(2)
    out = mod.convert_unet_state_dict({"down_blocks.0.resnets.0.norm1.weight": weight})
    assert list(out) == ["input_blocks.1.0.in_layers.0.weight"]
    assert out["input_blocks.1.0.in_layers.0.weight"] is weight


def test_convert_unet_state_dict_raises_when_two_keys_share_a_destination():
    mod = _mod()
    with pytest.raises(ValueError, match="unet rename collision"):
        mod.convert_unet_state_dict(
            {
                "conv_in.weight": torch.zeros(1),
                "input_blocks.0.0.weight": torch.ones(1),
            }
        )
