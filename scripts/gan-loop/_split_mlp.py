"""Twenty stratified splits with a small two-layer net.

Sklearn and XGBoost are not installed. The fallback is one hidden ReLU
layer of 8 units, trained on the train slice only. The validation slice
picks the epoch. The test slice is scored once. Reads the locked blend
and does not write it. log1p on commit counts. The hand score is
score_signals on the installed slopes.
"""
from __future__ import annotations

import copy
import json
import math
import random
import sys
from pathlib import Path

import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan
from _split7 import counts_for, split_class

EPOCHS = 300
HIDDEN = 8


class Net(nn.Module):
    def __init__(self, width: int) -> None:
        super().__init__()
        self.fc1 = nn.Linear(width, HIDDEN)
        self.fc2 = nn.Linear(HIDDEN, 1)

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return self.fc2(torch.relu(self.fc1(batch))).squeeze(-1)


def six_features(signals: list[float]) -> list[float]:
    return [gan.weights.fix_commit_feature(signals[0]), *signals[1:]]


def seven_features(signals: list[float], seventh: float) -> list[float]:
    squash = gan.weights.fix_commit_feature
    return [squash(signals[0]), *signals[1:], squash(seventh)]


def standardize(train: list[list[float]], others: list[list[list[float]]]):
    width = len(train[0])
    means = []
    scales = []
    for col in range(width):
        values = [row[col] for row in train]
        mean = sum(values) / len(values)
        var = sum((value - mean) ** 2 for value in values) / len(values)
        scale = math.sqrt(var)
        means.append(mean)
        scales.append(scale if scale > 1e-8 else 1.0)

    def apply(rows: list[list[float]]) -> list[list[float]]:
        return [
            [(row[col] - means[col]) / scales[col] for col in range(width)]
            for row in rows
        ]

    return apply(train), [apply(rows) for rows in others]


def fit_scores(train_x, train_y, val_x, val_y, test_x, seed: int) -> list[float]:
    torch.manual_seed(seed)
    model = Net(len(train_x[0]))
    opt = torch.optim.Adam(model.parameters(), lr=0.05, weight_decay=1e-2)
    loss_fn = nn.BCEWithLogitsLoss()
    xtr = torch.tensor(train_x, dtype=torch.float32)
    ytr = torch.tensor(train_y, dtype=torch.float32)
    xva = torch.tensor(val_x, dtype=torch.float32)
    xte = torch.tensor(test_x, dtype=torch.float32)
    best = -1.0
    state = copy.deepcopy(model.state_dict())
    for _ in range(EPOCHS):
        model.train()
        opt.zero_grad()
        loss = loss_fn(model(xtr), ytr)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            val_scores = model(xva).tolist()
        val_auc = gan.weights.auc(val_scores, val_y)
        if val_auc > best:
            best = val_auc
            state = copy.deepcopy(model.state_dict())
    model.load_state_dict(state)
    model.eval()
    with torch.no_grad():
        return model(xte).tolist()


def one_seed(entries, seed: int, use_seventh: bool) -> dict:
    rng = random.Random(seed)
    pos = [row for row in entries if row[3] == 1]
    neg = [row for row in entries if row[3] == 0]
    pos_parts = split_class(pos, rng)
    neg_parts = split_class(neg, rng)
    train = pos_parts[0] + neg_parts[0]
    val = pos_parts[1] + neg_parts[1]
    test = pos_parts[2] + neg_parts[2]
    rng.shuffle(train)

    def feats(row):
        if use_seventh:
            return seven_features(row[1], row[2])
        return six_features(row[1])

    train_x, (val_x, test_x) = standardize(
        [feats(row) for row in train],
        [[feats(row) for row in val], [feats(row) for row in test]],
    )
    scores = fit_scores(
        train_x,
        [row[3] for row in train],
        val_x,
        [row[3] for row in val],
        test_x,
        seed,
    )
    labels = [row[3] for row in test]
    hand = [gan.weights.score_signals(row[1]) for row in test]
    pos_n = sum(labels)
    return {
        "seed": seed,
        "test_pos": pos_n,
        "test_neg": len(labels) - pos_n,
        "test_hand": round(gan.weights.auc(hand, labels), 6),
        "test_fit": round(gan.weights.auc(scores, labels), 6),
    }


def median(values: list[float]) -> float:
    ordered = sorted(values)
    return round((ordered[9] + ordered[10]) / 2, 6)


def main() -> None:
    torch.set_num_threads(4)
    rows = gan.load_rows(gan.MIXED)
    if len(rows) != 603 or any(str(row.get("file", "")).startswith("gan/") for row in rows):
        raise SystemExit("blend is not the locked 603")
    seventh = counts_for(rows)
    if sum(1 for value in seventh if value) != 94:
        raise SystemExit(f"expected 94 lit rows, found {sum(1 for value in seventh if value)}")
    entries = []
    for row, extra in zip(rows, seventh):
        entries.append(
            (
                row.get("file"),
                gan.weights.coerce_signals(row.get("signals")),
                float(extra),
                0 if row.get("outcome") == "empty" else 1,
            )
        )
    report = {"model": "relu-8", "epochs": EPOCHS, "features": {}}
    for name, use_seventh in (("six", False), ("seven", True)):
        spread = [one_seed(entries, seed, use_seventh) for seed in range(20)]
        report["features"][name] = {
            "splits": spread,
            "test_fit_median": median([item["test_fit"] for item in spread]),
            "test_hand_median": median([item["test_hand"] for item in spread]),
        }
    print(json.dumps(report))


if __name__ == "__main__":
    main()
