"""AC20 / R24 — resource-use check is driven by the voice_bot config object."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    VoiceBotConfig,
    VoiceBotError,
    load_voice_bot_config,
    rss_meets_target,
    voice_bot_config_path,
)

# Peak RSS (MB) from the 2026-11-11 R24 live probe, evidence-register.md §T018.
MEASURED_AGENT_CHILDREN_MB = (607.8, 616.3, 630.2)
MEASURED_VOICE_SERVICE_MB = (20.8, 21.0, 21.1)


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    return RepoPaths(root=tmp_path)


def test_resource_defaults_are_set_and_cover_measured_peaks() -> None:
    cfg = VoiceBotConfig()
    assert cfg.agent_children_rss_target_mb == 650
    assert cfg.voice_service_rss_target_mb == 100
    assert all(rss_meets_target(mb, cfg.agent_children_rss_target_mb) for mb in MEASURED_AGENT_CHILDREN_MB)
    assert all(rss_meets_target(mb, cfg.voice_service_rss_target_mb) for mb in MEASURED_VOICE_SERVICE_MB)


def test_missing_resource_target_is_not_a_claim() -> None:
    assert rss_meets_target(10_000.0, None) is True


def test_rss_check_boundary_is_inclusive() -> None:
    assert rss_meets_target(650.0, 650) is True
    assert rss_meets_target(650.1, 650) is False


def test_resource_targets_can_be_unset_explicitly() -> None:
    cfg = VoiceBotConfig.from_dict({"voice_service_rss_target_mb": None, "agent_children_rss_target_mb": None})
    assert cfg.voice_service_rss_target_mb is None
    assert cfg.agent_children_rss_target_mb is None


@pytest.mark.parametrize("key", ["voice_service_rss_target_mb", "agent_children_rss_target_mb"])
def test_resource_target_must_be_positive_int(repo: RepoPaths, key: str) -> None:
    path = voice_bot_config_path(repo)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({key: 0}), encoding="utf-8")
    with pytest.raises(VoiceBotError):
        load_voice_bot_config(repo)


def test_config_file_changes_the_checked_result(repo: RepoPaths) -> None:
    """Integrated path: the file on disk, loaded the way the probe loads it, decides the verdict."""
    path = voice_bot_config_path(repo)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"agent_children_rss_target_mb": 600}), encoding="utf-8")
    tight = load_voice_bot_config(repo)
    path.write_text(json.dumps({"agent_children_rss_target_mb": 650}), encoding="utf-8")
    loose = load_voice_bot_config(repo)

    peak = MEASURED_AGENT_CHILDREN_MB[-1]  # 630.2 MB, worst measured run
    assert rss_meets_target(peak, tight.agent_children_rss_target_mb) is False
    assert rss_meets_target(peak, loose.agent_children_rss_target_mb) is True


# ---- T044 / gap C: runtime RSS check in VoiceTaskRunner (R24, AC20) ----

from hive_planner.voice_bot import voice_bot_config_path  # noqa: E402
from voice_turn_support import make_repo, make_runner, wait_task_terminal  # noqa: E402


def _rss_run(tmp_path: Path, config: dict, reader) -> list[dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo = make_repo(tmp_path)
    path = voice_bot_config_path(repo)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config), encoding="utf-8")
    r = make_runner(repo, rss_reader=reader)
    try:
        result = r.submit("hello", client_request_id="t044-1")
        wait_task_terminal(r, result["task_id"])
        return list(r.state.coding_tasks[result["task_id"]].events)
    finally:
        r.close()


def _rss_rows(events: list[dict]) -> list[dict]:
    return [e["payload"] for e in events if e.get("name") == "r24.over_budget" and e["payload"].get("kind") == "rss"]


def test_rss_over_agent_children_target_is_logged_at_runtime(tmp_path: Path) -> None:
    events = _rss_run(
        tmp_path,
        {"agent_children_rss_target_mb": 650, "voice_service_rss_target_mb": 100},
        lambda: {"voice_service": 21.0, "agent_children": 770.2},
    )
    rows = _rss_rows(events)
    assert [(p["scope"], p["target_mb"], p["measured_mb"]) for p in rows] == [("agent_children", 650, 770.2)]


def test_rss_within_targets_is_not_logged(tmp_path: Path) -> None:
    events = _rss_run(
        tmp_path,
        {"agent_children_rss_target_mb": 650, "voice_service_rss_target_mb": 100},
        lambda: {"voice_service": 21.0, "agent_children": 630.2},
    )
    assert _rss_rows(events) == []


def test_rss_voice_service_over_target_is_logged(tmp_path: Path) -> None:
    events = _rss_run(
        tmp_path,
        {"agent_children_rss_target_mb": 650, "voice_service_rss_target_mb": 10},
        lambda: {"voice_service": 21.0, "agent_children": 630.2},
    )
    assert [p["scope"] for p in _rss_rows(events)] == ["voice_service"]


def test_config_target_changes_the_runtime_result(tmp_path: Path) -> None:
    """Integrated path: the same measured RSS passes at 650 MB and fails at 600 MB."""
    reader = lambda: {"voice_service": 21.0, "agent_children": 630.2}  # noqa: E731
    loose = _rss_run(tmp_path / "loose", {"agent_children_rss_target_mb": 650}, reader)
    tight = _rss_run(tmp_path / "tight", {"agent_children_rss_target_mb": 600}, reader)
    assert _rss_rows(loose) == []
    assert [p["target_mb"] for p in _rss_rows(tight)] == [600]


def test_unmeasured_rss_is_not_checked(tmp_path: Path) -> None:
    events = _rss_run(
        tmp_path,
        {"agent_children_rss_target_mb": 1, "voice_service_rss_target_mb": 1},
        lambda: {"voice_service": None, "agent_children": None},
    )
    assert _rss_rows(events) == []


def test_missing_rss_targets_skip_the_reader(tmp_path: Path) -> None:
    calls: list[int] = []

    def reader():
        calls.append(1)
        return {"voice_service": 999.0, "agent_children": 999.0}

    events = _rss_run(
        tmp_path,
        {"agent_children_rss_target_mb": None, "voice_service_rss_target_mb": None},
        reader,
    )
    assert calls == []
    assert _rss_rows(events) == []


def test_each_rss_scope_is_logged_once_per_task(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    voice_bot_config_path(repo).parent.mkdir(parents=True)
    voice_bot_config_path(repo).write_text(json.dumps({"agent_children_rss_target_mb": 10}), encoding="utf-8")
    r = make_runner(repo, rss_reader=lambda: {"voice_service": None, "agent_children": 500.0})
    try:
        result = r.submit("hello", client_request_id="t044-2")
        wait_task_terminal(r, result["task_id"])
        task = r.state.coding_tasks[result["task_id"]]
        r._check_r24_rss(task)
        r._check_r24_rss(task)
        assert len(_rss_rows(list(task.events))) == 1
    finally:
        r.close()
