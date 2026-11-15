"""Spoken input paths (mic route): only the launcher's recordings folder inside `.hive/` is readable.

Regression for the 2026-11-14 live run: the mic writes WAVs under `.hive/voice-bot/recordings/`, and the
generic `.hive` fence refused every one with `path_protected`, so no spoken instruction ever reached STT.
The fence itself stays: the bridge token lives in `.hive/`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_task import DelegationError
from voice_turn_support import make_repo, make_runner


@pytest.fixture
def runner(tmp_path: Path):
    r = make_runner(make_repo(tmp_path))
    yield r
    r.close()


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF-fake")


def test_recording_inside_recordings_folder_is_accepted(runner) -> None:
    root = runner.paths.root
    _touch(root / ".hive" / "voice-bot" / "recordings" / "utt-1.wav")
    assert runner._resolve_wav_input(".hive/voice-bot/recordings/utt-1.wav") == ".hive/voice-bot/recordings/utt-1.wav"


def test_recording_path_with_backslashes_is_accepted(runner) -> None:
    root = runner.paths.root
    _touch(root / ".hive" / "voice-bot" / "recordings" / "utt-2.wav")
    assert runner._resolve_wav_input(".hive\\voice-bot\\recordings\\utt-2.wav") == ".hive/voice-bot/recordings/utt-2.wav"


def test_other_hive_files_stay_protected(runner) -> None:
    root = runner.paths.root
    _touch(root / ".hive" / "voice-bot" / "bridge-token")
    with pytest.raises(DelegationError) as excinfo:
        runner._resolve_wav_input(".hive/voice-bot/bridge-token")
    assert excinfo.value.code == "path_protected"


def test_wav_outside_the_recordings_folder_stays_protected(runner) -> None:
    root = runner.paths.root
    _touch(root / ".hive" / "voice-bot" / "stolen.wav")
    with pytest.raises(DelegationError) as excinfo:
        runner._resolve_wav_input(".hive/voice-bot/stolen.wav")
    assert excinfo.value.code == "path_protected"


def test_traversal_out_of_recordings_is_refused(runner) -> None:
    root = runner.paths.root
    _touch(root / ".hive" / "voice-bot" / "config.wav")
    with pytest.raises(DelegationError):
        runner._resolve_wav_input(".hive/voice-bot/recordings/../config.wav")


def test_missing_recording_is_refused_not_found_in_hive(runner) -> None:
    with pytest.raises(DelegationError) as excinfo:
        runner._resolve_wav_input(".hive/voice-bot/recordings/none.wav")
    assert excinfo.value.code == "path_protected"


def test_ordinary_workspace_wav_still_uses_the_normal_rule(runner) -> None:
    root = runner.paths.root
    _touch(root / "src" / "clip.wav")
    assert runner._resolve_wav_input("src/clip.wav") == "src/clip.wav"
