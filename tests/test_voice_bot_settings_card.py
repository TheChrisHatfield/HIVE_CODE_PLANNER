"""T042-s5-settings-1: read-only HIVE Voice Bot card in Settings (faked project root, no Tk window)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from hive_planner.launcher.voice_panel_controller import VoicePanelController
from hive_planner.voice_stt import STT_PIN_PROVIDER


def _write_config(root: Path, **fields) -> None:
    path = root / ".hive" / "voice-bot"
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(json.dumps(fields), encoding="utf-8")


def _app_for_root(root: Path | None):
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = SimpleNamespace(active_project=str(root) if root else "")
    app.voice_controller = VoicePanelController(app._voice_project_root)
    return app


def test_card_reflects_loaded_config_values(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        stt_provider=STT_PIN_PROVIDER,
        audio_enabled=True,
        edits_enabled=True,
    )
    text = _app_for_root(tmp_path)._voice_bot_card_text()
    assert f"stt_provider: {STT_PIN_PROVIDER}" in text
    assert "audio_enabled: on" in text
    assert "edits_enabled (config): on" in text
    assert "Bridge: not running" in text


def test_card_defaults_when_config_missing(tmp_path: Path) -> None:
    text = _app_for_root(tmp_path)._voice_bot_card_text()
    assert "stt_provider: off (typed only)" in text
    assert "audio_enabled: off" in text
    assert "edits_enabled (config): off" in text


def test_card_shows_config_error_instead_of_defaults(tmp_path: Path) -> None:
    _write_config(tmp_path, audio_enabled=True, not_a_real_key=1)
    text = _app_for_root(tmp_path)._voice_bot_card_text()
    assert text.startswith("Config error:")
    assert "not_a_real_key" in text
    assert "audio_enabled" not in text


def test_card_without_project_reports_defaults(tmp_path: Path) -> None:
    text = _app_for_root(None)._voice_bot_card_text()
    assert "stt_provider: off (typed only)" in text


def test_card_sits_between_agent_mcp_and_pro_tip() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    source = inspect.getsource(HivePlannerApp._build_settings_tab)
    mcp = source.index('"Agent MCP (control Hive Planner)"')
    voice = source.index('"HIVE Voice Bot (read-only)"')
    tip = source.index('"Pro tip"')
    assert mcp < voice < tip


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def config(self, **kwargs) -> None:
        self.text = kwargs["text"]


def test_sync_refreshes_card_text_for_active_project(tmp_path: Path) -> None:
    app = _app_for_root(tmp_path)
    app.voice_card_label = _FakeLabel()
    app.voice_card_label.text = app._voice_bot_card_text()
    assert "audio_enabled: off" in app.voice_card_label.text
    _write_config(tmp_path, audio_enabled=True)
    app._sync_voice_bot_card_for_active()
    assert "audio_enabled: on" in app.voice_card_label.text


def test_input_device_dropdown_handler_saves_and_refreshes_card_from_reload(tmp_path: Path) -> None:
    # T042c: the Settings dropdown handler must call set_input_device, save to config.json,
    # then refresh the card from the reloaded value (blank choice -> null).
    _write_config(tmp_path, audio_enabled=False)
    app = _app_for_root(tmp_path)
    app.voice_card_label = _FakeLabel()
    app.voice_card_label.text = app._voice_bot_card_text()

    result = app._on_voice_input_device_selected("USB Microphone")

    assert result.ok is True
    assert result.input_device == "USB Microphone"
    saved = json.loads((tmp_path / ".hive" / "voice-bot" / "config.json").read_text(encoding="utf-8"))
    assert saved["input_device"] == "USB Microphone"
    assert "input_device: USB Microphone" in app.voice_card_label.text

    blank = app._on_voice_input_device_selected("")
    assert blank.input_device is None
    saved = json.loads((tmp_path / ".hive" / "voice-bot" / "config.json").read_text(encoding="utf-8"))
    assert saved["input_device"] is None
    assert "input_device: off" in app.voice_card_label.text


def test_sync_is_noop_before_settings_tab_built(tmp_path: Path) -> None:
    app = _app_for_root(tmp_path)
    app._sync_voice_bot_card_for_active()  # must not raise


def test_sync_wired_into_refresh_and_settings_revisit() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    refresh = inspect.getsource(HivePlannerApp._soft_refresh_dashboard)
    tab_changed = inspect.getsource(HivePlannerApp._on_dashboard_tab_changed)
    assert "_sync_voice_bot_card_for_active()" in refresh
    assert "_sync_voice_bot_card_for_active()" in tab_changed
    assert "_settings_tab_frame" in tab_changed


class _FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _FakeBox:
    def __init__(self) -> None:
        self.values: list[str] = []

    def configure(self, **kwargs) -> None:
        if "values" in kwargs:
            self.values = list(kwargs["values"])


def _app_with_mic_widgets(root: Path | None):
    app = _app_for_root(root)
    app.voice_card_label = _FakeLabel()
    app.voice_card_label.text = app._voice_bot_card_text()
    app.voice_input_device_var = _FakeVar(app.voice_controller.status()["input_device"] or "")
    app.voice_input_device_box = _FakeBox()
    return app


def test_project_switch_refreshes_microphone_dropdown(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _write_config(root_a, input_device="Mic A")
    _write_config(root_b, input_device="Mic B")
    app = _app_with_mic_widgets(root_a)
    assert app.voice_input_device_var.get() == "Mic A"
    app.config.active_project = str(root_b)
    app._sync_voice_bot_card_for_active()
    assert app.voice_input_device_var.get() == "Mic B"
    assert app.voice_input_device_box.values == ["", "Mic B"]


def test_refused_save_reverts_dropdown_and_warns(tmp_path: Path, monkeypatch) -> None:
    import hive_planner.launcher.app as app_module

    _write_config(tmp_path, not_a_real_key=1)  # broken config -> controller refuses the save
    app = _app_with_mic_widgets(tmp_path)
    warnings: list[str] = []
    monkeypatch.setattr(
        app_module.messagebox,
        "showwarning",
        lambda title, message, **kwargs: warnings.append(message),
    )
    app.voice_input_device_var.set("Mic X")
    result = app._on_voice_input_device_selected("Mic X")
    assert result.ok is False
    assert app.voice_input_device_var.get() == ""
    assert warnings, "a refused save must tell the user"


def test_successful_save_keeps_saved_value_in_dropdown(tmp_path: Path) -> None:
    _write_config(tmp_path, audio_enabled=False)
    app = _app_with_mic_widgets(tmp_path)
    app.voice_input_device_var.set("Mic X")
    app._on_voice_input_device_selected("Mic X")
    assert app.voice_input_device_var.get() == "Mic X"
    assert "Mic X" in app.voice_input_device_box.values


def test_real_tk_settings_tab_dropdown_saves_on_combobox_event(tmp_path: Path) -> None:
    # Real Tk: builds the real _build_settings_tab in a hidden window and fires the combobox event.
    # Other app attributes the tab reads are auto-stubbed; only the Voice Bot card path is real.
    import tkinter as tk
    from unittest.mock import MagicMock

    from hive_planner.launcher.config import LauncherConfig
    from hive_planner.launcher.app import HivePlannerApp

    class _ProbeApp(HivePlannerApp):
        def __getattr__(self, name: str):
            if name.startswith("_"):
                raise AttributeError(name)
            mock = MagicMock(name=name)
            object.__setattr__(self, name, mock)
            return mock

    try:
        root = tk.Tk()
    except tk.TclError:
        import pytest

        pytest.skip("no display available for Tk")
    root.withdraw()
    try:
        _write_config(tmp_path, input_device="Mic A")
        app = _ProbeApp.__new__(_ProbeApp)
        app.root = root
        app.config = LauncherConfig(active_project=str(tmp_path))
        app.voice_controller = VoicePanelController(app._voice_project_root)
        app._build_settings_tab(tk.Frame(root))

        assert app.voice_input_device_var.get() == "Mic A"
        app.voice_input_device_var.set("Mic B")
        app.voice_input_device_box.event_generate("<<ComboboxSelected>>")
        root.update()

        saved = json.loads((tmp_path / ".hive" / "voice-bot" / "config.json").read_text(encoding="utf-8"))
        assert saved["input_device"] == "Mic B"
        assert app.voice_input_device_var.get() == "Mic B"
        assert "Mic B" in app.voice_input_device_box.cget("values")
    finally:
        root.destroy()


def test_input_device_dropdown_wired_inside_voice_bot_card() -> None:
    # T042c: the dropdown in the Voice Bot card must call _on_voice_input_device_selected.
    from hive_planner.launcher.app import HivePlannerApp

    source = inspect.getsource(HivePlannerApp._build_settings_tab)
    start = source.index('card_title(voice_card, "HIVE Voice Bot (read-only)")')
    end = source.index('"Pro tip"')
    assert start < end
    card_section = source[start:end]
    assert "_on_voice_input_device_selected" in card_section
