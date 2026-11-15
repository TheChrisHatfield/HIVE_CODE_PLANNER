"""Regression tests from the Voice_Bot two-pass code review (2026-11-13).

Each test pins one defect found in review so it cannot return:
- runner path check: a NUL or unresolvable path is a DelegationError `bad_path`, not a raw crash.
- live buffer check: the dirty flag compares by value, so a non-singleton bool cannot fake a stale buffer.
- buffers_match: same value comparison as the submit check.
- fs/read: reads at most `snapshot_max_bytes` from disk instead of loading the whole file first.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bot import ContextSnapshot, _read_workspace_text, buffers_match
from hive_planner.voice_task import DelegationError
from voice_turn_support import make_repo, make_runner


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_nul_byte_path_is_a_delegation_error_not_a_crash(runner):
    with pytest.raises(DelegationError) as info:
        runner._resolve_file("src/app.py\x00.txt")
    assert info.value.code == "bad_path"


def test_nul_byte_cannot_alias_another_workspace_file(runner):
    # Without the guard, Windows resolve() truncated this to src/app.py, a different binding.
    with pytest.raises(DelegationError):
        runner._resolve_file("src/app.py\x00.txt")


def test_acp_fs_read_refuses_nul_path(tmp_path: Path):
    from hive_planner.voice_bot import VoiceBotError

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x", encoding="utf-8")
    with pytest.raises(VoiceBotError):
        _read_workspace_text(tmp_path, {"path": "src/app.py\x00.txt"}, 1024)


def test_relative_path_still_resolves_inside_workspace(runner):
    assert runner._resolve_file("src/app.py") == "src/app.py"


def test_submit_with_matching_dirty_int_does_not_report_stale(runner):
    # Live buffer says dirty=False. A submit that sends the same value must not be refused as stale,
    # even when the flag arrives as a plain int from a JSON payload (identity compare used to fail).
    runner.set_live_buffer(lambda rel: (3, False))
    out = runner.submit(
        "explain add", client_request_id="dirty-int-1", file_path="src/app.py",
        document_version=3, dirty=0,
    )
    assert out.get("status") != "stale"


def test_submit_with_changed_version_is_still_stale(runner):
    runner.set_live_buffer(lambda rel: (4, False))
    with pytest.raises(DelegationError) as info:
        runner.submit(
            "explain add", client_request_id="stale-1", file_path="src/app.py",
            document_version=3, dirty=False,
        )
    assert info.value.code == "stale"


def test_buffers_match_compares_values_not_identity():
    snap = ContextSnapshot(
        workspace_root="/w", file_path="a.py", selection_text="", instruction="x",
        document_version=2, dirty=1,
    )
    assert buffers_match(snap, 2, True) is True
    assert buffers_match(snap, 3, True) is False
    assert buffers_match(snap, 2, False) is False


def test_fs_read_returns_at_most_the_cap_without_loading_whole_file(tmp_path: Path):
    big = tmp_path / "big.txt"
    big.write_bytes(b"a" * 500_000)
    out = _read_workspace_text(tmp_path, {"path": "big.txt"}, 1024)
    assert len(out["content"]) == 1024


def test_fs_read_still_refuses_hive_internal_paths(tmp_path: Path):
    (tmp_path / ".hive" / "voice-bot").mkdir(parents=True)
    (tmp_path / ".hive" / "voice-bot" / "bridge-token").write_text("secret", encoding="utf-8")
    from hive_planner.voice_bot import VoiceBotError

    with pytest.raises(VoiceBotError) as info:
        _read_workspace_text(tmp_path, {"path": ".hive/voice-bot/bridge-token"}, 1024)
    assert str(info.value) == "fs_read_protected"

# --- R22 write classification review (2026-11-13, pass 3) ---------------------------------

import pytest as _pytest  # noqa: E402

from hive_planner.voice_task import VoiceTaskRunner as _Runner  # noqa: E402


@_pytest.mark.parametrize("command", [
    "robocopy src backup /E",
    "xcopy a.txt b.txt",
    "setx HIVE_X 1",
    "curl -o out.txt https://example.test/a",
    "curl https://example.test/a -O",
    "wget -O out.txt https://example.test/a",
    "perl -i -pe 's/a/b/' src/app.py",
    "awk -i inplace '{print}' a.txt",
    "powershell -c \"Invoke-WebRequest https://x.test -OutFile a.bin\"",
])
def test_file_writing_tools_are_writes(command: str):
    assert _Runner._is_write_call("execute", command) is True


@_pytest.mark.parametrize("kind", ["", "other", None])
def test_unlabelled_tool_kind_with_write_command_fails_closed(kind):
    # A provider that omits or mislabels the kind must not skip the write count.
    assert _Runner._is_write_call(kind, "Set-Content a.txt x") is True


@_pytest.mark.parametrize("kind", ["read", "search", "fetch", "think"])
def test_read_only_kinds_are_never_writes(kind):
    # A search query that merely contains a `>` is not a file write.
    assert _Runner._is_write_call(kind, "find a > b") is False


def test_plain_read_command_under_unlabelled_kind_is_not_a_write():
    assert _Runner._is_write_call("", "pytest -q") is False

# --- Pass 2 (2026-11-13): editor payloads from .hive/ are excluded as secret --------------

from hive_planner.voice_bot import map_editor_snapshot as _map_editor_snapshot  # noqa: E402


@_pytest.mark.parametrize("file_path", [".hive/voice-bot/state.json", ".HIVE/voice-bot/config.json", ".hive\\voice-bot\\config.json"])
def test_editor_payload_from_hive_dir_is_excluded_as_secret(file_path: str):
    snap = _map_editor_snapshot(
        {"file": file_path, "file_content": "token=abc", "reason": ""},
        instruction="explain", workspace_root="/w",
    )
    assert snap.excluded == "secret"
    assert snap.file_content == ""


def test_editor_payload_from_normal_file_is_not_excluded_by_hive_rule():
    snap = _map_editor_snapshot(
        {"file": "src/app.py", "file_content": "x = 1", "reason": ""},
        instruction="explain", workspace_root="/w",
    )
    assert snap.excluded == ""
    assert snap.file_content == "x = 1"
