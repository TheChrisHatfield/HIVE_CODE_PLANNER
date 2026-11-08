"""Stratified train/validation/test fit on the locked 603-row blend.

Reads the mixed file. Does not write it. log1p on fix-commit counts, L2 1.0,
empties included. The fit uses only the training slice.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan

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
    parts = []
    for bucket in (split_class(pos, rng), split_class(neg, rng)):
        parts.append(bucket)
    train = parts[0][0] + parts[1][0]
    val = parts[0][1] + parts[1][1]
    test = parts[0][2] + parts[1][2]
    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    slopes = gan.weights.fit_logit(
        [gan.weights._log_features(signals) for _, signals, _ in train],
        [label for _, _, label in train],
        l2=1.0,
    )
    return {
        "seed": seed,
        "train": counts(train),
        "val": counts(val),
        "test": counts(test),
        "slopes": [round(value, 4) for value in slopes],
        "val_hand": round(score_part(val, slopes)[0], 6),
        "val_fit": round(score_part(val, slopes)[1], 6),
        "test_hand": round(score_part(test, slopes)[0], 6),
        "test_fit": round(score_part(test, slopes)[1], 6),
    }


rows = gan.load_rows(gan.MIXED)
gan_left = sum(1 for row in rows if str(row.get("file", "")).startswith("gan/"))
entries = gan.weights.labeled_entries(rows)
bugs = sum(label for _, _, label in entries)
if len(entries) != 603 or bugs != 398 or gan_left != 0:
    raise SystemExit(f"blend is not the locked 603: {len(entries)} bugs={bugs} gan={gan_left}")

primary = one_seed(entries, 0)
spread = [one_seed(entries, seed) for seed in range(20)]
fit_scores = sorted(item["test_fit"] for item in spread)
hand_scores = sorted(item["test_hand"] for item in spread)
print(json.dumps({
    "rows": len(entries),
    "bugs": bugs,
    "empties": len(entries) - bugs,
    "split": "stratified 60/20/20",
    "primary": primary,
    "seeds": 20,
    "test_fit_median": round((fit_scores[9] + fit_scores[10]) / 2, 6),
    "test_fit_min": fit_scores[0],
    "test_fit_max": fit_scores[-1],
    "test_hand_median": round((hand_scores[9] + hand_scores[10]) / 2, 6),
    "test_hand_min": hand_scores[0],
    "test_hand_max": hand_scores[-1],
}))
