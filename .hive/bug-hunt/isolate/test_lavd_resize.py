"""Resize scheduler: deadlines hold the queue, Thompson fill, per-kind hitch."""

from __future__ import annotations

import random

import pytest

from hive_planner.lavd_resize import SENSITIVITY, UNIT_KINDS, ResizeScheduler


def test_empty_plan_returns_nothing() -> None:
    scheduler = ResizeScheduler(rng=random.Random(0))
    assert scheduler.plan_chunk(0) == []
    before = scheduler.posterior("canvas_redraw")
    scheduler.observe({})
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
    assert scheduler.plan_chunk(first) == ["label_rewrap"]
    assert scheduler.ran_payload("label_rewrap") == "second"


def test_default_budget_holds_work_until_its_deadline() -> None:
    """Shipped defaults: one unit per chunk. The other three stay queued."""
    scheduler = ResizeScheduler(rng=random.Random(0))
    for kind in UNIT_KINDS:
        scheduler.enqueue(kind, kind, now_ms=0)
    assert scheduler.budget_ms == scheduler.unit_cost_ms
    assert scheduler.plan_chunk(0) == ["canvas_redraw"]
    assert scheduler.ran_payload("canvas_redraw") == "canvas_redraw"
    assert scheduler.deadline("split_reposition") == pytest.approx(48.0 * (1.0 - SENSITIVITY["split_reposition"]))
    assert scheduler.deadline("label_rewrap") is not None
    assert scheduler.deadline("scrollbar_pack") is not None
    assert scheduler.plan_chunk(21.6) == ["split_reposition"]
    assert scheduler.plan_chunk(100) == ["label_rewrap"]
    assert scheduler.deadline("scrollbar_pack") is not None


def test_seeded_thompson_order_is_stable() -> None:
    def picked() -> list[str]:
        scheduler = ResizeScheduler(rng=random.Random(7))
        for kind in UNIT_KINDS:
            scheduler.enqueue(kind, now_ms=0)
        return scheduler.plan_chunk(-1)

    assert picked() == picked()
    assert len(picked()) == 1


def test_thompson_fill_stops_before_the_queue_is_empty() -> None:
    def picked() -> list[str]:
        scheduler = ResizeScheduler(budget_ms=8, unit_cost_ms=4, rng=random.Random(7))
        for kind in ("split_reposition", "label_rewrap", "scrollbar_pack"):
            scheduler.enqueue(kind, now_ms=0)
        return scheduler.plan_chunk(-1)

    first = picked()
    assert first == picked()
    assert len(first) == 2


def test_hitch_updates_only_kinds_that_ran() -> None:
    scheduler = ResizeScheduler(rng=random.Random(0))
    for kind in UNIT_KINDS:
        scheduler.enqueue(kind, now_ms=0)
    ran = scheduler.plan_chunk(0)
    assert ran == ["canvas_redraw"]
    scheduler.observe({"canvas_redraw": 9, "scrollbar_pack": 0})
    assert scheduler.posterior("canvas_redraw") == (1.0, 2.0)
    assert scheduler.posterior("scrollbar_pack") == (1.0, 1.0)
    scheduler.observe({"canvas_redraw": 0})
    assert scheduler.posterior("canvas_redraw") == (1.0, 2.0)


def test_kinds_in_one_chunk_learn_different_hitches() -> None:
    scheduler = ResizeScheduler(budget_ms=8, unit_cost_ms=4, rng=random.Random(0))
    scheduler.enqueue("label_rewrap", now_ms=0)
    scheduler.enqueue("scrollbar_pack", now_ms=0)
    ran = scheduler.plan_chunk(-1)
    assert set(ran) == {"label_rewrap", "scrollbar_pack"}
    scheduler.observe({"label_rewrap": 1, "scrollbar_pack": 30})
    assert scheduler.posterior("label_rewrap") == (2.0, 1.0)
    assert scheduler.posterior("scrollbar_pack") == (1.0, 2.0)


def test_a_hitchy_kind_loses_the_next_draw() -> None:
    scheduler = ResizeScheduler(rng=random.Random(1))
    for _ in range(12):
        scheduler.enqueue("scrollbar_pack", now_ms=0)
        assert scheduler.plan_chunk(-1) == ["scrollbar_pack"]
        scheduler.observe({"scrollbar_pack": 40})
    for _ in range(12):
        scheduler.enqueue("label_rewrap", now_ms=0)
        assert scheduler.plan_chunk(-1) == ["label_rewrap"]
        scheduler.observe({"label_rewrap": 1})
    scheduler.enqueue("label_rewrap", now_ms=0)
    scheduler.enqueue("scrollbar_pack", now_ms=0)
    assert scheduler.plan_chunk(-1) == ["label_rewrap"]
    assert scheduler.deadline("scrollbar_pack") is not None


def test_fractional_budget_runs_each_unit_that_sums_to_the_budget() -> None:
    scheduler = ResizeScheduler(budget_ms=0.3, unit_cost_ms=0.1, rng=random.Random(0))
    kinds = ("split_reposition", "label_rewrap", "scrollbar_pack")
    for kind in kinds:
        scheduler.enqueue(kind, now_ms=0)
    assert set(scheduler.plan_chunk(-1)) == set(kinds)


def test_optional_unit_stops_when_its_cost_does_not_fit() -> None:
    scheduler = ResizeScheduler(rng=random.Random(0))
    scheduler.enqueue("label_rewrap", now_ms=0)
    scheduler.enqueue("scrollbar_pack", now_ms=0)
    ran = scheduler.plan_chunk(-1)
    assert len(ran) == 1
    left = next(kind for kind in ("label_rewrap", "scrollbar_pack") if kind not in ran)
    assert scheduler.deadline(left) is not None


def test_due_unit_over_a_short_budget_blocks_later_units() -> None:
    scheduler = ResizeScheduler(budget_ms=0.05, unit_cost_ms=0.1)
    scheduler.enqueue("canvas_redraw", now_ms=0)
    scheduler.enqueue("scrollbar_pack", now_ms=0)
    assert scheduler.plan_chunk(0) == ["canvas_redraw"]
    assert scheduler.deadline("scrollbar_pack") is not None
    scheduler.enqueue("split_reposition", now_ms=0)
    assert scheduler.plan_chunk(100) == ["split_reposition"]
    assert scheduler.deadline("scrollbar_pack") is not None


def test_clean_hitch_increments_alpha() -> None:
    scheduler = ResizeScheduler(budget_ms=8, unit_cost_ms=4, rng=random.Random(0))
    scheduler.enqueue("split_reposition", now_ms=0)
    scheduler.enqueue("scrollbar_pack", now_ms=0)
    ran = scheduler.plan_chunk(-1)
    assert set(ran) == {"split_reposition", "scrollbar_pack"}
    scheduler.observe({kind: 8 for kind in ran})
    for kind in ran:
        assert scheduler.posterior(kind) == (2.0, 1.0)
    assert scheduler.posterior("canvas_redraw") == (1.0, 1.0)
