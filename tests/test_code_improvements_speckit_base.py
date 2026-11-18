"""Windows PATHEXT: dispatch_command must resolve .cmd shims via shutil.which."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "spec-kit"
    / "src"
    / "specify_cli"
    / "integrations"
    / "base.py"
)


def _mod():
    spec = importlib.util.spec_from_file_location("speckit_integrations_base_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _dummy(module):
    class Dummy(module.IntegrationBase):
        key = "cursor-agent"

        def build_exec_args(self, prompt, *, model=None, output_json=True):
            return [self.key, "-p", prompt]

    return Dummy()


def test_dispatch_command_resolves_cmd_shim_for_subprocess() -> None:
    module = _mod()
    dummy = _dummy(module)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "ok"
    mock_result.stderr = ""
    fake_path = r"C:\Users\foo\AppData\Local\cursor-agent\cursor-agent.CMD"
    with (
        patch.object(module.shutil, "which", return_value=fake_path),
        patch("subprocess.run", return_value=mock_result) as mock_run,
    ):
        result = dummy.dispatch_command("speckit.plan", stream=False, timeout=5)
    assert result["exit_code"] == 0
    argv = mock_run.call_args[0][0]
    assert argv[0] == fake_path
    assert argv[1:3] == ["-p", "/speckit.plan"]


def test_dispatch_command_passthrough_when_which_finds_nothing() -> None:
    module = _mod()
    dummy = _dummy(module)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    with (
        patch.object(module.shutil, "which", return_value=None),
        patch("subprocess.run", return_value=mock_result) as mock_run,
    ):
        dummy.dispatch_command("speckit.plan", stream=False, timeout=5)
    argv = mock_run.call_args[0][0]
    assert argv[0] == "cursor-agent"
