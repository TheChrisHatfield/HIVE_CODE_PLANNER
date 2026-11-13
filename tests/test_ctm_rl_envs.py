from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np

SRC = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "continuous-thought-machines"
    / "tasks"
    / "rl"
    / "envs.py"
)


def _mod():
    gym = types.ModuleType("gymnasium")

    class Wrapper:
        def __init__(self, env) -> None:
            self.env = env

    gym.Wrapper = Wrapper
    gym.Env = object
    sys.modules.setdefault("gymnasium", gym)
    spec = importlib.util.spec_from_file_location("ctm_rl_envs", SRC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCartPole:
    spec = types.SimpleNamespace(id="CartPole-v1")

    def __init__(self) -> None:
        self.resets = 0

    def step(self, action):
        return np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32), 1.0, True, False, {"from": "step"}

    def reset(self, **kwargs):
        self.resets += 1
        return np.array([9.0, 8.0, 7.0, 6.0], dtype=np.float32), {"from": "reset"}


def test_terminal_step_stays_terminal_after_auto_reset() -> None:
    env = FakeCartPole()
    wrapped = _mod().MaskVelocityWrapper(env)
    obs, reward, terminated, truncated, info = wrapped.step(0)
    assert env.resets == 1
    assert reward == 1.0
    assert terminated is True
    assert truncated is False
    assert info == {"from": "reset"}
    np.testing.assert_array_equal(obs, np.array([9.0, 0.0, 7.0, 0.0], dtype=np.float32))
