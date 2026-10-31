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


def test_reset_clears_remainders() -> None:
    assert theme._wheel_steps(100, key=1) == 0
    theme.reset_mousewheel_state_for_tests()
    assert theme._wheel_steps(100, key=1) == 0
