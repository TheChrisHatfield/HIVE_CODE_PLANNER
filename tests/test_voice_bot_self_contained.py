"""T021 / R30 — Voice_Bot deploy ships Moshi and Pipecat in the Hive `voice` extra."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    VOICE_DEPLOY_PACK_SCHEMA,
    VOICE_EXTRA_NAME,
    VOICE_INSTALL_SCRIPT_NAME,
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
    present = {"moshi": False, "pipecat": False}

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        present["moshi"] = True
        present["pipecat"] = True

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("hive_planner.voice_bot.subprocess.run", fake_run)
    monkeypatch.setattr("hive_planner.voice_bot._module_installed", lambda name: present.get(name, False))
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
    assert out["steps"][0]["still_missing"] == []


def test_ensure_runtime_pip_zero_without_import_is_not_ok(monkeypatch):
    """Moshi can report pip exit 0 on Windows and still fail to import (R30)."""

    def fake_run(cmd, **_kwargs):
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
    assert out["ok"] is False
    step = out["steps"][0]
    assert step["ok"] is False
    assert step["returncode"] == 0
    assert "moshi" in step["still_missing"]
    assert "pipecat-ai" in step["still_missing"]


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


def _voice_status_repo(tmp_path: Path) -> RepoPaths:
    (tmp_path / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n", encoding="utf-8"
    )
    paths = RepoPaths(root=tmp_path)
    init_voice_session(paths, "Voice_Bot")
    return paths


CONFIG_EXAMPLE = Path(__file__).resolve().parents[1] / ".hive" / "voice-bot" / "config.json.example"


def test_config_example_ships_with_edits_disabled():
    data = json.loads(CONFIG_EXAMPLE.read_text(encoding="utf-8"))
    assert data["edits_enabled"] is False
    assert "bridge_token" not in json.dumps(data)


def test_install_md_documents_config_example_safe_default(tmp_path: Path):
    from hive_planner.voice_bot import _voice_pack_install_md

    text = _voice_pack_install_md(tmp_path, tmp_path / "pack", wheels=False)
    assert "config.json.example" in text
    assert "edits_enabled" in text


def test_voice_extra_declares_psutil_for_r24_rss():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert "psutil" in data["project"]["optional-dependencies"][VOICE_EXTRA_NAME]


def test_status_reports_r24_rss_unmeasurable_when_psutil_missing(tmp_path: Path, monkeypatch):
    # Setting sys.modules entry to None makes `import psutil` raise ImportError.
    monkeypatch.setitem(sys.modules, "psutil", None)
    summary = status_summary(_voice_status_repo(tmp_path), "Voice_Bot")
    assert summary["r24_rss_measurable"] is False


def test_status_reports_r24_rss_measurable_when_psutil_present(tmp_path: Path):
    pytest.importorskip("psutil")
    summary = status_summary(_voice_status_repo(tmp_path), "Voice_Bot")
    assert summary["r24_rss_measurable"] is True


def _fake_editor_extension(root: Path) -> Path:
    """A minimal editor adapter tree: manifest, src/, and a test/ folder that must not ship."""
    ext = root / "extensions" / "hive-voice-bot"
    (ext / "src").mkdir(parents=True)
    (ext / "test").mkdir(parents=True)
    (ext / "package.json").write_text(
        json.dumps(
            {
                "name": "hive-voice-bot",
                "displayName": "HIVE Voice_Bot Editor Adapter",
                "description": "test fixture",
                "version": "0.0.1",
                "publisher": "hive-planner",
                "engines": {"vscode": "^1.90.0"},
                "main": "./src/extension.js",
            }
        ),
        encoding="utf-8",
    )
    (ext / "src" / "extension.js").write_text("module.exports = {};\n", encoding="utf-8")
    (ext / "src" / "core.js").write_text("module.exports = {};\n", encoding="utf-8")
    (ext / "test" / "core.test.js").write_text("// not shipped\n", encoding="utf-8")
    return ext


def test_deploy_pack_emits_vsix_and_install_script(tmp_path: Path):
    _fake_editor_extension(tmp_path)
    out = tmp_path / "pack"
    result = build_voice_deploy_pack(tmp_path, out, download_wheels=False)
    assert result["ok"] is True
    vsix = out / "hive-voice-bot-0.0.1.vsix"
    assert result["editor_vsix"] == str(vsix)
    assert vsix.is_file()
    with zipfile.ZipFile(vsix) as zf:
        names = set(zf.namelist())
    assert {"[Content_Types].xml", "extension.vsixmanifest", "extension/package.json"} <= names
    assert "extension/src/extension.js" in names and "extension/src/core.js" in names
    assert not any("/test/" in n for n in names), "test/ must not ship in the VSIX"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["editor"] == {
        "extension_id": "hive-planner.hive-voice-bot",
        "vsix": "hive-voice-bot-0.0.1.vsix",
        "install_script": VOICE_INSTALL_SCRIPT_NAME,
    }
    assert manifest["target_install"]["editor_install"].endswith(VOICE_INSTALL_SCRIPT_NAME)


def test_deploy_pack_install_script_installs_vsix_with_code_then_cursor(tmp_path: Path):
    _fake_editor_extension(tmp_path)
    out = tmp_path / "pack"
    build_voice_deploy_pack(tmp_path, out, download_wheels=False)
    script = (out / VOICE_INSTALL_SCRIPT_NAME).read_text(encoding="utf-8")
    assert "--install-extension" in script and "--force" in script
    assert '"code", "cursor"' in script
    assert "hive-voice-bot-*.vsix" in script
    assert "hive-planner.hive-voice-bot" in script


@pytest.mark.skipif(shutil.which("powershell") is None, reason="needs Windows PowerShell to parse the script")
def test_deploy_pack_install_script_is_valid_powershell(tmp_path: Path):
    _fake_editor_extension(tmp_path)
    out = tmp_path / "pack"
    build_voice_deploy_pack(tmp_path, out, download_wheels=False)
    script = out / VOICE_INSTALL_SCRIPT_NAME
    probe = (
        "$errs = $null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{script}', [ref]$null, [ref]$errs); "
        "if ($errs) { $errs | ForEach-Object { $_.Message }; exit 1 } else { 'PARSE_OK' }"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", probe], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PARSE_OK" in proc.stdout


def test_install_md_points_at_script_first_and_keeps_pip_steps(tmp_path: Path):
    _fake_editor_extension(tmp_path)
    out = tmp_path / "pack"
    build_voice_deploy_pack(tmp_path, out, download_wheels=False)
    text = (out / "INSTALL.md").read_text(encoding="utf-8")
    assert VOICE_INSTALL_SCRIPT_NAME in text
    assert "hive-voice-bot-0.0.1.vsix" in text
    assert "install the extension separately" not in text.lower()
    assert text.index(VOICE_INSTALL_SCRIPT_NAME) < text.index("pip install -e")
    assert f'pip install -e ".[{VOICE_EXTRA_NAME}]"' in text
    assert "ensure-runtime --install" in text


def test_install_md_explains_stt_is_optional_and_offline_limit(tmp_path: Path):
    from hive_planner.voice_bot import _voice_pack_install_md

    text = _voice_pack_install_md(tmp_path, tmp_path / "pack", wheels=True)
    assert "STT is optional" in text
    assert "faster-whisper" in text
    assert "Offline limitation" in text
    offline_line = next(line for line in text.splitlines() if "--no-index --find-links" in line)
    assert "faster-whisper" not in offline_line
    assert "-e \".[voice]\"" not in offline_line


def test_deploy_pack_without_extension_source_reports_no_vsix(tmp_path: Path):
    out = tmp_path / "pack"
    result = build_voice_deploy_pack(tmp_path, out, download_wheels=False)
    assert result["ok"] is True
    assert result["editor_vsix"] is None
    assert not list(out.glob("*.vsix"))
    assert (out / VOICE_INSTALL_SCRIPT_NAME).is_file()
    assert "**no VSIX**" in (out / "INSTALL.md").read_text(encoding="utf-8")
