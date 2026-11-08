"""Hub and form wraplength goes through the resize scheduler."""

from __future__ import annotations

from hive_planner.launcher.app import HivePlannerApp


class _Widget:
    def __init__(self) -> None:
        self.callbacks: list = []
        self.cancelled: list = []
        self.delays: list[int] = []

    def after(self, delay_ms: int, callback):
        self.callbacks.append(callback)
        self.delays.append(delay_ms)
        return len(self.callbacks)

    def after_cancel(self, token) -> None:
        self.cancelled.append(token)


class _Label:
    def __init__(self, wraplength: int = 200) -> None:
        self.wraplength = wraplength

    def cget(self, key: str) -> int:
        if key != "wraplength":
            raise KeyError(key)
        return self.wraplength

    def configure(self, *, wraplength: int) -> None:
        self.wraplength = wraplength


class _Harness(HivePlannerApp):
    def __init__(self) -> None:
        self.now = 0.0
        self.root = _Widget()
        self._resize_clock = lambda: self.now
        self._resize_scheduler = None
        self._resize_slots = {}
        self._resize_pump_job = None
        self._resize_in_chunk = False

    def run_pump(self) -> None:
        self.root.callbacks[-1]()


def test_callback_replaced_during_the_chunk_is_not_called() -> None:
    app = _Harness()
    ran: list[str] = []

    def first() -> None:
        ran.append("first")
        app._resize_put("canvas_redraw", "second", lambda: ran.append("replaced"))

    app._resize_put("canvas_redraw", "first", first)
    app._resize_put("canvas_redraw", "second", lambda: ran.append("old"))
    app.now = app.root.delays[-1]
    app.run_pump()
    assert ran == ["first"]
    app.now = app.root.delays[-1]
    app.run_pump()
    assert ran == ["first", "replaced"]


def test_narrow_resize_cancels_a_pending_wide_wrap() -> None:
    app = _Harness()
    label = _Label()
    pending: dict = {"id": None, "width": 0}
    HivePlannerApp._schedule_label_wrap(app, app.root, (label,), 372, pending)
    assert app._resize_scheduler.deadline("label_rewrap") is not None
    HivePlannerApp._schedule_label_wrap(app, app.root, (label,), 22, pending)
    assert app._resize_scheduler.deadline("label_rewrap") is None
    assert pending["id"] is None
    assert label.wraplength == 200
    HivePlannerApp._schedule_label_wrap(app, app.root, (label,), 372, pending)
    app.now = 32
    app.run_pump()
    assert label.wraplength == 372


def test_later_width_replaces_the_pending_wrap() -> None:
    app = _Harness()
    first = _Label()
    second = _Label(180)
    pending: dict = {"id": None, "width": 0}
    HivePlannerApp._schedule_label_wrap(app, app.root, (first, second), 100, pending)
    first_deadline = app._resize_scheduler.deadline("label_rewrap")
    HivePlannerApp._schedule_label_wrap(app, app.root, (first, second), 100, pending)
    assert app._resize_scheduler.deadline("label_rewrap") == first_deadline
    assert len(app.root.callbacks) == 1
    HivePlannerApp._schedule_label_wrap(app, app.root, (first, second), 240, pending)
    assert app._resize_scheduler.deadline("label_rewrap") == first_deadline
    app.now = 32
    app.run_pump()
    assert first.wraplength == 240
    assert second.wraplength == 240


def test_resize_handlers_wait_for_virtual_deadlines() -> None:
    app = _Harness()
    pending: dict = {"id": None, "width": 0}
    label = _Label()
    HivePlannerApp._schedule_label_wrap(app, app.root, (label,), 300, pending)

    applied: list[str] = []
    app.projects_split = object()
    app._apply_projects_split_sash = lambda: applied.append("split")
    HivePlannerApp._place_projects_split_once(app)

    app._projects_top_canvas = object()
    app._apply_projects_top_scroll = lambda: applied.append("scroll")
    HivePlannerApp._sync_projects_top_scroll(app)

    app.recent_list = object()
    app._sync_recent_scrollbar = lambda: applied.append("recent")
    HivePlannerApp._schedule_recent_scrollbar(app)

    app._resize_put("canvas_redraw", "canvas", lambda: applied.append("canvas"))

    app.run_pump()
    assert applied == ["canvas"]
    assert label.wraplength == 200
    assert app._resize_scheduler.posterior("canvas_redraw") == (2.0, 1.0)
    assert app._resize_scheduler.posterior("split_reposition") == (1.0, 1.0)

    app.now = 22
    app.run_pump()
    assert applied == ["canvas", "split"]
    assert app._resize_scheduler.posterior("split_reposition") == (2.0, 1.0)
    assert label.wraplength == 200

    app.now = 32
    app.run_pump()
    assert label.wraplength == 300
    assert "scroll" not in applied
    assert app._resize_scheduler.posterior("label_rewrap") == (2.0, 1.0)
    assert app._resize_scheduler.posterior("scrollbar_pack") == (1.0, 1.0)

    app.now = 41
    app.run_pump()
    assert applied == ["canvas", "split", "scroll", "recent"]
    assert app._resize_scheduler.posterior("scrollbar_pack") == (2.0, 1.0)
    assert app._resize_scheduler.next_deadline_ms() is None


def test_pump_waits_until_the_earlier_deadline() -> None:
    app = _Harness()
    ran: list[str] = []
    app._resize_put("split_reposition", "projects", lambda: ran.append("split"))
    app._resize_put("label_rewrap", "hub", lambda: ran.append("label"))
    assert app.root.delays[-1] == 22
    app.now = app.root.delays[-1]
    app.run_pump()
    assert ran == ["split"]
    assert app._resize_scheduler.deadline("label_rewrap") is not None


def test_failed_projects_scrollbar_sync_is_a_posterior_miss() -> None:
    import tkinter as tk

    class _Canvas:
        def yview(self) -> tuple[float, float]:
            raise tk.TclError("yview failed")

    app = _Harness()
    app._projects_top_canvas = _Canvas()
    app._projects_top_scroll = object()
    app._resize_put("scrollbar_pack", "projects_top", app._apply_projects_top_scroll)
    app.now = 41
    app.run_pump()
    assert app._resize_scheduler.posterior("scrollbar_pack") == (1.0, 2.0)
    assert isinstance(app._resize_last_error, tk.TclError)
    assert app._resize_scheduler.deadline("scrollbar_pack") is None


def test_failed_recent_scrollbar_sync_is_a_posterior_miss() -> None:
    import tkinter as tk

    class _List:
        def size(self) -> int:
            return 3

        def winfo_height(self) -> int:
            return 40

        def yview(self) -> tuple[float, float]:
            return (0.0, 0.5)

        def cget(self, _key: str) -> int:
            return 4

        def winfo_ismapped(self) -> bool:
            raise tk.TclError("list is gone")

    app = _Harness()
    app.recent_list = _List()
    app.recent_scroll = _List()
    app._resize_put("scrollbar_pack", "recent", app._sync_recent_scrollbar)
    app.now = 41
    app.run_pump()
    assert app._resize_scheduler.posterior("scrollbar_pack") == (1.0, 2.0)
    assert isinstance(app._resize_last_error, tk.TclError)
