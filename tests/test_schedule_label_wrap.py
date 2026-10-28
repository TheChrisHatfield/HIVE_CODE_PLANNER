"""Hub and form wraplength debounce."""

from __future__ import annotations

from hive_planner.launcher.app import HivePlannerApp


class _Widget:
    def __init__(self) -> None:
        self.callbacks: list = []
        self.cancelled: list = []

    def after(self, _delay_ms: int, callback):
        self.callbacks.append(callback)
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


def test_narrow_resize_cancels_a_pending_wide_wrap() -> None:
    widget = _Widget()
    label = _Label()
    pending: dict = {"id": None, "width": 0}
    HivePlannerApp._schedule_label_wrap(widget, (label,), 372, pending)
    HivePlannerApp._schedule_label_wrap(widget, (label,), 22, pending)
    assert widget.cancelled == [1]
    assert pending["id"] is None
    assert label.wraplength == 200
    HivePlannerApp._schedule_label_wrap(widget, (label,), 372, pending)
    widget.callbacks[-1]()
    assert label.wraplength == 372


def test_later_width_replaces_the_pending_wrap() -> None:
    widget = _Widget()
    first = _Label()
    second = _Label(180)
    pending: dict = {"id": None, "width": 0}
    HivePlannerApp._schedule_label_wrap(widget, (first, second), 100, pending)
    HivePlannerApp._schedule_label_wrap(widget, (first, second), 100, pending)
    assert len(widget.callbacks) == 1
    HivePlannerApp._schedule_label_wrap(widget, (first, second), 240, pending)
    assert widget.cancelled == [1]
    widget.callbacks[-1]()
    assert first.wraplength == 240
    assert second.wraplength == 240
