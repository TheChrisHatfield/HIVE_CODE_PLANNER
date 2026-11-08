"""Tournament for three hard-negative strategies. Does not edit the prompt or Hive logs.

Each strategy runs a three-step loop and a second three-step loop on that
output. A step is one sandbox holdout on the mixed rows, transformed by that
strategy. First 70 percent fits on log1p(commit count) with L2 1.0. The
holdout is the last 30 percent.

    py -3.11 scripts/sandbox_rank_tournament.py <step>
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

m = load_mod("sandbox_rank_weights", ROOT / "sandbox_rank_weights.py")

SIX = m.SIGNALS
SEVENTH = "guard_clause"
HAND7 = tuple(m.HAND) + (0.0,)


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def labeled(rows: list[dict]) -> list[tuple[list[float], int]]:
    entries = m.labeled_entries(rows)
    return [(signals, label) for _, signals, label in entries]


def holdout(entries: list[tuple[list[float], int]], hand: tuple[float, ...], features):
    xs = [signals for signals, _ in entries]
    ys = [label for _, label in entries]
    cut = int(len(xs) * 0.7)
    train_x, test_x = xs[:cut], xs[cut:]
    train_y, test_y = ys[:cut], ys[cut:]
    fitted = m.fit_logit([features(x) for x in train_x], train_y, l2=1.0)
    hand_auc = m.auc([hand_score(hand, x) for x in test_x], test_y)
    fit_auc = m.auc([m.dot(fitted, features(x)) for x in test_x], test_y)
    return hand_auc, fit_auc


def hand_score(hand: tuple[float, ...], signals: list[float]) -> float:
    score = m.score_signals(signals[:6], hand[:6])
    extra = range(6, len(signals))
    return score + sum(float(hand[index]) * float(signals[index]) for index in extra)


def log_features(x: list[float]) -> list[float]:
    return [m.fix_commit_feature(x[0]), *x[1:]]


def log_features7(x: list[float]) -> list[float]:
    return [m.fix_commit_feature(x[0]), *x[1:6], x[6]]


def tighten(signals: list[float]) -> list[float]:
    values = list(signals)
    for index, name in enumerate(SIX):
        if name != "recent_fix_commits" and values[index] and signals[0]:
            values[index] = 0
    return values


def is_tight(signals: list[float]) -> bool:
    return all(not signals[index] for index, name in enumerate(SIX) if name != "recent_fix_commits" and signals[index]) or not signals[0]


def guard_signal(row: dict) -> float:
    scenario = str(row.get("scenario", "")).casefold()
    if "guarded" in scenario or "guard" in scenario:
        return 1.0
    return 0.0


def with_seventh(row: dict) -> list[float]:
    values = list(m.coerce_signals(row.get("signals")))
    return values + [guard_signal(row)]


def match_partial(entries: list[tuple[list[float], int]], rng_seed: int) -> list[tuple[list[float], int]]:
    import random

    bugs = [(signals, label) for signals, label in entries if label == 1]
    negs = [(signals, label) for signals, label in entries if label == 0]
    patterns = Counter(tuple(i for i, v in enumerate(signals) if v) for signals, label in negs if any(signals))
    nonzero_negs = sum(patterns.values())
    if not nonzero_negs:
        return entries
    rng = random.Random(rng_seed)
    chosen = list(negs)
    for pattern, count in patterns.items():
        need = count
        pool = [(signals, label) for signals, label in bugs if any(signals)]
        rng.shuffle(pool)
        for signals, label in pool:
            if need <= 0:
                break
            masked = [v if i in pattern else 0 for i, v in enumerate(signals)]
            chosen.append((masked, label))
            need -= 1
    return chosen


def interleave_entries(entries: list[tuple[list[float], int]]) -> list[tuple[list[float], int]]:
    bugs = [item for item in entries if item[1] == 1]
    negs = [item for item in entries if item[1] == 0]
    mixed = []
    b = n = 0
    while b < len(bugs) or n < len(negs):
        if b < len(bugs) and (n >= len(negs) or b * len(negs) <= n * len(bugs)):
            mixed.append(bugs[b])
            b += 1
        else:
            mixed.append(negs[n])
            n += 1
    return mixed


def main() -> int:
    step = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    loop = (step - 1) // 3
    slot = (step - 1) % 3
    strategy = ["tighten", "match-positives", "seventh-signal"][slot]
    rows = load_rows(ROOT / "sandbox_rank_detect_mixed.jsonl")
    entries = labeled(rows)

    if strategy == "tighten":
        transformed = [(tighten(signals), label) for signals, label in entries]
        removed = sum(
            1 for signals, _ in entries
            if any(signals[i] for i, name in enumerate(SIX) if name != "recent_fix_commits")
            and signals[0]
        )
        hand, fit = holdout(transformed, m.HAND, log_features)
        print(f"strategy={strategy} slot={slot} removed_flags={removed}")
    elif strategy == "match-positives":
        masked = match_partial(entries, rng_seed=slot)
        ordered = interleave_entries(masked)
        hand, fit = holdout(ordered, m.HAND, log_features)
        print(f"strategy={strategy} slot={slot} rows={len(masked)} bugs={sum(1 for _, y in masked if y)}")
    else:
        transformed7 = [(with_seventh(row), 1 if str(row.get("outcome")) in m.BUG else 0) for row in rows if str(row.get("outcome")) in m.BUG or str(row.get("outcome")) == "empty"]
        hand, fit = holdout(transformed7, HAND7, log_features7)
        guards = sum(1 for signals, label in transformed7 if signals[6] and label == 0)
        print(f"strategy={strategy} slot={slot} guarded_negatives={guards}")

    print(f"loop={loop} step={step} strategy={strategy}")
    print(f"hand_auc={hand:.3f}")
    print(f"fit_auc={fit:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
