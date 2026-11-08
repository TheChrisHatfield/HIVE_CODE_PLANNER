"""Score generator near-misses and refit the sandbox holdout.

The discriminator is the detector: findings_for, python_signals, and the
fitted slopes from the current mixed file (first 70 percent, log1p on
fix-commit counts, L2 1.0). Does not read or write the Hive rank logs
or the installed prompt.

    py -3.11 scripts/sandbox_rank_gan.py score scripts/gan-loop/round1-proposals.json
    py -3.11 scripts/sandbox_rank_gan.py auc --extra scripts/gan-loop/accepted.jsonl
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
MIXED = SCRIPTS / "sandbox_rank_detect_mixed.jsonl"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


detect = _load("sandbox_rank_detect", SCRIPTS / "sandbox_rank_detect.py")
weights = _load("sandbox_rank_weights", SCRIPTS / "sandbox_rank_weights.py")


def lit_names(signals: list[float]) -> list[str]:
    return [name for name, value in zip(weights.SIGNALS, signals) if value]


def score_source(name: str, source: str, slopes: list[float]) -> dict:
    path = Path(name)
    findings = detect.findings_for(path, source)
    thin = 0 if detect._is_test_rel(name) else 1
    signals = detect.python_signals(source, thin)
    values = [float(signals.as_dict()[key]) for key in weights.SIGNALS]
    names = lit_names(values)
    features = weights._log_features(values)
    fitted = weights.dot(slopes, features)
    hand = weights.score_signals(values)
    defect = findings is None or len(findings) > 0
    band = 1 <= len(names) <= 2
    accepted = (not defect) and band
    return {
        "name": name,
        "signals": signals.as_dict(),
        "lit": names,
        "findings": [] if not findings else [item.text for item in findings],
        "hand": round(hand, 4),
        "fitted": round(fitted, 4),
        "accepted": accepted,
        "reason": (
            "accepted"
            if accepted
            else "defect"
            if defect
            else "signal-count"
        ),
    }


def holdout(rows: list[dict]) -> dict:
    entries = weights.labeled_entries(rows)
    cut = int(len(entries) * 0.7)
    train = entries[:cut]
    test = entries[cut:]
    labels = [label for _, _, label in train]
    slopes = weights.fit_logit(
        [weights._log_features(signals) for _, signals, _ in train],
        labels,
        l2=1.0,
    )
    hand_scores = [weights.score_signals(signals) for _, signals, label in test]
    fit_scores = [
        weights.dot(slopes, weights._log_features(signals)) for _, signals, _ in test
    ]
    test_labels = [label for _, _, label in test]
    pos = sum(test_labels)
    return {
        "rows": len(entries),
        "train": cut,
        "test_pos": pos,
        "test_neg": len(test_labels) - pos,
        "hand_auc": round(weights.auc(hand_scores, test_labels), 6),
        "fit_auc": round(weights.auc(fit_scores, test_labels), 6),
        "slopes": [round(value, 4) for value in slopes],
        "pos_median": _median([s for s, y in zip(fit_scores, test_labels) if y == 1]),
        "neg_median": _median([s for s, y in zip(fit_scores, test_labels) if y == 0]),
    }


def _median(values: list[float]) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 4)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 4)


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def accepted_to_rows(scored: list[dict]) -> list[dict]:
    rows = []
    for item in scored:
        if not item["accepted"]:
            continue
        signals = item["signals"]
        rows.append(
            {
                "file": f"gan/{item['name']}",
                "signals": signals,
                "weighted_sum": weights.score_signals([signals[k] for k in weights.SIGNALS]),
                "scenario": "hard-negative:gan:" + ",".join(item["lit"]),
                "outcome": "empty",
            }
        )
    return rows


def main() -> None:
    mode = sys.argv[1]
    if mode == "baseline":
        print(json.dumps(holdout(load_rows(MIXED))))
        return
    if mode == "score":
        proposals = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        base = holdout(load_rows(MIXED))
        extra_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
        prior = []
        if extra_path is not None and extra_path.exists():
            prior = load_rows(extra_path)
        mixed_now = load_rows(MIXED)
        current = (
            detect.interleave_rows(
                [row for row in mixed_now if row.get("outcome") != "empty"],
                [row for row in mixed_now if row.get("outcome") == "empty"] + prior,
            )
            if prior
            else mixed_now
        )
        # Score with the slopes of the file as it stands before this batch.
        standing = holdout(current)
        slopes = standing["slopes"]
        scored = [score_source(item["name"], item["source"], slopes) for item in proposals]
        median_pos = standing["pos_median"]
        for item in scored:
            item["fools"] = bool(item["accepted"] and item["fitted"] >= median_pos)
        new_rows = accepted_to_rows(scored)
        mixed_rows = load_rows(MIXED)
        bugs = [row for row in mixed_rows if row.get("outcome") != "empty"]
        negs = [row for row in mixed_rows if row.get("outcome") == "empty"] + prior + new_rows
        blended = detect.interleave_rows(bugs, negs)
        after = holdout(blended)
        print(
            json.dumps(
                {
                    "before": standing,
                    "baseline": base,
                    "scored": scored,
                    "accepted": sum(1 for item in scored if item["accepted"]),
                    "fooled": sum(1 for item in scored if item["fools"]),
                    "after": after,
                    "new_rows": new_rows,
                }
            )
        )
        return
    raise SystemExit(f"unknown mode {mode}")


if __name__ == "__main__":
    main()
