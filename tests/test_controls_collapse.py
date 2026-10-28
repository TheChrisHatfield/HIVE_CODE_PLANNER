from __future__ import annotations

from hive_planner.launcher.app import HivePlannerApp


class _Bool:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value

    def set(self, value: bool) -> None:
        self.value = bool(value)


class _Widget:
    def __init__(self) -> None:
        self.forgotten = 0
        self.packed = 0
        self.text = ""

    def pack_forget(self) -> None:
        self.forgotten += 1

    def pack(self, **_k) -> None:
        self.packed += 1

    def configure(self, **kwargs) -> None:
        if "text" in kwargs:
            self.text = str(kwargs["text"])


def test_added_loop_block_starts_collapsed() -> None:
    assert HivePlannerApp.added_controls_block_collapsed() is True
    assert HivePlannerApp.controls_instance_collapsed({}) is False
    assert HivePlannerApp.controls_instance_collapsed({"collapsed": _Bool(True)}) is True


def test_collapse_hides_settings_and_keeps_run_row() -> None:
    app = HivePlannerApp.__new__(HivePlannerApp)
    settings = _Widget()
    last = _Widget()
    button = _Widget()
    inst = {
        "collapsed": _Bool(True),
        "settings": settings,
        "last_label": last,
        "collapse_btn": button,
        "rows": {"reward": _Widget()},
    }
    app._apply_controls_collapse(inst)
    assert settings.forgotten == 1
    assert last.forgotten == 0
    assert button.text == "▸"


def test_expand_shows_settings_again() -> None:
    app = HivePlannerApp.__new__(HivePlannerApp)
    settings = _Widget()
    last = _Widget()
    button = _Widget()
    inst = {
        "collapsed": _Bool(False),
        "settings": settings,
        "last_label": last,
        "collapse_btn": button,
        "loop": type("V", (), {"get": lambda self: "Bug hunt"})(),
        "rows": {},
    }
    app._apply_controls_collapse(inst)
    assert last.packed == 1
    assert settings.packed == 1
    assert button.text == "▾"


def test_first_collapse_click_works_when_flag_is_missing() -> None:
    app = HivePlannerApp.__new__(HivePlannerApp)
    settings = _Widget()
    inst = {
        "settings": settings,
        "last_label": _Widget(),
        "collapse_btn": _Widget(),
        "rows": {},
        "loop": type("V", (), {"get": lambda self: "CodeSpec"})(),
    }
    app._on_toggle_controls_collapse(inst)
    assert HivePlannerApp.controls_instance_collapsed(inst) is True
    assert settings.forgotten == 1


def test_reveal_codespec_expands_without_scroll_canvas() -> None:
    app = HivePlannerApp.__new__(HivePlannerApp)
    inst = {
        "loop": type("V", (), {"get": lambda self: "CodeSpec"})(),
        "collapsed": _Bool(True),
        "settings": _Widget(),
        "last_label": _Widget(),
        "collapse_btn": _Widget(),
        "rows": {},
        "frame": object(),
    }
    app._controls_instances = [inst]
    app._controls_canvas = None
    app._reveal_codespec_block()
    assert HivePlannerApp.controls_instance_collapsed(inst) is False
    assert inst["settings"].packed == 1


def test_toggle_collapse_flips_hidden_fields() -> None:
    app = HivePlannerApp.__new__(HivePlannerApp)
    inst = {
        "collapsed": _Bool(False),
        "settings": _Widget(),
        "last_label": _Widget(),
        "collapse_btn": _Widget(),
        "rows": {},
        "loop": type("V", (), {"get": lambda self: "CodeSpec"})(),
    }
    app._on_toggle_controls_collapse(inst)
    assert HivePlannerApp.controls_instance_collapsed(inst) is True
    assert inst["settings"].forgotten == 1
    assert inst["last_label"].forgotten == 0
    app._on_toggle_controls_collapse(inst)
    assert HivePlannerApp.controls_instance_collapsed(inst) is False
    assert inst["settings"].packed == 1
