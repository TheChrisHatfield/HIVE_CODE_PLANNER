"""T021 / R30 — Voice_Bot deploy ships Moshi and Pipecat in the Hive `voice` extra."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    VOICE_DEPLOY_PACK_SCHEMA,
    VOICE_EXTRA_NAME,
    VOICE_STACK_PYPI,
    build_voice_deploy_pack,
    ensure_voice_runtime,
    hybrid_speech_path,
    init_voice_session,
    probe_optional_voice_providers,
    status_summary,
    voice_runtime_plan,
)

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_voice_extra_declares_moshi_and_pipecat():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]
    voice = extras[VOICE_EXTRA_NAME]
    for name in VOICE_STACK_PYPI:
        assert name in voice
    assert data["project"]["dependencies"] == []


def test_runtime_plan_lists_the_voice_pack_without_pip_installing():
    plan = voice_runtime_plan()
    assert plan["extra"] == "voice"
    names = [row["package"] for row in plan["packages"]]
    assert names == list(VOICE_STACK_PYPI)
    assert "pip install" in plan["pip_install"]
    assert ".[voice]" in plan["pip_install"]
    dry = ensure_voice_runtime(install=False)
    assert dry["installed"] is False
    assert dry["steps"] == []
    assert dry["plan"]["speech_path"] == hybrid_speech_path() == "typed_instruction"


def test_ensure_runtime_install_calls_pip_for_missing_packages(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("hive_planner.voice_bot.subprocess.run", fake_run)
    monkeypatch.setattr("hive_planner.voice_bot._module_installed", lambda _name: False)
    monkeypatch.setattr(
        "hive_planner.voice_bot.resolve_cursor_agent_cli",
        lambda: {"available": True, "path": "agent", "version": "test", "acp_subcommand": True},
    )
    out = ensure_voice_runtime(install=True)
    assert out["ok"] is True
    assert calls
    pip = calls[0]
    assert pip[:3] == [pip[0], "-m", "pip"]
    assert "install" in pip
    assert "moshi" in pip and "pipecat-ai" in pip


def test_ensure_runtime_records_pip_failure(monkeypatch):
    def fake_run(cmd, **_kwargs):
        class Result:
            returncode = 1

        return Result()

    monkeypatch.setattr("hive_planner.voice_bot.subprocess.run", fake_run)
    monkeypatch.setattr("hive_planner.voice_bot._module_installed", lambda _name: False)
    out = ensure_voice_runtime(install=True)
    assert out["ok"] is False
    assert out["steps"][0]["ok"] is False


def test_deploy_pack_writes_manifest_and_install_doc(tmp_path: Path):
    out = tmp_path / "voice-pack"
    result = build_voice_deploy_pack(tmp_path, out, download_wheels=False)
    assert result["ok"] is True
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == VOICE_DEPLOY_PACK_SCHEMA
    assert manifest["packages"] == list(VOICE_STACK_PYPI)
    assert manifest["target_install"]["online_pip"] == voice_runtime_plan()["pip_install"]
    assert (out / "INSTALL.md").read_text(encoding="utf-8").startswith("# Voice_Bot deploy pack")
    assert (out / "requirements-voice.txt").read_text(encoding="utf-8").strip().splitlines() == list(
        VOICE_STACK_PYPI
    )


def test_deploy_pack_download_wheels_invokes_pip(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        if "download" in cmd:
            wheels = Path(cmd[cmd.index("-d") + 1])
            wheels.mkdir(parents=True, exist_ok=True)
            (wheels / "moshi-placeholder.whl").write_text("", encoding="utf-8")

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("hive_planner.voice_bot.subprocess.run", fake_run)
    monkeypatch.setattr(
        "hive_planner.voice_bot.resolve_cursor_agent_cli",
        lambda: {"available": True, "path": "agent", "version": "test", "acp_subcommand": True},
    )
    out = tmp_path / "pack"
    result = build_voice_deploy_pack(tmp_path, out, download_wheels=True)
    assert result["ok"] is True
    assert result["wheel_count"] == 1
    assert "moshi" in calls[0] and "pipecat-ai" in calls[0]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["target_install"]["offline_pip"]


def test_status_reports_declared_voice_stack(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n", encoding="utf-8"
    )
    paths = RepoPaths(root=tmp_path)
    init_voice_session(paths, "Voice_Bot")
    providers = status_summary(paths, "Voice_Bot")["optional_providers"]
    assert providers["hive_ships_these"] is True
    assert providers["extra"] == "voice"
    assert providers["moshi"]["declared"] is True
    assert providers["pipecat"]["declared"] is True
    assert providers["speech_path"] == "typed_instruction"
    probe = probe_optional_voice_providers()
    assert probe["cursor_agent_cli"]["command"]
