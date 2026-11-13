from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "voice_g5_live_probe.py"


def _load():
    spec = importlib.util.spec_from_file_location("voice_g5_live_probe", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_does_not_start_live_runner():
    with patch("tempfile.mkdtemp") as mkdtemp:
        probe = _load()
        mkdtemp.assert_not_called()
        assert probe.RUNNING_WAIT_S == 180
        assert probe.TERMINAL_WAIT_S == 240


def test_missing_task_id_skips_wait(tmp_path: Path):
    probe = _load()

    class Runner:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def submit(self, *args, **kwargs):
            return {"status": "error"}

        def close(self) -> None:
            pass

    with (
        patch("tempfile.mkdtemp", return_value=str(tmp_path)),
        patch.object(probe, "make_repo", return_value=None),
        patch.object(probe, "VoiceTaskRunner", Runner),
        patch.object(probe, "wait_task_state") as wait_running,
        patch.object(probe, "wait_task_terminal") as wait_term,
    ):
        out = probe.main()
    wait_running.assert_not_called()
    wait_term.assert_not_called()
    assert out["error"] == "first submit returned no task_id"
    assert out["first_submit"]["task_id"] is None


def test_running_wait_uses_request_timeout(tmp_path: Path):
    probe = _load()
    task = type("T", (), {"state": "running", "reason": "ok"})()

    class Runner:
        def __init__(self, *args, **kwargs) -> None:
            self.state = type("S", (), {"coding_tasks": {"t1": task}})()

        def submit(self, *args, **kwargs):
            return {"status": "ok", "task_id": "t1", "state": "queued"}

        def interrupt_playback(self) -> None:
            pass

        def close(self) -> None:
            pass

    with (
        patch("tempfile.mkdtemp", return_value=str(tmp_path)),
        patch.object(probe, "make_repo", return_value=None),
        patch.object(probe, "VoiceTaskRunner", Runner),
        patch.object(probe, "wait_task_state") as wait_running,
        patch.object(probe, "wait_task_terminal", return_value="completed") as wait_term,
    ):
        out = probe.main()
    assert wait_running.call_args.kwargs["timeout"] == probe.RUNNING_WAIT_S
    assert wait_term.call_args.kwargs["timeout"] == probe.TERMINAL_WAIT_S
    assert out["terminal_state"] == "completed"
