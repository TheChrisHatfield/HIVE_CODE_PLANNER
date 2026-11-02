"""Unit tests for launcher mousewheel accumulation (per-target remainder)."""

from __future__ import annotations

from hive_planner.launcher import theme


def setup_function(_function) -> None:
    theme.reset_mousewheel_state_for_tests()


def test_wheel_remainder_is_kept_per_target() -> None:
    assert theme._wheel_steps(40, key=1) == 0
    assert theme._wheel_steps(40, key=1) == 0
    # A second target starts fresh: one small notch must not scroll it.
    assert theme._wheel_steps(40, key=2) == 0
    # The first target still completes its line on its own third notch.
    assert theme._wheel_steps(40, key=1) == -1


def test_wheel_remainder_does_not_eat_opposite_scroll_on_another_target() -> None:
    assert theme._wheel_steps(100, key=1) == 0
    assert theme._wheel_steps(-40, key=2) == 0
    assert theme._wheel_steps(-80, key=2) == 1


def test_tooltip_flips_above_the_widget_when_the_bottom_is_cut_off() -> None:
    # Below the widget still fits: the origin stays put, including a left-hand monitor.
    assert theme._tooltip_origin(-400, 20, 120, 40, 2560, 1440, anchor_top=10) == (-400, 20)
    # The right edge still clamps onto the primary screen.
    assert theme._tooltip_origin(2500, 20, 120, 40, 2560, 1440, anchor_top=10) == (2432, 20)
    # A control at the bottom of the screen opens the tip above itself.
    assert theme._tooltip_origin(100, 1420, 120, 40, 2560, 1440, anchor_top=1400) == (100, 1354)


def test_tooltip_stays_beside_a_control_on_another_monitor() -> None:
    assert theme._tooltip_origin(2000, 40, 120, 40, 1920, 1080, anchor_top=20) == (2000, 40)
    assert theme._tooltip_origin(100, 1200, 120, 40, 1920, 1080, anchor_top=1180) == (100, 1200)
    # The virtual desktop starts left of the primary monitor. A tip at its far
    # right edge stays on that edge instead of jumping to the primary width.
    assert theme._tooltip_origin(
        5750, 40, 200, 40, 8406, 1449, anchor_top=20, origin_x=-2560, origin_y=-9
    ) == (5638, 40)


def test_partial_notch_is_handled_once() -> None:
    scrolled: list[tuple[int, str]] = []

    class Target:
        def winfo_id(self) -> int:
            return 7

        def winfo_exists(self) -> bool:
            return True

        def yview_scroll(self, steps: int, units: str) -> None:
            scrolled.append((steps, units))

    theme._wheel_bindings[1] = Target()
    theme._wheel_stack.append(1)
    event = type("E", (), {"delta": 60})()

    assert theme._dispatch_wheel(event) == "break"
    assert scrolled == []
    assert theme._wheel_remainders[7] == 60
    assert theme._dispatch_wheel(event) == "break"
    assert scrolled == [(-1, "units")]


def test_button_wheel_stops_after_one_line() -> None:
    scrolled: list[tuple[int, str]] = []

    class Target:
        def winfo_exists(self) -> bool:
            return True

        def yview_scroll(self, steps: int, units: str) -> None:
            scrolled.append((steps, units))

    target = Target()
    theme._wheel_bindings[1] = target
    theme._wheel_stack.append(1)
    event = type("E", (), {})()

    assert theme._dispatch_wheel_up(event) == "break"
    assert theme._dispatch_wheel_down(event) == "break"
    assert scrolled == [(-1, "units"), (1, "units")]
    assert theme._dispatch_wheel_up(type("E", (), {})()) == "break"


def test_button_wheel_without_a_target_does_not_stop() -> None:
    event = type("E", (), {})()
    assert theme._dispatch_wheel_up(event) is None
    assert theme._dispatch_wheel_down(event) is None


def test_reset_clears_remainders() -> None:
    assert theme._wheel_steps(100, key=1) == 0
    theme.reset_mousewheel_state_for_tests()
    assert theme._wheel_steps(100, key=1) == 0
