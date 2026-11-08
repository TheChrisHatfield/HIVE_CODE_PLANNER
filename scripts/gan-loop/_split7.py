"""Twenty stratified splits with the six signals plus flagged_line_fix.

Reads the locked blend. Does not write it. log1p on both commit counts
(file-level fix commits and the new line-level count). L2 1.0.
The hand score is score_signals on the installed slopes.
"""
from __future__ import annotations

import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan
import sandbox_rank_detect as det
from _flagged_line_fix import _ROOTS, _git_commits, flagged_line_fix_count, row_lines

TRAIN, VAL = 0.60, 0.20


def split_class(items, rng):
    pool = list(items)
    rng.shuffle(pool)
    n = len(pool)
    n_train = int(round(n * TRAIN))
    n_val = int(round(n * VAL))
    if n_train + n_val >= n:
        n_val = max(1, n - n_train - 1)
    return pool[:n_train], pool[n_train : n_train + n_val], pool[n_train + n_val :]


def features(signals: list[float], seventh: float) -> list[float]:
    squash = gan.weights.fix_commit_feature
    return [squash(signals[0]), *signals[1:], squash(seventh)]


def counts_for(rows: list[dict]) -> list[int]:
    line_sets: list[set[int]] = []
    groups: set[tuple[str, str]] = set()
    for row in rows:
        file_name = str(row.get("file", ""))
        repo_name, _, rel = file_name.partition("/")
        root = _ROOTS.get(repo_name)
        source = det._read(root / rel) if root is not None and rel else None
        lines = row_lines(row, source)
        line_sets.append(lines)
        if lines and root is not None and rel:
            groups.add((repo_name, rel))

    def load(item):
        repo_name, rel = item
        return item, _git_commits(_ROOTS[repo_name], rel)

    history: dict[tuple[str, str], list] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, value in pool.map(load, groups):
            history[key] = value
    counts = []
    for row, lines in zip(rows, line_sets):
        repo_name, _, rel = str(row.get("file", "")).partition("/")
        counts.append(flagged_line_fix_count(history.get((repo_name, rel), []), lines))
    return counts


def one_seed(entries, seed):
    rng = random.Random(seed)
    pos = [row for row in entries if row[3] == 1]
    neg = [row for row in entries if row[3] == 0]
    pos_parts = split_class(pos, rng)
    neg_parts = split_class(neg, rng)
    train = pos_parts[0] + neg_parts[0]
    val = pos_parts[1] + neg_parts[1]
    test = pos_parts[2] + neg_parts[2]
    rng.shuffle(train)
    slopes = gan.weights.fit_logit(
        [features(signals, seventh) for _, signals, seventh, _ in train],
        [label for _, _, _, label in train],
        l2=1.0,
    )
    labels = [label for _, _, _, label in test]
    hand = [gan.weights.score_signals(signals) for _, signals, _, _ in test]
    fitted = [gan.weights.dot(slopes, features(signals, seventh)) for _, signals, seventh, _ in test]
    pos = sum(labels)
    return {
        "seed": seed,
        "test_pos": pos,
        "test_neg": len(labels) - pos,
        "test_hand": round(gan.weights.auc(hand, labels), 6),
        "test_fit": round(gan.weights.auc(fitted, labels), 6),
        "slopes": [round(value, 4) for value in slopes],
    }


def main() -> None:
    rows = gan.load_rows(gan.MIXED)
    if len(rows) != 603 or any(str(row.get("file", "")).startswith("gan/") for row in rows):
        raise SystemExit("blend is not the locked 603")
    seventh = counts_for(rows)
    entries = []
    for row, extra in zip(rows, seventh):
        outcome = row.get("outcome")
        label = 1 if outcome != "empty" else 0
        signals = gan.weights.coerce_signals(row.get("signals"))
        entries.append((row.get("file"), signals, float(extra), label))
    if sum(1 for value in seventh if value) != 94:
        raise SystemExit(f"expected 94 lit rows, found {sum(1 for value in seventh if value)}")
    spread = [one_seed(entries, seed) for seed in range(20)]
    fit_scores = sorted(item["test_fit"] for item in spread)
    hand_scores = sorted(item["test_hand"] for item in spread)
    print(json.dumps({
        "lit": 94,
        "splits": spread,
        "test_fit_median": round((fit_scores[9] + fit_scores[10]) / 2, 6),
        "test_hand_median": round((hand_scores[9] + hand_scores[10]) / 2, 6),
        "seed0_slopes": spread[0]["slopes"],
    }))


if __name__ == "__main__":
    main()
