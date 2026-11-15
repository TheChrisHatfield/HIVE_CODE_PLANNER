"""T017 (token part) + bridge: per-session token, R18 schema, and approval replies over loopback HTTP.

Each test drives a real VoiceTaskRunner over the stdio ACP child process and a real
ThreadingHTTPServer bound to 127.0.0.1. Replies go through the bridge; the outcome is checked in
the child's `written_result`, so the provider side is observed, not assumed.
"""

from __future__ import annotations

import dataclasses
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from hive_planner.voice_bridge import (
    VoiceBridge,
    bridge_endpoint_path,
    bridge_token_path,
    max_submit_body_bytes,
    run_turn_via_bridge,
    token_matches,
)
from hive_planner.voice_task import VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_for, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


@pytest.fixture
def bridge(runner: VoiceTaskRunner):
    b = VoiceBridge(runner)
    b.start()
    yield b
    b.close()


def _call(bridge: VoiceBridge, method: str, path: str, *, token: str | None, body: Any = None,
          raw: bytes | None = None) -> tuple[int, dict]:
    url = f"http://127.0.0.1:{bridge.port}{path}"
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    req = urllib.request.Request(url, data=data, method=method)
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _q(repo, **params: str) -> str:
    return "?" + urllib.parse.urlencode({"workspace": str(repo.root), **params})


def _await_approval(runner: VoiceTaskRunner, task_id: str) -> dict:
    wait_task_state(runner, task_id, "awaiting_approval")
    return runner.state.coding_tasks[task_id].approval


def _reply_body(repo, task_id: str, pending: dict, text: str) -> dict:
    return {"workspace": str(repo.root), "task_id": task_id, "request_id": pending["request_id"], "text": text}


def test_start_writes_token_and_endpoint_under_voice_bot_dir(repo, bridge):
    token = bridge_token_path(repo).read_text(encoding="utf-8")
    assert token == bridge.token and len(token) >= 40
    endpoint = json.loads(bridge_endpoint_path(repo).read_text(encoding="utf-8"))
    assert endpoint["host"] == "127.0.0.1" and endpoint["port"] == bridge.port


def test_token_matches_rejects_wrong_length_without_raising():
    expected = "a" * 40
    assert token_matches(expected, expected) is True
    assert token_matches("short", expected) is False
    assert token_matches(None, expected) is False
    assert token_matches("", expected) is False


def test_requests_without_or_with_wrong_token_are_refused_and_change_nothing(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="tk-1")
    pending = _await_approval(runner, out["task_id"])

    assert _call(bridge, "GET", "/v1/approval" + _q(repo), token=None) == (401, {"error": "unauthorized"})
    assert _call(bridge, "GET", "/v1/approval" + _q(repo), token="wrong") == (401, {"error": "unauthorized"})
    status, _ = _call(
        bridge, "POST", "/v1/reply", token="wrong",
        body=_reply_body(repo, out["task_id"], pending, "approve edit src/app.py"),
    )
    assert status == 401

    # Refused calls reached no runner logic: the approval is still pending and nothing executed.
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.state == "awaiting_approval"
    assert task.approvals == []
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


def test_authorized_get_exposes_pending_approval(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="gp-1")
    pending = _await_approval(runner, out["task_id"])
    status, view = _call(bridge, "GET", "/v1/approval" + _q(repo), token=bridge.token)
    assert status == 200
    assert view == {
        "pending": True,
        "request_id": pending["request_id"],
        "task_id": out["task_id"],
        "kind": "write_or_command",
        "action": "edit src/app.py",
        "file_path": "",
    }
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


def test_authorized_approve_reply_reaches_the_provider_as_selected(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="ok-1")
    pending = _await_approval(runner, out["task_id"])
    status, reply = _call(
        bridge, "POST", "/v1/reply", token=bridge.token,
        body=_reply_body(repo, out["task_id"], pending, "approve edit src/app.py"),
    )
    assert status == 200 and reply["status"] == "approved"
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    written = runner.state.coding_tasks[out["task_id"]].evidence.written_result
    assert '"outcome": "selected"' in written and '"optionId": "allow"' in written


def test_submit_after_close_over_http_includes_spoken_notice(repo, runner, bridge):
    runner.close()
    status, body = _call(
        bridge,
        "POST",
        "/v1/submit",
        token=bridge.token,
        body={
            "workspace": str(repo.root),
            "instruction": "explain add",
            "client_request_id": "bridge-session-ended-1",
            "mode": "ask",
        },
    )
    assert status == 400 and body.get("error") == "session_not_active"
    assert body.get("spoken") == "The voice session has ended. Nothing was submitted."


def test_stale_submit_over_http_includes_spoken_notice(repo, runner, bridge):
    runner.set_live_buffer(lambda _path: (42, True))
    status, body = _call(
        bridge,
        "POST",
        "/v1/submit",
        token=bridge.token,
        body={
            "workspace": str(repo.root),
            "instruction": "explain add",
            "client_request_id": "bridge-stale-1",
            "mode": "ask",
            "file_path": "src/app.py",
            "editor_snapshot": {"file": "src/app.py", "document_version": 1, "dirty": False},
        },
    )
    assert status == 400 and body.get("error") == "stale"
    assert body.get("spoken")
    assert runner.state.coding_tasks == {}


def test_reply_editor_snapshot_blocks_stale_write(repo, runner, bridge):
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py",
        client_request_id="ok-stale-live",
        file_path="src/app.py",
        document_version=1,
        dirty=False,
    )
    pending = _await_approval(runner, out["task_id"])
    body = _reply_body(repo, out["task_id"], pending, "approve edit src/app.py")
    body["editor_snapshot"] = {"file": "src/app.py", "document_version": 8, "dirty": True}
    status, reply = _call(bridge, "POST", "/v1/reply", token=bridge.token, body=body)
    assert status == 200 and reply["status"] == "stale"
    wait_task_terminal(runner, out["task_id"])


def test_deny_reply_reaches_the_provider_as_cancelled(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:delete build dir", client_request_id="dn-b")
    pending = _await_approval(runner, out["task_id"])
    status, reply = _call(
        bridge, "POST", "/v1/reply", token=bridge.token,
        body=_reply_body(repo, out["task_id"], pending, "deny delete build dir"),
    )
    assert status == 200 and reply["status"] == "denied"
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    assert '"outcome": "cancelled"' in runner.state.coding_tasks[out["task_id"]].evidence.written_result


def test_stale_request_id_is_refused_and_the_current_approval_stays_pending(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="st-1")
    pending = _await_approval(runner, out["task_id"])
    status, reply = _call(
        bridge, "POST", "/v1/reply", token=bridge.token,
        body=_reply_body(repo, out["task_id"], {"request_id": "apr_old000000"}, "approve edit src/app.py"),
    )
    assert status == 409 and reply["status"] == "stale_approval"
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"

    status, reply = _call(
        bridge, "POST", "/v1/reply", token=bridge.token,
        body=_reply_body(repo, out["task_id"], pending, "approve edit src/app.py"),
    )
    assert status == 200 and reply["status"] == "approved"
    wait_task_terminal(runner, out["task_id"])


def test_reply_for_the_wrong_task_is_409_and_resolves_nothing(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="tm-1")
    pending = _await_approval(runner, out["task_id"])
    status, reply = _call(
        bridge, "POST", "/v1/reply", token=bridge.token,
        body=_reply_body(repo, "task_other000000", pending, "approve edit src/app.py"),
    )
    assert status == 409 and reply["status"] == "task_mismatch"
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


def test_reply_with_no_pending_approval_is_409_and_queues_nothing(repo, runner, bridge):
    out = runner.submit("hello", client_request_id="np-1")
    wait_task_terminal(runner, out["task_id"])
    status, reply = _call(
        bridge, "POST", "/v1/reply", token=bridge.token,
        body=_reply_body(repo, out["task_id"], {"request_id": "apr_x"}, "approve edit src/app.py"),
    )
    assert status == 409 and reply["status"] == "no_pending_approval"
    assert runner.state.queue == []


def test_malformed_bodies_are_rejected_before_the_runner(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="mb-1")
    pending = _await_approval(runner, out["task_id"])
    ws = str(repo.root)
    assert _call(bridge, "POST", "/v1/reply", token=bridge.token, raw=b"not json")[0] == 400
    assert _call(bridge, "POST", "/v1/reply", token=bridge.token, raw=b"[1,2]")[0] == 400
    assert _call(bridge, "POST", "/v1/reply", token=bridge.token,
                 body={"workspace": ws, "task_id": out["task_id"], "text": "approve x"})[0] == 400
    assert _call(bridge, "POST", "/v1/reply", token=bridge.token,
                 body={**_reply_body(repo, out["task_id"], pending, ""), "text": 5})[0] == 400
    assert _call(bridge, "GET", "/v1/other", token=bridge.token)[0] == 404
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


def test_post_submit_with_query_string_still_routes(repo, runner, bridge):
    status, sub = _call(
        bridge, "POST", "/v1/submit?trace=1", token=bridge.token,
        body={"workspace": str(repo.root), "instruction": "hello",
              "client_request_id": "bs-query"},
    )
    assert status == 200 and sub["task_id"]
    assert wait_task_terminal(runner, sub["task_id"]) == "completed"


def test_post_submit_runs_the_task_and_get_task_reports_the_result(repo, runner, bridge):
    status, sub = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                        body={"workspace": str(repo.root), "instruction": "RUN_TESTS_PASS explain add",
                              "client_request_id": "bs-1"})
    assert status == 200 and sub["task_id"] and sub["status"] in ("submitted", "running", "completed")
    assert sub["context_snapshot_id"]
    assert wait_task_terminal(runner, sub["task_id"]) == "completed"
    status, view = _call(bridge, "GET", "/v1/task" + _q(
        repo, task_id=sub["task_id"], context_snapshot_id=sub["context_snapshot_id"]), token=bridge.token)
    assert status == 200 and view["state"] == "completed"
    assert view["tests_status"] == "passed"
    assert "ran tests, exit 0" in view["written"]


def test_post_submit_duplicate_client_request_id_is_not_run_twice(repo, runner, bridge):
    body = {"workspace": str(repo.root), "instruction": "RUN_TESTS_PASS explain add", "client_request_id": "bs-dup"}
    _, first = _call(bridge, "POST", "/v1/submit", token=bridge.token, body=body)
    wait_task_terminal(runner, first["task_id"])
    status, second = _call(bridge, "POST", "/v1/submit", token=bridge.token, body=body)
    assert status == 200 and second["status"] == "duplicate" and second["task_id"] == first["task_id"]
    assert len(runner.state.coding_tasks) == 1


def test_submit_without_token_creates_no_task(repo, runner, bridge):
    status, _ = _call(bridge, "POST", "/v1/submit", token=None,
                      body={"workspace": str(repo.root), "instruction": "hello", "client_request_id": "bs-nt"})
    assert status == 401
    assert runner.state.coding_tasks == {} and runner.state.queue == []


def test_submit_refusals_come_back_as_400_with_the_refusal_code(repo, runner, bridge):
    ws = str(repo.root)
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": ws, "instruction": "hello"})  # no client_request_id
    assert status == 400 and body["error"] == "missing_client_request_id"
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": ws, "instruction": "hi", "client_request_id": "bs-x",
                               "file_path": "../secret.txt"})
    assert status == 400 and body["error"] == "path_outside_workspace"
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": ws, "instruction": "hi", "client_request_id": "bs-y", "mode": "agent"})
    assert status == 400 and body["error"] == "agent_mode_disabled"
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": ws, "instruction": 5, "client_request_id": "bs-z"})
    assert status == 400 and body["error"] == "bad_instruction"
    assert runner.state.coding_tasks == {}


# --- R18 schema validation (T017) -------------------------------------------------------


def test_missing_workspace_is_refused_before_any_task_on_every_tool(repo, runner, bridge):
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"instruction": "hello", "client_request_id": "sv-1"})
    assert status == 400 and body["error"] == "missing_workspace"
    status, body = _call(bridge, "GET", "/v1/approval", token=bridge.token)
    assert status == 400 and body["error"] == "missing_workspace"
    assert runner.state.coding_tasks == {}


def test_wrong_workspace_is_refused_and_creates_no_task(repo, runner, bridge, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": str(other), "instruction": "hello", "client_request_id": "sv-2"})
    assert status == 400 and body["error"] == "workspace_mismatch"
    status, body = _call(bridge, "GET", "/v1/approval?" + urllib.parse.urlencode({"workspace": str(other)}),
                         token=bridge.token)
    assert status == 400 and body["error"] == "workspace_mismatch"
    assert runner.state.coding_tasks == {}


def test_editor_snapshot_on_submit_keeps_version_and_diagnostics(repo, runner, bridge):
    status, body = _call(
        bridge, "POST", "/v1/submit", token=bridge.token,
        body={
            "workspace": str(repo.root),
            "instruction": "explain add",
            "client_request_id": "snap-host-1",
            "file_path": "src/app.py",
            "editor_snapshot": {
                "file": "src/app.py",
                "document_version": 7,
                "dirty": False,
                "selection": {"text": "def add(a, b):", "truncated": False},
                "diagnostics": [{"severity": "error", "message": "unused"}],
            },
        },
    )
    assert status == 200, body
    snap = runner.state.context_snapshots[runner.state.coding_tasks[body["task_id"]].context_snapshot_id]
    assert snap.document_version == 7
    assert snap.dirty is False
    assert snap.selection_text == "def add(a, b):"
    assert snap.diagnostics == ["error: unused"]
    wait_task_terminal(runner, body["task_id"])


def test_submit_body_may_exceed_the_old_16kib_cap(repo, runner, bridge):
    payload = "x" * 20_000
    status, body = _call(
        bridge, "POST", "/v1/submit", token=bridge.token,
        body={
            "workspace": str(repo.root),
            "instruction": "explain add",
            "client_request_id": "snap-body-1",
            "file_path": "src/app.py",
            "file_content": payload,
        },
    )
    assert status == 200, body
    snap = runner.state.context_snapshots[runner.state.coding_tasks[body["task_id"]].context_snapshot_id]
    assert snap.file_content == payload
    wait_task_terminal(runner, body["task_id"])


def test_unknown_argument_and_bad_shapes_are_refused_with_codes(repo, runner, bridge):
    ws = str(repo.root)
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": ws, "instruction": "hi", "client_request_id": "sv-3", "shell": "rm -rf"})
    assert status == 400 and body["error"] == "unknown_argument"
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": ws, "instruction": "hi", "client_request_id": "../etc"})
    assert status == 400 and body["error"] == "bad_client_request_id"
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": ws, "instruction": "hi", "client_request_id": "sv-4", "mode": "yolo"})
    assert status == 400 and body["error"] == "invalid_mode"
    assert runner.state.coding_tasks == {}


def test_over_limit_instruction_is_refused_by_the_schema_without_a_task(repo, runner, bridge):
    runner.config = dataclasses.replace(runner.config, instruction_max_chars=12)
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": str(repo.root), "instruction": "x" * 13, "client_request_id": "sv-5"})
    assert status == 400 and body["error"] == "instruction_too_long"
    assert runner.state.coding_tasks == {}


def test_task_view_must_name_the_tasks_own_snapshot(repo, runner, bridge):
    _, sub = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                   body={"workspace": str(repo.root), "instruction": "RUN_TESTS_PASS explain add",
                         "client_request_id": "sv-6"})
    wait_task_terminal(runner, sub["task_id"])
    status, body = _call(bridge, "GET", "/v1/task" + _q(
        repo, task_id=sub["task_id"], context_snapshot_id="ctx_not_this_one"), token=bridge.token)
    assert status == 409 and body == {"error": "context_mismatch"}
    status, body = _call(bridge, "GET", "/v1/task" + _q(repo, task_id=sub["task_id"]), token=bridge.token)
    assert status == 400 and body["error"] == "missing_context_snapshot_id"


def test_get_task_unknown_id_is_404_and_missing_id_is_400(repo, runner, bridge):
    assert _call(bridge, "GET", "/v1/task" + _q(repo, task_id="task_nope", context_snapshot_id="ctx_x"),
                 token=bridge.token) == (404, {"error": "unknown_task"})
    assert _call(bridge, "GET", "/v1/task" + _q(repo, context_snapshot_id="ctx_x"),
                 token=bridge.token)[0] == 400


class _FakeWhisper:
    """Stands in for the pinned faster-whisper adapter; no model is loaded."""

    def __init__(self, model_dir: Any) -> None:
        self.model_dir = model_dir

    def transcribe(self, audio: bytes) -> str:
        return "RUN_TESTS_PASS explain add"

    def transcribe_file(self, wav_path: Path) -> str:
        assert wav_path.is_file()
        return "RUN_TESTS_PASS explain add"


def test_spoken_route_transcribes_workspace_wav_and_submits_the_transcript(repo, runner, bridge, monkeypatch):
    import hive_planner.voice_task as voice_task

    monkeypatch.setattr(voice_task, "resolve_pinned_model_dir", lambda: repo.root)
    monkeypatch.setattr(voice_task, "FasterWhisperAdapter", _FakeWhisper)
    # voice_layer typed: this test covers the STT route, not the Moshi listen gate (T053).
    runner.config = dataclasses.replace(runner.config, stt_provider="faster-whisper", voice_layer="typed")
    (repo.root / "utt.wav").write_bytes(b"RIFF-fake")

    status, body = _call(bridge, "POST", "/v1/submit/spoken", token=bridge.token,
                         body={"workspace": str(repo.root), "wav_path": "utt.wav",
                               "client_request_id": "spk-1"})
    assert status == 200, body
    assert body["transcript"] == "RUN_TESTS_PASS explain add"
    task = runner.state.coding_tasks[body["task_id"]]
    assert task.instruction == "RUN_TESTS_PASS explain add"
    assert wait_task_terminal(runner, body["task_id"]) == "completed"


def test_spoken_route_keeps_editor_snapshot(repo, runner, bridge, monkeypatch):
    import hive_planner.voice_task as voice_task

    monkeypatch.setattr(voice_task, "resolve_pinned_model_dir", lambda: repo.root)
    monkeypatch.setattr(voice_task, "FasterWhisperAdapter", _FakeWhisper)
    runner.config = dataclasses.replace(runner.config, stt_provider="faster-whisper", voice_layer="typed")
    (repo.root / "utt.wav").write_bytes(b"RIFF-fake")

    status, body = _call(
        bridge, "POST", "/v1/submit/spoken", token=bridge.token,
        body={
            "workspace": str(repo.root),
            "wav_path": "utt.wav",
            "client_request_id": "spk-snap-1",
            "editor_snapshot": {
                "file": "src/app.py",
                "document_version": 4,
                "dirty": False,
                "selection": {"text": "add"},
            },
        },
    )
    assert status == 200, body
    task = runner.state.coding_tasks[body["task_id"]]
    snap = runner.state.context_snapshots[task.context_snapshot_id]
    assert task.file_path == "src/app.py"
    assert snap.document_version == 4
    assert snap.selection_text == "add"

    # Same gate as /v1/submit: no token means no transcription and no task.
    status, _ = _call(bridge, "POST", "/v1/submit/spoken", token=None,
                      body={"workspace": str(repo.root), "wav_path": "utt.wav", "client_request_id": "spk-2"})
    assert status == 401
    assert len(runner.state.coding_tasks) == 1


def test_submission_view_reports_unknown_submissions_as_404(repo, runner, bridge):
    assert _call(bridge, "GET", "/v1/submission" + _q(repo, client_request_id="never-sent"),
                 token=bridge.token) == (404, {"error": "unknown_submission"})


# --- queued turns (R5): a turn behind an active task waits for its dispatch ------------


def test_queued_turn_through_the_bridge_waits_for_dispatch_and_completes(repo, runner, bridge):
    first = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="qt-1")
    pending = _await_approval(runner, first["task_id"])

    box: dict[str, Any] = {}

    def turn() -> None:
        box["payload"] = run_turn_via_bridge(
            repo, instruction="RUN_TESTS_PASS explain add", mode="ask", file_path="",
            client_request_id="qt-2", timeout=20,
        )

    worker = threading.Thread(target=turn, daemon=True)
    worker.start()

    def queued() -> bool:
        with runner._lock:
            return any(q.get("state") == "held" for q in runner.state.queue)

    assert wait_for(queued), "the second turn never reached the queue"
    _, view = _call(bridge, "GET", "/v1/submission" + _q(repo, client_request_id="qt-2"), token=bridge.token)
    assert view["task_id"] is None and view["state"] == "held"

    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"], task_id=first["task_id"])
    worker.join(timeout=60)
    assert not worker.is_alive(), "the turn did not return"
    payload = box["payload"]
    assert payload["state"] == "completed"
    assert payload["tests_status"] == "passed"
    assert payload["task_id"] and payload["task_id"] != first["task_id"]


def test_turn_cli_delegates_to_a_live_bridge_and_only_the_bridge_writes_state(repo, runner, bridge, monkeypatch, capsys):
    import hive_planner.voice_task as voice_task
    from hive_planner.cli import main
    from hive_planner.voice_bot import load_state

    def no_standalone_agent(*args, **kwargs):
        raise AssertionError("turn must not start its own agent while a bridge is live")

    monkeypatch.setattr(voice_task, "open_agent_acp", no_standalone_agent)
    code = main([
        "--root", str(repo.root), "voice-bot", "turn", "RUN_TESTS_PASS explain add",
        "--feature", "Voice_Bot", "--client-request-id", "dl-1", "--timeout", "20",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out.split("\n", 1)[1])
    assert code == 0 and payload["state"] == "completed"
    assert payload["tests_status"] == "passed"
    assert payload["task_id"] in runner.state.coding_tasks
    assert payload["task_id"] in load_state(repo).coding_tasks  # written by the bridge's runner


def test_init_is_refused_while_a_bridge_is_live(repo, bridge, capsys):
    from hive_planner.cli import main

    code = main(["--root", str(repo.root), "voice-bot", "init", "--feature", "Voice_Bot"])
    assert code == 1
    assert "bridge is live" in capsys.readouterr().err


def test_close_removes_token_and_endpoint_and_stops_listening(repo, runner):
    bridge = VoiceBridge(runner)
    bridge.start()
    port = bridge.port
    old_token = bridge.token
    bridge.close()
    assert not bridge_token_path(repo).exists()
    assert not bridge_endpoint_path(repo).exists()
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/approval", timeout=2)

    second = VoiceBridge(runner)
    second.start()
    try:
        assert second.token != old_token  # a new token per session
        assert _call(second, "GET", "/v1/approval" + _q(repo), token=old_token)[0] == 401
    finally:
        second.close()


# --- T029: R22 live buffer installed at bridge startup -----------------------------


def test_bridge_start_installs_live_lookup_and_close_removes_it(repo, runner):
    b = VoiceBridge(runner)
    b.start()
    try:
        assert runner.live_buffer_lookup() == b.live_buffer_for
    finally:
        b.close()
    assert runner.live_buffer_lookup() is None


def test_reply_without_snapshot_is_blocked_by_a_stale_live_buffer(repo, runner, bridge):
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py", client_request_id="lb-1",
        file_path="src/app.py", document_version=1, dirty=False,
    )
    pending = _await_approval(runner, out["task_id"])
    bridge.record_live_buffer("src/app.py", 8, True)  # the editor moved on since the snapshot
    status, reply = _call(bridge, "POST", "/v1/reply", token=bridge.token,
                          body=_reply_body(repo, out["task_id"], pending, "approve edit src/app.py"))
    assert status == 200 and reply["status"] == "stale"
    wait_task_terminal(runner, out["task_id"])
    assert '"outcome": "selected"' not in runner.state.coding_tasks[out["task_id"]].evidence.written_result


def test_reply_stale_check_matches_a_backslash_bound_path_to_the_live_buffer(repo, runner, bridge):
    # The live feed keys buffers by forward-slash path. A task bound with a backslash path must
    # still find its buffer, or the R22 stale check is silently skipped.
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py", client_request_id="lb-bs-1",
        file_path="src\\app.py", document_version=1, dirty=False,
    )
    pending = _await_approval(runner, out["task_id"])
    bridge.record_live_buffer("src/app.py", 8, True)  # the editor moved on since the snapshot
    status, reply = _call(bridge, "POST", "/v1/reply", token=bridge.token,
                          body=_reply_body(repo, out["task_id"], pending, "approve edit src/app.py"))
    assert status == 200 and reply["status"] == "stale"
    wait_task_terminal(runner, out["task_id"])
    assert '"outcome": "selected"' not in runner.state.coding_tasks[out["task_id"]].evidence.written_result


def test_reply_without_snapshot_passes_when_the_live_buffer_matches(repo, runner, bridge):
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py", client_request_id="lb-2",
        file_path="src/app.py", document_version=1, dirty=False,
    )
    pending = _await_approval(runner, out["task_id"])
    bridge.record_live_buffer("src/app.py", 1, False)  # control: same version, clean
    status, reply = _call(bridge, "POST", "/v1/reply", token=bridge.token,
                          body=_reply_body(repo, out["task_id"], pending, "approve edit src/app.py"))
    assert status == 200 and reply["status"] == "approved"
    assert wait_task_terminal(runner, out["task_id"]) == "completed"


def test_submit_with_stale_version_is_blocked_by_the_live_buffer(repo, runner, bridge):
    bridge.record_live_buffer("src/app.py", 42, True)
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": str(repo.root), "instruction": "explain add",
                               "client_request_id": "lb-3", "file_path": "src/app.py",
                               "editor_snapshot": {"file": "src/app.py", "document_version": 1, "dirty": False}})
    assert status == 400 and body["error"] == "stale"
    assert runner.state.coding_tasks == {}


def test_submit_without_a_version_is_not_compared_to_the_live_buffer(repo, runner, bridge):
    # Over HTTP a submit carries no version unless the body has an editor_snapshot. With nothing to
    # compare, the live buffer is not consulted; this is the documented limit until the R33 latch opens.
    bridge.record_live_buffer("src/app.py", 42, True)
    status, body = _call(bridge, "POST", "/v1/submit", token=bridge.token,
                         body={"workspace": str(repo.root), "instruction": "explain add",
                               "client_request_id": "lb-4", "file_path": "src/app.py"})
    assert status == 200, body
    wait_task_terminal(runner, body["task_id"])


def test_http_live_feed_then_reply_without_snapshot_is_blocked_as_stale(repo, runner, bridge):
    # T029 producer path: the extension posts the editor version over HTTP, then a reply with no
    # editor_snapshot in the body is checked against that live reading (R22).
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py", client_request_id="lf-1",
        file_path="src/app.py", document_version=1, dirty=False,
    )
    pending = _await_approval(runner, out["task_id"])
    status, fed = _call(bridge, "POST", "/v1/live", token=bridge.token,
                        body={"workspace": str(repo.root), "file_path": "src/app.py",
                              "document_version": 8, "dirty": True})
    assert status == 200 and fed == {"status": "recorded"}
    assert bridge.live_buffer_for("src/app.py") == (8, True)
    status, reply = _call(bridge, "POST", "/v1/reply", token=bridge.token,
                          body=_reply_body(repo, out["task_id"], pending, "approve edit src/app.py"))
    assert status == 200 and reply["status"] == "stale"
    wait_task_terminal(runner, out["task_id"])
    assert '"outcome": "selected"' not in runner.state.coding_tasks[out["task_id"]].evidence.written_result


def test_oversize_post_body_is_refused_without_resetting_the_socket(repo, runner, bridge):
    """Reject a too-large Content-Length after draining it, so the next request still works."""
    limit = max_submit_body_bytes(runner.config.instruction_max_chars, runner.config.snapshot_max_bytes)
    status, body = _call(
        bridge, "POST", "/v1/submit", token=bridge.token, raw=b"x" * (limit + 1),
    )
    assert status == 400 and body == {"error": "bad_length"}
    assert runner.state.coding_tasks == {}
    status, approval = _call(bridge, "GET", "/v1/approval" + _q(repo), token=bridge.token)
    assert status == 200 and approval["pending"] is False


def test_live_feed_without_token_records_nothing(repo, runner, bridge):
    status, _ = _call(bridge, "POST", "/v1/live", token=None,
                      body={"workspace": str(repo.root), "file_path": "src/app.py",
                            "document_version": 8, "dirty": True})
    assert status == 401
    assert bridge.live_buffer_for("src/app.py") is None


@pytest.mark.parametrize("bad", [
    {"file_path": "/etc/passwd"},
    {"file_path": "..\\outside.py"},
    {"file_path": "C:/secret.py"},
    {"document_version": True},
    {"document_version": -1},
    {"document_version": "8"},
    {"dirty": "yes"},
])
def test_live_feed_refuses_bad_fields_before_recording(repo, runner, bridge, bad):
    body = {"workspace": str(repo.root), "file_path": "src/app.py", "document_version": 8, "dirty": True}
    body.update(bad)
    status, out = _call(bridge, "POST", "/v1/live", token=bridge.token, body=body)
    assert status == 400 and out["error"].startswith("bad_")
    assert bridge.live_buffer_for("src/app.py") is None
    assert bridge.live_buffer_for(body["file_path"]) is None


# --- T031: playback interrupt and call end over HTTP (R1, R5, R7, R25) -------------------


def test_playback_interrupt_and_call_end_require_the_token_and_change_nothing(repo, runner, bridge):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="t31-tk")
    wait_task_state(runner, blocker["task_id"], "running")
    ws = str(repo.root)
    assert _call(bridge, "POST", "/v1/playback/interrupt", token=None, body={"workspace": ws}) == (
        401, {"error": "unauthorized"})
    assert _call(bridge, "POST", "/v1/call/end", token="wrong", body={"workspace": ws}) == (
        401, {"error": "unauthorized"})
    assert runner.session.state == "active"
    assert runner.state.coding_tasks[blocker["task_id"]].state == "running"
    runner.cancel(blocker["task_id"])
    wait_task_terminal(runner, blocker["task_id"])


def test_playback_interrupt_over_http_keeps_task_state_and_sets_session_interrupted(repo, runner, bridge):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="t31-int")
    wait_task_state(runner, blocker["task_id"], "running")
    status, body = _call(bridge, "POST", "/v1/playback/interrupt", token=bridge.token,
                         body={"workspace": str(repo.root)})
    assert status == 200
    assert body["event"] == "speech.interrupted"
    assert body["state_changed"] is False
    assert body["session_state"] == "interrupted"
    assert runner.session.state == "interrupted"
    assert runner.state.coding_tasks[blocker["task_id"]].state == "running"
    runner.cancel(blocker["task_id"])
    wait_task_terminal(runner, blocker["task_id"])


def test_call_end_over_http_keeps_active_task_running_and_discards_queued(repo, runner, bridge):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="t31-end")
    wait_task_state(runner, blocker["task_id"], "running")
    runner.queue_follow_up("never runs", task_id=blocker["task_id"])
    status, body = _call(bridge, "POST", "/v1/call/end", token=bridge.token,
                         body={"workspace": str(repo.root)})
    assert status == 200
    assert body["session_ended"] is True
    assert body["discarded"] == 1
    assert body["active_task_state"] == "running"
    assert body["rollback"] == "not_performed"
    assert runner.session.state == "ended"
    assert runner.state.queue[0]["state"] == "discarded"
    assert runner.state.coding_tasks[blocker["task_id"]].state == "running"
    runner.cancel(blocker["task_id"])
    wait_task_terminal(runner, blocker["task_id"])


@pytest.mark.parametrize("route", ["/v1/playback/interrupt", "/v1/call/end"])
def test_new_control_routes_refuse_unknown_keys_and_missing_workspace(repo, runner, bridge, route):
    status, body = _call(bridge, "POST", route, token=bridge.token,
                         body={"workspace": str(repo.root), "shell": "rm -rf"})
    assert status == 400 and body["error"] == "unknown_argument"
    status, body = _call(bridge, "POST", route, token=bridge.token, body={})
    assert status == 400 and body["error"] == "missing_workspace"
    assert runner.session.state == "active"


# --- T036: Patch B routes (cancel, queue, diff, reconnect) over HTTP -----------------------


@pytest.mark.parametrize("method,route", [
    ("POST", "/v1/cancel"), ("POST", "/v1/queue"), ("POST", "/v1/reconnect"), ("GET", "/v1/diff"),
])
def test_patch_b_routes_require_the_token(repo, runner, bridge, method, route):
    ws = str(repo.root)
    if method == "GET":
        status, body = _call(bridge, "GET", route + _q(repo, task_id="t36-none"), token=None)
    else:
        status, body = _call(bridge, method, route, token=None,
                             body={"workspace": ws, "task_id": "t36-none", "text": "x"})
    assert (status, body) == (401, {"error": "unauthorized"})
    assert runner.state.coding_tasks == {}


@pytest.mark.parametrize("route,fields", [
    ("/v1/cancel", {"task_id": "t36-x"}),
    ("/v1/queue", {"task_id": "t36-x", "text": "x"}),
    ("/v1/reconnect", {"task_id": "t36-x"}),
])
def test_patch_b_post_routes_refuse_unknown_keys_and_missing_workspace(repo, runner, bridge, route, fields):
    status, body = _call(bridge, "POST", route, token=bridge.token,
                         body={"workspace": str(repo.root), **fields, "shell": "rm"})
    assert status == 400 and body["error"] == "unknown_argument"
    status, body = _call(bridge, "POST", route, token=bridge.token, body=dict(fields))
    assert status == 400 and body["error"] == "missing_workspace"
    assert runner.state.coding_tasks == {}


def test_diff_route_refuses_missing_task_id_and_reports_unknown_task_404(repo, runner, bridge):
    status, body = _call(bridge, "GET", "/v1/diff" + _q(repo), token=bridge.token)
    assert status == 400 and body["error"] == "missing_task_id"
    status, body = _call(bridge, "GET", "/v1/diff" + _q(repo, task_id="t36-none"), token=bridge.token)
    assert status == 404 and body["error"] == "unknown_task"


def test_cancel_over_http_records_the_request_and_unknown_task_is_404(repo, runner, bridge):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="t36-cancel")
    wait_task_state(runner, blocker["task_id"], "running")
    status, body = _call(bridge, "POST", "/v1/cancel", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": blocker["task_id"]})
    assert status == 200
    assert body["task_id"] == blocker["task_id"]
    assert body["state"] in ("cancel_requested", "cancelled", "failed")
    wait_task_terminal(runner, blocker["task_id"])
    status, body = _call(bridge, "POST", "/v1/cancel", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": blocker["task_id"]})
    assert status == 409 and body["error"] == "task_already_terminal"
    status, body = _call(bridge, "POST", "/v1/cancel", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": "t36-none"})
    assert status == 404 and body["error"] == "unknown_task"


def test_queue_over_http_queues_behind_the_active_task_and_wrong_task_is_409(repo, runner, bridge):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="t36-queue")
    wait_task_state(runner, blocker["task_id"], "running")
    status, body = _call(bridge, "POST", "/v1/queue", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": blocker["task_id"], "text": "later"})
    assert status == 200
    assert body["status"] == "queued" and body["task_id"] is None
    assert runner.state.queue[-1]["state"] != "discarded"
    status, body = _call(bridge, "POST", "/v1/queue", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": "t36-other", "text": "nope"})
    assert status == 409 and body["error"] == "task_mismatch"
    # Clean up: call end discards the queued follow-up (R25), then the blocker is cancelled.
    _call(bridge, "POST", "/v1/call/end", token=bridge.token, body={"workspace": str(repo.root)})
    runner.cancel(blocker["task_id"])
    wait_task_terminal(runner, blocker["task_id"])


def test_diff_over_http_reports_no_evidence_for_a_task_without_writes(repo, runner, bridge):
    done = runner.submit("say hello", client_request_id="t36-diff")
    wait_task_terminal(runner, done["task_id"])
    status, body = _call(bridge, "GET", "/v1/diff" + _q(repo, task_id=done["task_id"]), token=bridge.token)
    assert status == 200
    assert body["task_id"] == done["task_id"]
    assert body["source"] == "no_diff_evidence"
    assert body["diff"] == ""


def test_show_diff_over_http_queues_the_editor_action_for_a_completed_task(repo, runner, bridge):
    # T043: the EDH host reaches show_diff only through the bridge, so the route must queue it
    # for GET /v1/editor and refuse unknown tasks and missing tokens without queuing anything.
    done = runner.submit("say hello", client_request_id="t43-show-diff")
    wait_task_terminal(runner, done["task_id"])
    status, body = _call(bridge, "POST", "/v1/editor/show_diff", token=None,
                         body={"workspace": str(repo.root), "task_id": done["task_id"]})
    assert status == 401 and body["error"] == "unauthorized"
    assert not any(row.get("kind") == "show_diff" for row in runner.state.editor_actions)
    status, body = _call(bridge, "POST", "/v1/editor/show_diff", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": done["task_id"]})
    assert status == 200 and body["queued"] is True and body["task_id"] == done["task_id"]
    status, pending = _call(bridge, "GET", "/v1/editor" + _q(repo), token=bridge.token)
    assert status == 200 and pending["pending"] is True
    assert pending["kind"] == "show_diff" and pending["action_id"] == body["action_id"]
    assert pending["task_id"] == done["task_id"]
    status, body = _call(bridge, "POST", "/v1/editor/show_diff", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": "t43-none"})
    assert status == 404 and body["error"] == "unknown_task"
    status, body = _call(bridge, "POST", "/v1/editor/show_diff", token=bridge.token,
                         body={"task_id": done["task_id"]})
    assert status == 400 and body["error"] == "missing_workspace"


def test_navigate_over_http_queues_the_editor_action_and_refuses_bad_paths(repo, runner, bridge):
    # Gap fix: navigate_to had no HTTP route, so the extension could never receive a navigate.
    done = runner.submit("say hello", client_request_id="nav-http-1", file_path="src/app.py")
    wait_task_terminal(runner, done["task_id"])
    snap_id = runner.state.coding_tasks[done["task_id"]].context_snapshot_id
    ws = str(repo.root)

    assert _call(bridge, "POST", "/v1/editor/navigate", token=None,
                 body={"workspace": ws, "file_path": "src/app.py", "context_snapshot_id": snap_id}) == (
        401, {"error": "unauthorized"})
    assert not any(row.get("kind") == "navigate" for row in runner.state.editor_actions)

    status, body = _call(bridge, "POST", "/v1/editor/navigate", token=bridge.token,
                         body={"workspace": ws, "file_path": "src/app.py", "context_snapshot_id": snap_id})
    assert status == 200 and body["queued"] is True and body["file_path"] == "src/app.py"
    status, pending = _call(bridge, "GET", "/v1/editor" + _q(repo), token=bridge.token)
    assert pending["pending"] is True and pending["kind"] == "navigate"
    assert pending["action_id"] == body["action_id"]

    status, body = _call(bridge, "POST", "/v1/editor/navigate", token=bridge.token,
                         body={"workspace": ws, "file_path": "../secret.txt", "context_snapshot_id": snap_id})
    assert status == 400 and body["error"] == "path_outside_workspace"
    status, body = _call(bridge, "POST", "/v1/editor/navigate", token=bridge.token,
                         body={"workspace": ws, "file_path": "src/app.py"})
    assert status == 400 and body["error"] == "missing_context_snapshot_id"
    status, body = _call(bridge, "POST", "/v1/editor/navigate", token=bridge.token,
                         body={"workspace": ws, "file_path": "src/app.py", "context_snapshot_id": snap_id,
                               "shell": "rm"})
    assert status == 400 and body["error"] == "unknown_argument"


def test_diff_over_http_returns_write_evidence_when_latch_is_on(repo, runner, bridge):
    from hive_planner.config import RepoPaths
    from hive_planner.voice_bot import voice_bot_config_path

    spec = repo.root / "docs" / "specs" / "Voice_Bot"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "evidence-register.md").write_text(
        "| Claim ID | Component | Pinned | Test | Result | Date | Notes |\n"
        "|---|---|---|---|---|---|---|\n"
        "| G6 | permissions | x | t | **pass** | 2026-11-11 | fixture |\n",
        encoding="utf-8",
    )
    cfg = voice_bot_config_path(RepoPaths(root=repo.root))
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"edits_enabled": True}), encoding="utf-8")

    out = runner.submit("CANCEL_ME hold", client_request_id="t36-wdiff")
    wait_task_state(runner, out["task_id"], "running")
    runner._on_update({
        "sessionId": runner._acp_session_id,
        "update": {
            "sessionUpdate": "tool_call_update",
            "toolCallId": "call-http-w1",
            "status": "completed",
            "content": [{"type": "diff", "path": "src/app.py",
                         "oldText": "x = 1\n", "newText": "x = 2\n"}],
        },
    })
    try:
        status, body = _call(bridge, "GET", "/v1/diff" + _q(repo, task_id=out["task_id"]), token=bridge.token)
        assert status == 200
        assert body["source"] == "write_evidence"
        assert "-x = 1\n" in body["diff"] and "+x = 2\n" in body["diff"]
    finally:
        runner.cancel(out["task_id"])
        wait_task_terminal(runner, out["task_id"])


def test_reconnect_over_http_refuses_a_task_that_is_not_unknown(repo, runner, bridge):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="t36-rec")
    wait_task_state(runner, blocker["task_id"], "running")
    status, body = _call(bridge, "POST", "/v1/reconnect", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": blocker["task_id"]})
    assert status == 409 and body["error"] == "not_unknown"
    assert runner.state.coding_tasks[blocker["task_id"]].state == "running"
    status, body = _call(bridge, "POST", "/v1/reconnect", token=bridge.token,
                         body={"workspace": str(repo.root), "task_id": "t36-none"})
    assert status == 404 and body["error"] == "unknown_task"
    runner.cancel(blocker["task_id"])
    wait_task_terminal(runner, blocker["task_id"])
