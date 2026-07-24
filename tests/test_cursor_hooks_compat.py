"""Cursor 3.x hook compatibility checks for Hive project + CL plugin hooks."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run_hook(script: Path, stdin: str = "{}") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        input=stdin,
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        check=False,
    )


def test_hooks_json_has_numeric_version() -> None:
    project = json.loads((ROOT / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert project["version"] == 1
    assert "workspaceOpen" in project["hooks"]
    assert "sessionStart" in project["hooks"]
    assert "stop" in project["hooks"]
    assert "afterFileEdit" in project["hooks"]
    matcher = project["hooks"]["afterFileEdit"][0].get("matcher", "")
    assert "Write" in matcher
    assert "AGENTS" not in matcher  # path matchers are invalid on Cursor 3.x


def test_workspace_open_emits_plugin_paths() -> None:
    result = _run_hook(ROOT / ".cursor" / "hooks" / "hive_workspace_open.py")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    paths = payload["pluginPaths"]
    assert len(paths) == 1
    assert paths[0].endswith("hive-continual-learning")
    assert (Path(paths[0]) / ".cursor-plugin" / "plugin.json").is_file()


def test_cl_plugin_hooks_use_python_not_bun() -> None:
    plugin_hooks = json.loads(
        (ROOT / ".cursor" / "plugins" / "hive-continual-learning" / "hooks" / "hooks.json").read_text(
            encoding="utf-8"
        )
    )
    assert plugin_hooks["version"] == 1
    command = plugin_hooks["hooks"]["stop"][0]["command"]
    assert "py -3.11" in command
    assert "continual-learning-stop.py" in command
    assert "bun" not in command
    assert (
        ROOT
        / ".cursor"
        / "plugins"
        / "hive-continual-learning"
        / "hooks"
        / "continual-learning-stop.py"
    ).is_file()


def test_session_start_emits_additional_context_json() -> None:
    result = _run_hook(ROOT / ".cursor" / "hooks" / "hive_session_start.py")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert "additional_context" in payload
    assert "Hive" in payload["additional_context"]


def test_session_stop_emits_empty_json_object() -> None:
    result = _run_hook(
        ROOT / ".cursor" / "hooks" / "hive_session_stop.py",
        stdin='{"status":"completed","loop_count":0}',
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {}


def test_agents_lint_hook_emits_json_for_non_agents_path() -> None:
    result = _run_hook(
        ROOT / ".cursor" / "hooks" / "hive_agents_lint.py",
        stdin=json.dumps({"file_path": str(ROOT / "README.md"), "edits": []}),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {}


def test_session_start_fail_open_emits_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exceptions must still yield valid Cursor JSON on stdout."""
    import importlib.util

    script = ROOT / ".cursor" / "hooks" / "hive_session_start.py"
    spec = importlib.util.spec_from_file_location("hive_session_start_failopen", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(
        mod.sys.stdin, "isatty", lambda: (_ for _ in ()).throw(RuntimeError("forced"))
    )
    assert mod.main() == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert "additional_context" in payload
    assert "forced" in payload["additional_context"] or "error" in payload["additional_context"].lower()


def test_continual_learning_stop_emits_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    script = (
        ROOT
        / ".cursor"
        / "plugins"
        / "hive-continual-learning"
        / "hooks"
        / "continual-learning-stop.py"
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(
            {
                "status": "completed",
                "loop_count": 0,
                "generation_id": "gen-1",
                "transcript_path": None,
            }
        ),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {}
    state = tmp_path / ".cursor" / "hooks" / "state" / "continual-learning.json"
    assert state.is_file()
