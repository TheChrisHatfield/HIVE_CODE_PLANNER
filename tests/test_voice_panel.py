"""Tests for the right-hand HIVE Voice bot panel (launcher visual shell)."""

from __future__ import annotations

import tkinter as tk

import pytest

from hive_planner.launcher import voice_panel
from hive_planner.launcher.theme import COLORS
from hive_planner.launcher.voice_panel import GREETING, LISTENING_GREETING, VoicePanel


@pytest.fixture()
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    r.withdraw()
    yield r
    r.destroy()


def _after_ids(root: tk.Misc) -> tuple:
    info = root.tk.call("after", "info")
    if not info:
        return ()
    if isinstance(info, str):
        return tuple(part for part in info.split() if part)
    return tuple(info)


def _labels(panel: VoicePanel) -> list[str]:
    out: list[str] = []

    def walk(w: tk.Misc) -> None:
        for child in w.winfo_children():
            if isinstance(child, tk.Label):
                out.append(str(child.cget("text")))
            walk(child)

    walk(panel)
    return out


def test_panel_shows_reference_text(root) -> None:
    panel = VoicePanel(root)
    labels = _labels(panel)
    assert "HIVE Voice bot" in labels
    assert "Your Assistant" in labels
    assert GREETING in labels
    assert str(panel.cget("width")) == str(voice_panel.PANEL_WIDTH)
    assert int(panel.cget("height")) >= voice_panel.PANEL_HEIGHT


def test_mic_toggles_listening_state(root) -> None:
    panel = VoicePanel(root)
    assert panel.listening is False
    panel._toggle_listening()
    assert panel.listening is True
    assert LISTENING_GREETING in _labels(panel)
    panel._toggle_listening()
    assert panel.listening is False
    assert GREETING in _labels(panel)


def test_end_call_resets_and_fires_callback(root) -> None:
    calls: list[str] = []
    panel = VoicePanel(root, on_end=lambda: calls.append("end"))
    panel._toggle_listening()
    panel._end_call()
    assert panel.listening is False
    assert GREETING in _labels(panel)
    assert calls == ["end"]


def test_blob_points_form_closed_ring() -> None:
    points = voice_panel._blob_points(50, 50, 20, 0.0, 0.05)
    assert len(points) == 32
    assert all(isinstance(v, float) for v in points)


def test_animation_cancelled_on_destroy(root) -> None:
    panel = VoicePanel(root)
    root.update()
    assert panel._after_id is not None
    panel.destroy()
    root.update()
    assert panel._after_id is None
    assert _after_ids(root) == ()


def test_child_destroy_does_not_stop_animation(root) -> None:
    panel = VoicePanel(root)
    root.update()
    child = tk.Frame(panel)
    child.destroy()
    root.update()
    assert panel._after_id is not None
    assert _after_ids(root)
    panel.destroy()
    root.update()
    assert _after_ids(root) == ()


def test_header_icons_are_inert_without_callbacks(root) -> None:
    panel = VoicePanel(root)
    icons: list[tk.Label] = []

    def walk(w: tk.Misc) -> None:
        for child in w.winfo_children():
            if isinstance(child, tk.Label) and str(child.cget("text")) in ("\u2190", "\u22ef"):
                icons.append(child)
            walk(child)

    walk(panel)
    assert [str(icon.cget("cursor")) for icon in icons] == ["", ""]
    assert all(not icon.bind("<Button-1>") for icon in icons)


def test_header_icons_bind_when_callbacks_given(root) -> None:
    panel = VoicePanel(root, on_back=lambda: None, on_menu=lambda: None)
    buttons: dict[str, tk.Label] = {}

    def walk(w: tk.Misc) -> None:
        for child in w.winfo_children():
            if isinstance(child, tk.Label):
                text = str(child.cget("text"))
                if text in ("\u2190", "\u22ef"):
                    buttons[text] = child
            walk(child)

    walk(panel)
    assert str(buttons["\u2190"].cget("cursor")) == "hand2"
    assert str(buttons["\u22ef"].cget("cursor")) == "hand2"
    assert buttons["\u2190"].bind("<Button-1>")
    assert buttons["\u22ef"].bind("<Button-1>")


def test_launcher_app_exports_voice_panel() -> None:
    from hive_planner.launcher import app as launcher_app

    assert launcher_app.PANEL_WIDTH == voice_panel.PANEL_WIDTH
    assert launcher_app.VoicePanel is VoicePanel


def test_toggle_and_end_after_destroy_do_not_raise(root) -> None:
    ended: list[str] = []
    panel = VoicePanel(root, on_end=lambda: ended.append("end"))
    root.update()
    panel.destroy()
    root.update()
    panel._toggle_listening()
    panel._end_call()
    assert panel.listening is False
    assert ended == []


def test_draw_error_does_not_stop_animation(root) -> None:
    panel = VoicePanel(root)
    root.update()
    real = panel._draw_orb
    panel.winfo_viewable = lambda: True  # type: ignore[method-assign]

    def boom() -> None:
        raise tk.TclError("orb")

    panel._draw_orb = boom  # type: ignore[method-assign]
    panel._animate()
    root.update()
    panel._draw_orb = real  # type: ignore[method-assign]
    assert panel._after_id is not None
    panel.destroy()
    root.update()
    assert _after_ids(root) == ()


def test_toggle_restores_greeting_when_mic_draw_fails(root) -> None:
    panel = VoicePanel(root)

    def boom() -> None:
        raise tk.TclError("mic")

    panel._draw_mic = boom  # type: ignore[method-assign]
    panel._toggle_listening()
    assert panel.listening is False
    assert GREETING in _labels(panel)
    panel.destroy()
    root.update()


def test_toggle_ignored_during_end_call(root) -> None:
    holder: dict[str, VoicePanel] = {}

    def on_end() -> None:
        holder["p"]._toggle_listening()

    panel = VoicePanel(root, on_end=on_end)
    holder["p"] = panel
    panel._toggle_listening()
    panel._end_call()
    assert panel.listening is False
    assert GREETING in _labels(panel)
    panel.destroy()
    root.update()


def test_end_call_swallows_callback_tclerror(root) -> None:
    panel = VoicePanel(root, on_end=lambda: (_ for _ in ()).throw(tk.TclError("cb")))
    panel._toggle_listening()
    panel._end_call()
    assert panel.listening is False
    assert GREETING in _labels(panel)
    panel.destroy()
    root.update()


def test_toggle_reverts_when_refresh_fails(root) -> None:
    panel = VoicePanel(root)
    def boom(**_kwargs):
        raise tk.TclError("greeting")

    panel._greeting.configure = boom  # type: ignore[method-assign]
    panel._toggle_listening()
    assert panel.listening is False
    panel.destroy()
    root.update()


def test_end_call_is_not_reentrant(root) -> None:
    hits: list[str] = []
    panel_holder: dict[str, VoicePanel] = {}

    def boom() -> None:
        hits.append("end")
        panel_holder["p"]._end_call()

    panel = VoicePanel(root, on_end=boom)
    panel_holder["p"] = panel
    panel._end_call()
    assert hits == ["end"]
    assert panel.listening is False
    panel.destroy()
    root.update()


def test_destroy_clears_listening_and_dead_end_does_not_fire(root) -> None:
    ended: list[str] = []
    panel = VoicePanel(root, on_end=lambda: ended.append("end"))
    panel._toggle_listening()
    assert panel.listening is True
    panel.destroy()
    root.update()
    assert panel.listening is False
    panel._end_call()
    assert ended == []


def test_destroy_handler_cancels_when_identity_raises(root) -> None:
    panel = VoicePanel(root)
    root.update()

    class Event:
        widget = panel

    original = VoicePanel.__str__

    def boom(_self) -> str:
        raise tk.TclError("gone")

    VoicePanel.__str__ = boom  # type: ignore[method-assign]
    try:
        panel._on_destroy(Event())
    finally:
        VoicePanel.__str__ = original  # type: ignore[method-assign]
    assert panel._after_id is None
    panel.destroy()
    root.update()
    assert _after_ids(root) == ()


def test_intrinsic_size_is_not_a_one_pixel_strip(root) -> None:
    panel = VoicePanel(root)
    assert int(panel.cget("width")) == voice_panel.PANEL_WIDTH
    assert int(panel.winfo_reqheight()) >= voice_panel.PANEL_HEIGHT
    panel.destroy()
    root.update()


def test_animate_does_not_stack_timers(root) -> None:
    panel = VoicePanel(root)
    root.update()
    panel._animate()
    panel._animate()
    root.update_idletasks()
    assert len(_after_ids(root)) == 1
    panel.destroy()
    root.update()
    assert _after_ids(root) == ()


def _footer(panel: VoicePanel) -> tk.Frame:
    for child in panel.winfo_children():
        if isinstance(child, tk.Frame) and any(
            isinstance(c, tk.Canvas) and int(c.cget("width")) == 56 for c in child.winfo_children()
        ):
            return child
    raise AssertionError("footer not found")


def test_body_expands_between_header_and_footer(root) -> None:
    panel = VoicePanel(root)
    footer = _footer(panel)
    body = panel._orb.master
    assert footer.pack_info()["side"] == "bottom"
    assert int(body.pack_info()["expand"]) == 1
    assert body.pack_info()["fill"] == "both"
    spacers = [
        child
        for child in body.winfo_children()
        if isinstance(child, tk.Frame) and not child.winfo_children()
    ]
    assert len(spacers) == 2
    assert all(int(child.pack_info()["expand"]) == 1 for child in spacers)
    panel.destroy()
    root.update()


def test_hangup_is_packed_before_expanding_mic(root) -> None:
    panel = VoicePanel(root)
    footer = _footer(panel)
    side, end, mic = footer.winfo_children()
    assert mic is panel._mic
    assert end is panel._hangup
    assert side.pack_info()["side"] == "left"
    assert end.pack_info()["side"] == "right"
    assert mic.pack_info()["side"] == "left"
    assert int(mic.pack_info()["expand"]) == 1
    panel.destroy()
    root.update()


def test_mic_glyph_is_narrow_capsule_with_u_cradle(root) -> None:
    panel = VoicePanel(root)
    capsule = panel._mic.bbox("capsule")
    assert capsule is not None
    width = capsule[2] - capsule[0]
    height = capsule[3] - capsule[1]
    assert width < height
    assert width <= 10
    cradle = panel._mic.find_withtag("cradle")
    assert len(cradle) == 1
    assert float(panel._mic.itemcget(cradle[0], "start")) == 180
    assert float(panel._mic.itemcget(cradle[0], "extent")) == 180
    assert panel._mic.find_withtag("listen-ring") == ()
    panel._toggle_listening()
    assert panel._mic.find_withtag("listen-ring")
    assert panel._mic.itemcget(panel._mic.find_withtag("bg")[0], "fill") == COLORS["primary_light"]
    panel.destroy()
    root.update()


def test_hangup_is_red_with_white_x(root) -> None:
    panel = VoicePanel(root)
    bg = panel._hangup.find_withtag("bg")
    assert len(bg) == 1
    assert panel._hangup.itemcget(bg[0], "fill") == COLORS["error"]
    glyphs = panel._hangup.find_withtag("glyph")
    assert len(glyphs) == 2
    assert all(panel._hangup.itemcget(item, "fill") == "white" for item in glyphs)
    panel.destroy()
    root.update()


def test_mousewheel_on_panel_does_not_scroll_sibling(root) -> None:
    from hive_planner.launcher.theme import bind_mousewheel, reset_mousewheel_state_for_tests

    reset_mousewheel_state_for_tests()
    canvas = tk.Canvas(root, width=120, height=120)
    canvas.pack(side="left")
    canvas.create_rectangle(0, 0, 80, 800, fill="white")
    canvas.configure(scrollregion=(0, 0, 80, 800))
    bind_mousewheel(canvas, target=canvas)
    canvas.event_generate("<Enter>")
    panel = VoicePanel(root)
    panel.pack(side="right")
    root.update()
    canvas.yview_moveto(0)
    before = canvas.yview()
    panel._mic.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert canvas.yview() == before
    panel.destroy()
    canvas.destroy()
    reset_mousewheel_state_for_tests()
    root.update()


def test_mic_refusal_reverts_state_and_shows_message(root) -> None:
    calls: list[bool] = []

    def refuse(start: bool) -> str:
        calls.append(start)
        return "stt_not_configured refused"

    panel = VoicePanel(root, on_mic=refuse)
    panel._toggle_listening()
    assert calls == [True]
    assert panel.listening is False
    assert GREETING not in _labels(panel)
    assert "stt_not_configured refused" in _labels(panel)
    panel.destroy()
    root.update()


def test_mic_stop_refusal_does_not_revert_to_listening(root) -> None:
    calls: list[bool] = []

    def on_mic(start: bool):
        calls.append(start)
        return None if start else "could not save the recording"

    panel = VoicePanel(root, on_mic=on_mic)
    panel._toggle_listening()
    assert panel.listening is True
    panel._toggle_listening()
    assert calls == [True, False]
    # The recorder is already stopped on a stop call, so a refused send must not show "listening".
    assert panel.listening is False
    assert "could not save the recording" in _labels(panel)
    panel.destroy()
    root.update()


def test_mic_accepted_callback_keeps_listening(root) -> None:
    calls: list[bool] = []
    panel = VoicePanel(root, on_mic=lambda start: calls.append(start))
    panel._toggle_listening()
    assert calls == [True]
    assert panel.listening is True
    assert LISTENING_GREETING in _labels(panel)
    panel._toggle_listening()
    assert calls == [True, False]
    assert panel.listening is False
    panel.destroy()
    root.update()


# --- T042 slice 5b: side button (typed instruction) ---------------------------


def _side_canvas(panel: VoicePanel) -> tk.Canvas:
    footer = _footer(panel)
    side = footer.winfo_children()[0]
    assert isinstance(side, tk.Canvas)
    assert side is panel._side
    return side


def test_side_canvas_binds_hand_cursor_when_on_side_set(root) -> None:
    panel = VoicePanel(root, on_side=lambda: None)
    side = _side_canvas(panel)
    assert str(side.cget("cursor")) == "hand2"
    assert side.bind("<Button-1>")
    panel.destroy()
    root.update()


def test_side_canvas_inert_without_on_side(root) -> None:
    panel = VoicePanel(root)
    side = _side_canvas(panel)
    assert str(side.cget("cursor")) == ""
    assert not side.bind("<Button-1>")
    panel.destroy()
    root.update()


def test_side_click_fires_on_side(root) -> None:
    calls: list[str] = []
    panel = VoicePanel(root, on_side=lambda: calls.append("side"))
    panel.pack()
    root.deiconify()
    root.geometry("+0+0")
    root.update()
    side = _side_canvas(panel)
    side.focus_force()
    side.event_generate("<Button-1>", x=10, y=10)
    root.update()
    assert calls == ["side"]
    panel.destroy()
    root.update()


def test_voice_on_side_sends_typed_text_and_shows_success(monkeypatch) -> None:
    """Handler wiring: dialog -> controller.submit_typed -> panel message. Dialog/messagebox stubbed."""
    from hive_planner.launcher import app as launcher_app
    from hive_planner.launcher.voice_panel_controller import SubmitResult

    shown: list[str] = []
    boxes: list[str] = []
    asked: dict[str, object] = {}

    class _Ctrl:
        last_instruction = "previous"

        def submit_typed(self, text: str) -> SubmitResult:
            asked["sent"] = text
            return SubmitResult(True, "submitted", "Sent. Task t-9 started.", "t-9")

    class _Panel:
        def show_message(self, text: str) -> None:
            shown.append(text)

    class _Self:
        voice_controller = _Ctrl()
        voice_panel = _Panel()
        root = None

    def fake_ask(title, prompt, **kwargs):
        asked["initialvalue"] = kwargs.get("initialvalue")
        return "  do the thing  "

    monkeypatch.setattr(launcher_app.simpledialog, "askstring", fake_ask)
    monkeypatch.setattr(launcher_app.messagebox, "showinfo", lambda *a, **k: boxes.append(a[1]))
    launcher_app.HivePlannerApp._voice_on_side(_Self())
    assert asked["initialvalue"] == "previous"
    assert asked["sent"] == "  do the thing  "
    assert shown == ["Sent. Task t-9 started."]
    assert boxes == []


def test_voice_on_side_cancel_sends_nothing(monkeypatch) -> None:
    from hive_planner.launcher import app as launcher_app

    class _Ctrl:
        last_instruction = None

        def submit_typed(self, text: str):  # pragma: no cover - must not run
            raise AssertionError("cancel must not submit")

    class _Self:
        voice_controller = _Ctrl()
        voice_panel = None
        root = None

    monkeypatch.setattr(launcher_app.simpledialog, "askstring", lambda *a, **k: None)
    launcher_app.HivePlannerApp._voice_on_side(_Self())


def test_voice_on_side_refusal_shows_messagebox(monkeypatch) -> None:
    from hive_planner.launcher import app as launcher_app
    from hive_planner.launcher.voice_panel_controller import SubmitResult

    boxes: list[str] = []

    class _Ctrl:
        last_instruction = None

        def submit_typed(self, text: str) -> SubmitResult:
            return SubmitResult(False, "bridge_not_running", "Bridge is not running. Nothing was sent.")

    class _Self:
        voice_controller = _Ctrl()
        voice_panel = None
        root = None

    monkeypatch.setattr(launcher_app.simpledialog, "askstring", lambda *a, **k: "hi")
    monkeypatch.setattr(launcher_app.messagebox, "showinfo", lambda *a, **k: boxes.append(a[1]))
    launcher_app.HivePlannerApp._voice_on_side(_Self())
    assert boxes == ["Bridge is not running. Nothing was sent."]
