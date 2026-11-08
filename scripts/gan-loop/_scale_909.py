"""Stratified 60/20/20 refit of the 909-row mix. Does not write the locked blend.

398 bug rows come from the locked file. 311 hard negatives are the cap-40
one-or-two-signal scan. 200 all-zero blanks make the negative count 511,
which is the 909-row mix (398 + 511).
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan
import sandbox_rank_hard_negatives as hard

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


def counts(part):
    pos = sum(label for _, _, label in part)
    return pos, len(part) - pos


def score_part(part, slopes):
    labels = [label for _, _, label in part]
    hand = [gan.weights.score_signals(signals) for _, signals, _ in part]
    fitted = [gan.weights.dot(slopes, gan.weights._log_features(signals)) for _, signals, _ in part]
    return gan.weights.auc(hand, labels), gan.weights.auc(fitted, labels)


def one_seed(entries, seed):
    rng = random.Random(seed)
    pos = [row for row in entries if row[2] == 1]
    neg = [row for row in entries if row[2] == 0]
    pos_parts = split_class(pos, rng)
    neg_parts = split_class(neg, rng)
    train = pos_parts[0] + neg_parts[0]
    val = pos_parts[1] + neg_parts[1]
    test = pos_parts[2] + neg_parts[2]
    rng.shuffle(train)
    slopes = gan.weights.fit_logit(
        [gan.weights._log_features(signals) for _, signals, _ in train],
        [label for _, _, label in train],
        l2=1.0,
    )
    hand, fitted = score_part(test, slopes)
    return {
        "seed": seed,
        "train": counts(train),
        "val": counts(val),
        "test": counts(test),
        "test_hand": round(hand, 6),
        "test_fit": round(fitted, 6),
    }


locked = gan.load_rows(gan.MIXED)
bugs = [row for row in locked if row.get("outcome") != "empty"]
if len(bugs) != 398:
    raise SystemExit(f"expected 398 bugs, found {len(bugs)}")
hard_rows = hard.collect()
if len(hard_rows) != 311:
    raise SystemExit(f"expected 311 hard negatives, found {len(hard_rows)}")
blanks = []
for index in range(200):
    blanks.append(
        {
            "file": f"blank/{index}",
            "signals": {name: 0 for name in gan.weights.SIGNALS},
            "weighted_sum": 0,
            "scenario": "blank",
            "outcome": "empty",
        }
    )
mixed = bugs + hard_rows + blanks
entries = gan.weights.labeled_entries(mixed)
if len(entries) != 909:
    raise SystemExit(f"expected 909 labeled rows, found {len(entries)}")
spread = [one_seed(entries, seed) for seed in range(20)]
fit_scores = sorted(item["test_fit"] for item in spread)
hand_scores = sorted(item["test_hand"] for item in spread)
print(json.dumps({
    "rows": 909,
    "bugs": 398,
    "hard_negatives": 311,
    "blanks": 200,
    "splits": spread,
    "test_fit_median": round((fit_scores[9] + fit_scores[10]) / 2, 6),
    "test_hand_median": round((hand_scores[9] + hand_scores[10]) / 2, 6),
}))
