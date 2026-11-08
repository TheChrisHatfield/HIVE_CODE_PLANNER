"""Prototype: fit the six rank weights by gradient descent on the hunt log.

Does not import or edit hive_planner.bug_hunt, and does not change the prompt.
The installed later-row fit is already gradient descent on logistic loss.
This script adds the split that fit never had: files, not rows, go into
train, validation, and a test set that is scored once.

    py -3.11 scripts/sandbox_rank_gd.py
"""

from __future__ import annotations

import importlib.util
import math
import random
import sys
from pathlib import Path


def _weights():
    path = Path(__file__).with_name("sandbox_rank_weights.py")
    spec = importlib.util.spec_from_file_location("sandbox_rank_weights", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


W = _weights()


def observable(entries):
    """Drop all-zero rows. They have no signal for a ranker to learn."""
    return [entry for entry in entries if not W._is_all_zero(entry[1])]


def by_file(entries):
    groups: dict[str, list] = {}
    for entry in entries:
        groups.setdefault(entry[0].replace("\\", "/").casefold(), []).append(entry)
    return groups


def both_classes(rows) -> bool:
    labels = {label for _, _, label in rows}
    return labels == {0, 1}


def take(groups, names):
    rows = []
    for name in names:
        rows.extend(groups[name])
    return rows


def split_files(groups, seed: int):
    """60/20/20 of files. Every row of a file stays in one split."""
    names = [name for name in groups if name]
    rng = random.Random(seed)
    rng.shuffle(names)
    n = len(names)
    n_test = max(1, int(round(n * 0.20)))
    n_val = max(1, int(round(n * 0.20)))
    test_names = names[:n_test]
    val_names = names[n_test : n_test + n_val]
    train_names = names[n_test + n_val :]
    parts = {
        "train": take(groups, train_names),
        "val": take(groups, val_names),
        "test": take(groups, test_names),
    }
    if not all(both_classes(rows) for rows in parts.values()):
        return None
    if len(train_names) < 4:
        return None
    return parts


def pack(rows, logged: bool):
    xs = [W._log_features(signals) if logged else signals for _, signals, _ in rows]
    ys = [label for _, _, label in rows]
    return xs, ys


def descend(xs, ys, l2: float, steps: int = 400):
    """Full-batch gradient descent on logistic loss. One linear layer.

    The intercept is free and is not a rank weight. L2 applies to slopes only,
    same penalty shape as fit_logit.
    """
    n = len(xs)
    k = len(xs[0])
    w = [0.0] * (k + 1)
    for _ in range(steps):
        grad = [0.0] * (k + 1)
        for i in range(n):
            err = W.sigmoid(w[0] + W.dot(w[1:], xs[i])) - ys[i]
            grad[0] += err
            for j in range(k):
                grad[j + 1] += err * xs[i][j]
        for j in range(k):
            grad[j + 1] += l2 * w[j + 1]
        step = sum((g / n) * (g / n) for g in grad)
        lr = 0.8 if step < 25.0 else 0.8 / math.sqrt(step)
        for j in range(k + 1):
            w[j] -= lr * grad[j] / n
    return w


def auc_of(weights, rows, logged: bool) -> float:
    scores = []
    labels = []
    slopes = weights[1:] if len(weights) == 7 else weights
    bias = weights[0] if len(weights) == 7 else 0.0
    for _, signals, label in rows:
        features = W._log_features(signals) if logged else signals
        scores.append(bias + W.dot(slopes, features))
        labels.append(label)
    return W.auc(scores, labels)


def select(train, val, logged: bool):
    """Fit several L2 values. Keep the one with the best validation AUC."""
    xs, ys = pack(train, logged)
    best = None
    for l2 in (0.01, 0.1, 1.0, 10.0):
        weights = descend(xs, ys, l2=l2)
        score = auc_of(weights, val, logged)
        if best is None or score > best[0]:
            best = (score, l2, weights)
    return best


def main() -> int:
    entries = observable(W.labeled_entries(W.load_real(W.ROWS)))
    groups = by_file(entries)
    print(f"hunt log observable rows={len(entries)} files={len(groups)}")
    chosen = None
    for seed in range(20):
        chosen = split_files(groups, seed)
        if chosen is not None:
            print(f"file split seed={seed}")
            break
    if chosen is None:
        print("no file split kept both classes in train, validation, and test")
        return 2
    for name in ("train", "val", "test"):
        bugs, empties = W._class_counts(chosen[name])
        files = len({row[0] for row in chosen[name]})
        print(f"  {name}: files={files} rows={len(chosen[name])} bugs={bugs} empty={empties}")

    hand = auc_of(W.HAND, chosen["test"], logged=True)
    mixed_log = auc_of(W.CANDIDATE_SLOPES, chosen["test"], logged=True)
    mixed_raw = auc_of(W.CANDIDATE_SCALED, chosen["test"], logged=False)
    val_log, l2_log, w_log = select(chosen["train"], chosen["val"], logged=True)
    val_raw, l2_raw, w_raw = select(chosen["train"], chosen["val"], logged=False)
    test_log = auc_of(w_log, chosen["test"], logged=True)
    test_raw = auc_of(w_raw, chosen["test"], logged=False)
    print(f"validation auc log-features l2={l2_log:g} auc={val_log:.3f}")
    print(f"validation auc raw-features l2={l2_raw:g} auc={val_raw:.3f}")
    print("gd slopes on log1p:", " ".join(f"{v:.2f}" for v in w_log[1:]))
    print("gd slopes on raw:", " ".join(f"{v:.2f}" for v in w_raw[1:]))
    print(f"test hand raw auc={hand:.3f}")
    print(f"test mixed-file slopes on log1p auc={mixed_log:.3f}")
    print(f"test mixed-file scaled on raw auc={mixed_raw:.3f}")
    print(f"test gradient-descent log-features auc={test_log:.3f}")
    print(f"test gradient-descent raw-features auc={test_raw:.3f}")
    # One 14-empty test can look decisive. Repeat the same protocol on every seed.
    print("=== repeated file splits, test scored once per seed ===")
    columns = {"hand": [], "mixed_log": [], "mixed_raw": [], "gd_log": [], "gd_raw": []}
    for seed in range(20):
        parts = split_files(groups, seed)
        if parts is None:
            continue
        _, _, weights = select(parts["train"], parts["val"], logged=True)
        _, _, raw_weights = select(parts["train"], parts["val"], logged=False)
        columns["hand"].append(auc_of(W.HAND, parts["test"], logged=True))
        columns["mixed_log"].append(auc_of(W.CANDIDATE_SLOPES, parts["test"], logged=True))
        columns["mixed_raw"].append(auc_of(W.CANDIDATE_SCALED, parts["test"], logged=False))
        columns["gd_log"].append(auc_of(weights, parts["test"], logged=True))
        columns["gd_raw"].append(auc_of(raw_weights, parts["test"], logged=False))
    for name, values in columns.items():
        ordered = sorted(values)
        mid = ordered[len(ordered) // 2]
        print(
            f"{name}: splits={len(values)} min={ordered[0]:.3f} "
            f"median={mid:.3f} max={ordered[-1]:.3f}"
        )
    print("prompt unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
