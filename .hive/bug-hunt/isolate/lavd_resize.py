"""Resize-chunk scheduler: virtual deadlines plus Thompson sampling.

Each resize job is one unit kind. A tighter latency sensitivity gets an
earlier virtual deadline. The earliest due unit runs even when it overruns
the chunk. Further due units, then not-yet-due units in Thompson order, run
only while their cost still fits. The default budget is one unit, so a queue
of all four kinds is not cleared by the first chunk.

Hitch updates are per kind. A chunk that ran canvas and a scrollbar reports
two measurements; each posterior moves on its own.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

UNIT_KINDS: tuple[str, ...] = (
    "canvas_redraw",
    "split_reposition",
    "label_rewrap",
    "scrollbar_pack",
)

SENSITIVITY: dict[str, float] = {
    "canvas_redraw": 1.00,
    "split_reposition": 0.55,
    "label_rewrap": 0.35,
    "scrollbar_pack": 0.15,
}

DEFAULT_BUDGET_MS = 4.0
DEFAULT_UNIT_COST_MS = 4.0


@dataclass
class _Pending:
    kind: str
    deadline_ms: float
    payload: object


@dataclass
class _Posterior:
    alpha: float = 1.0
    beta: float = 1.0


class ResizeScheduler:
    """Plan which resize units run in one short chunk."""

    def __init__(
        self,
        *,
        base_window_ms: float = 48.0,
        budget_ms: float = DEFAULT_BUDGET_MS,
        unit_cost_ms: float = DEFAULT_UNIT_COST_MS,
        hitch_limit_ms: float = 8.0,
        rng: random.Random | None = None,
    ) -> None:
        self.base_window_ms = float(base_window_ms)
        self.budget_ms = float(budget_ms)
        self.unit_cost_ms = float(unit_cost_ms)
        self.hitch_limit_ms = float(hitch_limit_ms)
        self._rng = rng if rng is not None else random.Random()
        self._pending: dict[str, _Pending] = {}
        self._posterior = {kind: _Posterior() for kind in UNIT_KINDS}
        self._last_ran: list[str] | None = None
        self._last_payloads: dict[str, object] = {}

    def enqueue(self, kind: str, payload: object = None, *, now_ms: float) -> None:
        """Queue one unit. A repeat of a pending kind keeps the earlier deadline."""
        if kind not in SENSITIVITY:
            raise ValueError(f"unknown unit kind: {kind}")
        existing = self._pending.get(kind)
        if existing is not None:
            existing.payload = payload
            return
        slack = self.base_window_ms * (1.0 - SENSITIVITY[kind])
        self._pending[kind] = _Pending(kind, float(now_ms) + slack, payload)

    def cancel(self, kind: str) -> None:
        """Drop a pending kind. Unknown kinds are rejected."""
        if kind not in SENSITIVITY:
            raise ValueError(f"unknown unit kind: {kind}")
        self._pending.pop(kind, None)

    def deadline(self, kind: str) -> float | None:
        pending = self._pending.get(kind)
        if pending is None:
            return None
        return pending.deadline_ms

    def next_deadline_ms(self) -> float | None:
        """Earliest pending deadline, or None when the queue is empty."""
        if not self._pending:
            return None
        return min(unit.deadline_ms for unit in self._pending.values())

    def posterior(self, kind: str) -> tuple[float, float]:
        if kind not in self._posterior:
            raise ValueError(f"unknown unit kind: {kind}")
        post = self._posterior[kind]
        return post.alpha, post.beta

    def ran_payload(self, kind: str) -> object:
        """Payload captured for a kind the last plan actually ran."""
        return self._last_payloads[kind]

    def plan_chunk(self, now_ms: float) -> list[str]:
        """Return kinds that run now.

        The earliest due unit runs even when it overruns the budget. Any
        further due unit, and then not-yet-due units in Thompson order, run
        only while another unit still fits. Not-yet-due units stay queued
        when the default one-unit budget is already spent.
        """
        now = float(now_ms)
        if not self._pending:
            self._last_ran = []
            self._last_payloads = {}
            return []

        due = [unit for unit in self._pending.values() if unit.deadline_ms <= now]
        due.sort(key=lambda unit: (unit.deadline_ms, -SENSITIVITY[unit.kind], unit.kind))
        optional = [unit for unit in self._pending.values() if unit.deadline_ms > now]
        draws: list[tuple[float, _Pending]] = []
        for unit in sorted(optional, key=lambda item: item.kind):
            post = self._posterior[unit.kind]
            draw = self._rng.betavariate(post.alpha, post.beta)
            draws.append((draw, unit))
        draws.sort(key=lambda item: (-item[0], item[1].deadline_ms, item[1].kind))

        ran_units: list[_Pending] = []
        remaining = self.budget_ms
        if due:
            ran_units.append(due[0])
            remaining -= self.unit_cost_ms
            for unit in due[1:]:
                if not self._cost_fits(remaining):
                    break
                ran_units.append(unit)
                remaining -= self.unit_cost_ms
        if self._cost_fits(remaining):
            for _draw, unit in draws:
                if not self._cost_fits(remaining):
                    break
                ran_units.append(unit)
                remaining -= self.unit_cost_ms

        ran = [unit.kind for unit in ran_units]
        self._last_payloads = {unit.kind: unit.payload for unit in ran_units}
        for kind in ran:
            self._pending.pop(kind, None)
        self._last_ran = list(ran)
        return ran

    def _cost_fits(self, remaining: float) -> bool:
        """True when one more unit still fits in the leftover budget.

        Repeated subtraction of values such as 0.1 leaves a remainder that
        is a few ulps under the cost even though the sum still fits.
        """
        cost = self.unit_cost_ms
        if remaining >= cost:
            return True
        return math.isclose(remaining, cost, rel_tol=1e-9, abs_tol=0.0)

    def observe(self, hitches: dict[str, float]) -> None:
        """Update each kind that ran from its own hitch, then consume the plan.

        Kinds that ran but are omitted keep their posterior. Kinds that did
        not run are ignored. A second call without a new plan changes nothing.
        """
        if not self._last_ran:
            return
        if not isinstance(hitches, dict):
            raise TypeError("observe expects one hitch measurement per kind")
        for kind in self._last_ran:
            if kind not in hitches:
                continue
            post = self._posterior[kind]
            if float(hitches[kind]) <= self.hitch_limit_ms:
                post.alpha += 1.0
            else:
                post.beta += 1.0
        self._last_ran = None
