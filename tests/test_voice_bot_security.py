"""T017 (path part, R23): workspace path validation through the real submit path.

Every refusal is asserted through `VoiceTaskRunner.submit` (the tool dispatch path) and, for the
main escape cases, through the bridge's `POST /v1/submit`. The provider factory raises if it is
ever called, so a refused path is proven to stop before any agent process starts.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from hive_planner.config import RepoPaths
from hive_planner.voice_bridge import VoiceBridge
from hive_planner.voice_task import DelegationError, VoiceTaskRunner


def _no_provider(handler: Any) -> Any:
    raise AssertionError("a refused request must not start a provider session")


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    (tmp_path / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n", encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return RepoPaths(root=tmp_path)


@pytest.fixture
def outside_file(repo: RepoPaths) -> Path:
    """A real file next to the workspace, so the refusal is about location, not existence."""
    target = repo.root.parent / "outside_secret.txt"
    target.write_text("do not read", encoding="utf-8")
    yield target
    target.unlink(missing_ok=True)


@pytest.fixture
def runner(repo: RepoPaths):
    r = VoiceTaskRunner(repo, "Voice_Bot", client_factory=_no_provider, request_timeout=5)
    yield r
    r.close()


def _refused_code(runner: VoiceTaskRunner, file_path: str) -> str:
    with pytest.raises(DelegationError) as exc:
        runner.submit("explain add", client_request_id=f"sec-{abs(hash(file_path))}", file_path=file_path)
    return exc.value.code


def test_relative_parent_escape_is_refused_before_any_task_exists(runner):
    assert _refused_code(runner, "../outside_secret.txt") == "path_outside_workspace"
    assert runner.state.coding_tasks == {}
    assert runner.state.queue == []


def test_absolute_path_outside_the_workspace_is_refused_even_when_the_file_exists(runner, outside_file):
    assert _refused_code(runner, str(outside_file)) == "path_outside_workspace"
    assert runner.state.coding_tasks == {}


def test_nested_escape_that_resolves_outside_is_refused(runner):
    assert _refused_code(runner, "src/../../outside_secret.txt") == "path_outside_workspace"


@pytest.mark.skipif(os.name != "nt", reason="backslash separators are only path separators on Windows")
def test_backslash_parent_escape_is_refused_on_windows(runner):
    assert _refused_code(runner, "..\\outside_secret.txt") == "path_outside_workspace"


def test_missing_file_inside_the_workspace_is_refused_as_not_found(runner):
    assert _refused_code(runner, "src/missing.py") == "file_not_found"
    assert runner.state.coding_tasks == {}


def test_a_file_inside_the_workspace_passes_path_validation(repo, monkeypatch):
    """Positive control: the same code path accepts an in-workspace file (the refusals above are not blanket)."""
    started: list[str] = []

    def fake_launch(self, task_id):
        started.append(task_id)

    monkeypatch.setattr(VoiceTaskRunner, "_launch", fake_launch)
    r = VoiceTaskRunner(repo, "Voice_Bot", client_factory=_no_provider, request_timeout=5)
    try:
        out = r.submit("explain add", client_request_id="sec-ok", file_path="src/app.py")
        assert out["task_id"] in r.state.coding_tasks
        assert r.state.coding_tasks[out["task_id"]].file_path == "src/app.py"
        assert started == [out["task_id"]]
    finally:
        r.close()


def test_bridge_submit_refuses_escape_with_400_and_creates_no_task(repo, outside_file):
    r = VoiceTaskRunner(repo, "Voice_Bot", client_factory=_no_provider, request_timeout=5)
    bridge = VoiceBridge(r)
    bridge.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{bridge.port}/v1/submit",
            data=json.dumps({
                "workspace": str(repo.root), "instruction": "read it", "client_request_id": "sec-b1",
                "file_path": str(outside_file),
            }).encode("utf-8"),
            method="POST",
        )
        req.add_header("Authorization", f"Bearer {bridge.token}")
        req.add_header("Content-Type", "application/json")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        assert exc.value.code == 400
        assert json.loads(exc.value.read().decode("utf-8"))["error"] == "path_outside_workspace"
        assert r.state.coding_tasks == {}
    finally:
        bridge.close()
        r.close()
