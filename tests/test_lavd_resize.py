"""Resize scheduler: deadlines, chunk budget, Thompson order, hitch update."""

from __future__ import annotations

import random

import pytest

from hive_planner.lavd_resize import SENSITIVITY, UNIT_KINDS, ResizeScheduler


def test_empty_plan_returns_nothing() -> None:
    scheduler = ResizeScheduler(rng=random.Random(0))
    assert scheduler.plan_chunk(0) == []
    before = scheduler.posterior("canvas_redraw")
    scheduler.observe(100)
    assert scheduler.posterior("canvas_redraw") == before


def test_unknown_kind_rejected() -> None:
    scheduler = ResizeScheduler()
    with pytest.raises(ValueError):
        scheduler.enqueue("not-a-unit", now_ms=0)


def test_repeat_enqueue_keeps_earlier_deadline() -> None:
    scheduler = ResizeScheduler()
    scheduler.enqueue("label_rewrap", "first", now_ms=0)
    first = scheduler.deadline("label_rewrap")
    scheduler.enqueue("label_rewrap", "second", now_ms=100)
    assert scheduler.deadline("label_rewrap") == first
    assert first == pytest.approx(48.0 * (1.0 - SENSITIVITY["label_rewrap"]))


def test_due_canvas_runs_first_and_budget_stops_optional_units() -> None:
    scheduler = ResizeScheduler(budget_ms=4, unit_cost_ms=4, rng=random.Random(1))
    for kind in UNIT_KINDS:
        scheduler.enqueue(kind, now_ms=0)
    assert scheduler.plan_chunk(0) == ["canvas_redraw"]


def test_seeded_thompson_order_is_stable() -> None:
    def order() -> list[str]:
        scheduler = ResizeScheduler(budget_ms=16, unit_cost_ms=4, rng=random.Random(7))
        for kind in UNIT_KINDS:
            scheduler.enqueue(kind, now_ms=0)
        return scheduler.plan_chunk(-1)

    assert order() == order()
    assert len(order()) == 4


def test_hitch_updates_only_kinds_that_ran() -> None:
    scheduler = ResizeScheduler(budget_ms=4, unit_cost_ms=4, rng=random.Random(0))
    for kind in UNIT_KINDS:
        scheduler.enqueue(kind, now_ms=0)
    ran = scheduler.plan_chunk(0)
    assert ran == ["canvas_redraw"]
    scheduler.observe(9)
    assert scheduler.posterior("canvas_redraw") == (1.0, 2.0)
    assert scheduler.posterior("scrollbar_pack") == (1.0, 1.0)
    scheduler.observe(0)
    assert scheduler.posterior("canvas_redraw") == (1.0, 2.0)


def test_fractional_budget_runs_each_unit_that_sums_to_the_budget() -> None:
    scheduler = ResizeScheduler(budget_ms=0.3, unit_cost_ms=0.1, rng=random.Random(0))
    kinds = ("split_reposition", "label_rewrap", "scrollbar_pack")
    for kind in kinds:
        scheduler.enqueue(kind, now_ms=0)
    assert set(scheduler.plan_chunk(-1)) == set(kinds)


def test_optional_unit_stops_when_its_cost_does_not_fit() -> None:
    scheduler = ResizeScheduler(budget_ms=6, unit_cost_ms=4, rng=random.Random(0))
    scheduler.enqueue("label_rewrap", now_ms=0)
    scheduler.enqueue("scrollbar_pack", now_ms=0)
    ran = scheduler.plan_chunk(-1)
    assert len(ran) == 1
    left = next(kind for kind in ("label_rewrap", "scrollbar_pack") if kind not in ran)
    assert scheduler.deadline(left) is not None


def test_due_unit_over_a_short_budget_blocks_optional_units() -> None:
    scheduler = ResizeScheduler(budget_ms=0.05, unit_cost_ms=0.1)
    scheduler.enqueue("canvas_redraw", now_ms=0)
    scheduler.enqueue("scrollbar_pack", now_ms=0)
    assert scheduler.plan_chunk(0) == ["canvas_redraw"]
    assert scheduler.deadline("scrollbar_pack") is not None


def test_clean_hitch_increments_alpha() -> None:
    scheduler = ResizeScheduler(budget_ms=8, unit_cost_ms=4, rng=random.Random(0))
    scheduler.enqueue("split_reposition", now_ms=0)
    scheduler.enqueue("scrollbar_pack", now_ms=0)
    ran = scheduler.plan_chunk(-1)
    assert set(ran) == {"split_reposition", "scrollbar_pack"}
    scheduler.observe(8)
    for kind in ran:
        assert scheduler.posterior(kind) == (2.0, 1.0)
