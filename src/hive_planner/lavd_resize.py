"""Resize-chunk scheduler: virtual deadlines plus Thompson sampling.

Each resize job is one unit kind. A tighter latency sensitivity gets an
earlier virtual deadline. Due units run first. Optional units fill the
rest of the chunk in Thompson order, using hitch observations as the reward.
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
        budget_ms: float = 16.0,
        unit_cost_ms: float = 4.0,
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

    def deadline(self, kind: str) -> float | None:
        pending = self._pending.get(kind)
        if pending is None:
            return None
        return pending.deadline_ms

    def posterior(self, kind: str) -> tuple[float, float]:
        if kind not in self._posterior:
            raise ValueError(f"unknown unit kind: {kind}")
        post = self._posterior[kind]
        return post.alpha, post.beta

    def plan_chunk(self, now_ms: float) -> list[str]:
        """Return kinds that run now, due units first, then Thompson order."""
        now = float(now_ms)
        if not self._pending:
            self._last_ran = []
            return []

        due = [unit for unit in self._pending.values() if unit.deadline_ms <= now]
        due.sort(key=lambda unit: (unit.deadline_ms, unit.kind))
        optional = [unit for unit in self._pending.values() if unit.deadline_ms > now]
        draws: list[tuple[float, _Pending]] = []
        for unit in sorted(optional, key=lambda item: item.kind):
            post = self._posterior[unit.kind]
            draw = self._rng.betavariate(post.alpha, post.beta)
            draws.append((draw, unit))
        draws.sort(key=lambda item: (-item[0], item[1].kind))

        ran: list[str] = [unit.kind for unit in due]
        remaining = self.budget_ms - self.unit_cost_ms * len(due)
        if self._cost_fits(remaining):
            for _draw, unit in draws:
                if not self._cost_fits(remaining):
                    break
                ran.append(unit.kind)
                remaining -= self.unit_cost_ms

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

    def observe(self, hitch_ms: float) -> None:
        """Update posteriors for the kinds the last plan actually ran."""
        if not self._last_ran:
            return
        clean = float(hitch_ms) <= self.hitch_limit_ms
        for kind in self._last_ran:
            post = self._posterior[kind]
            if clean:
                post.alpha += 1.0
            else:
                post.beta += 1.0
        self._last_ran = None
