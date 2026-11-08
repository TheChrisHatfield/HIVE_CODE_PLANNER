"""Sandbox: are the bug-hunt hand weights good ranks, and how many rows
does a refit need before it recovers a known weight vector?

Scores with hive_planner.bug_hunt.score_signals. Does not edit that module. Run:

    py -3.11 scripts/sandbox_rank_weights.py
    py -3.11 scripts/sandbox_rank_weights.py --rows scripts/sandbox_rank_detect_mixed.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

from hive_planner.bug_hunt import INITIAL_SLOPES, fix_commit_feature, score_signals

SIGNALS = (
    "recent_fix_commits",
    "thin_test",
    "wiring_hop",
    "dead_setting",
    "reverted",
    "split_stores",
)
HAND = INITIAL_SLOPES
# Printed later-row refit on the mixed detector file. Not installed in the prompt
# until validate_prompt_swap reproduces it and an unused-file holdout still supports it.
CANDIDATE_SLOPES = (1.42, 5.17, 2.02, 0.05, 0.00, 0.00)
CANDIDATE_SCALED = (4.1, 14.92, 5.83, 0.15, 0.0, 0.0)
# Known logit weights for the synthetic world. Different from HAND on purpose.
TRUTH = (1.0, 6.0, 2.0, 5.0, 3.0, 4.0)
TRUTH_BIAS = -2.2
COUNTS = (10, 20, 30, 50, 100, 200, 400, 800)
TRIALS = 40
# Unit-length cosine. 0.95 is "same direction" for a 6-vector.
COSINE_TOL = 0.95
HIT_RATE = 0.80
ROWS = Path(__file__).resolve().parents[1] / ".hive" / "bug-hunt" / "rank-rows.jsonl"
BUG = {"committed", "review-failed"}


def sigmoid(z: float) -> float:
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)


def dot(w: tuple[float, ...] | list[float], x: list[float]) -> float:
    return sum(a * b for a, b in zip(w, x))


def cosine(a: list[float], b: tuple[float, ...]) -> float:
    na = math.sqrt(sum(v * v for v in a))
    nb = math.sqrt(sum(v * v for v in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def auc(scores: list[float], labels: list[int]) -> float:
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return float("nan")
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def top_capture(scores: list[float], labels: list[int], frac: float = 0.2) -> float:
    """Share of real bugs that land in the top fraction of scores."""
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    k = max(1, int(round(len(scores) * frac)))
    bugs = sum(labels)
    if bugs == 0:
        return float("nan")
    return sum(labels[i] for i in order[:k]) / bugs


def fit_logit(xs: list[list[float]], ys: list[int], l2: float = 1e-3) -> list[float]:
    """Slopes only. Light L2 keeps n=10 from exploding. Intercept is free."""
    n = len(xs)
    k = len(xs[0])
    w = [0.0] * (k + 1)
    for _ in range(200):
        grad = [0.0] * (k + 1)
        for i in range(n):
            z = w[0] + dot(w[1:], xs[i])
            err = sigmoid(z) - ys[i]
            grad[0] += err
            for j in range(k):
                grad[j + 1] += err * xs[i][j]
        for j in range(k):
            grad[j + 1] += l2 * w[j + 1]
        step = 0.0
        for g in grad:
            step += (g / n) * (g / n)
        lr = 0.8 if step < 25.0 else 0.8 / math.sqrt(step)
        for j in range(k + 1):
            w[j] -= lr * grad[j] / n
    return w[1:]


def scale_to_hand_sum(w: list[float]) -> tuple[float, ...]:
    """Positive parts renormalized to sum to 25, the hand-weight total."""
    pos = [max(0.0, v) for v in w]
    total = sum(pos)
    if total == 0.0:
        return tuple(0.0 for _ in pos)
    return tuple(round(25.0 * v / total, 2) for v in pos)


def synthesize(rng: random.Random, n: int) -> tuple[list[list[float]], list[int]]:
    """Schema-shaped rows. recent_fix is a small count so the other five
    signals can still move the logit. Outcomes follow TRUTH."""
    xs: list[list[float]] = []
    ys: list[int] = []
    rates = (None, 0.35, 0.30, 0.20, 0.15, 0.25)
    while len(xs) < n:
        x = [float(rng.randint(0, 8))]
        for p in rates[1:]:
            x.append(1.0 if rng.random() < p else 0.0)
        bug = rng.random() < sigmoid(TRUTH_BIAS + dot(TRUTH, x))
        if bug:
            outcome_bug = True
        else:
            if rng.random() < 0.12:
                continue  # skipped: logged in real life, dropped from the fit
            outcome_bug = False
        xs.append(x)
        ys.append(1 if outcome_bug else 0)
    return xs, ys


def sensitivity() -> int | None:
    print("=== synthetic recovery (known truth) ===")
    print("truth", " ".join(f"{s}={v:g}" for s, v in zip(SIGNALS, TRUTH)))
    print(f"tolerance cosine>={COSINE_TOL} on {HIT_RATE:.0%} of {TRIALS} trials")
    converged: int | None = None
    for n in COUNTS:
        cosines: list[float] = []
        for t in range(TRIALS):
            rng = random.Random(10_000 + n * 100 + t)
            xs, ys = synthesize(rng, n)
            if len(set(ys)) < 2:
                cosines.append(0.0)
                continue
            cosines.append(cosine(fit_logit(xs, ys), TRUTH))
        cosines.sort()
        median = cosines[len(cosines) // 2]
        hits = sum(1 for c in cosines if c >= COSINE_TOL) / len(cosines)
        mark = ""
        if converged is None and hits >= HIT_RATE:
            converged = n
            mark = "  <-- converges"
        print(f"n={n:4d}  median_cosine={median:.3f}  within_tol={hits:.0%}{mark}")
    if converged is None:
        print(f"recommended weights have not converged by {COUNTS[-1]} rows")
    else:
        print(f"row threshold: {converged}")
    return converged


# Name tags used in a few early rows, mapped onto the six numeric signals.
_TAG_TO_SIGNAL = {
    "prior-bug-fixes": "recent_fix_commits",
    "shared-value-readers": "split_stores",
    "two-readers": "split_stores",
    "two-readers-disagree": "split_stores",
    "wiring-hop-check": "wiring_hop",
    "dead-button-check": "dead_setting",
}


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def coerce_signals(sig: object) -> list[float]:
    """Six numbers. Dicts use the signal keys. Lists use numeric items, then tag names."""
    out = [0.0] * len(SIGNALS)
    index = {name: i for i, name in enumerate(SIGNALS)}
    if isinstance(sig, dict):
        for name, i in index.items():
            number = _as_float(sig.get(name, 0))
            out[i] = 0.0 if number is None else number
        return out
    if isinstance(sig, list):
        numbers = [_as_float(item) for item in sig]
        numeric = [n for n in numbers if n is not None]
        if len(numeric) == len(SIGNALS):
            return numeric
        for item in sig:
            if not isinstance(item, str):
                continue
            slot = _TAG_TO_SIGNAL.get(item.strip())
            if slot is not None:
                out[index[slot]] += 1.0
        return out
    return out


def load_real(path: Path) -> list[dict]:
    rows = []
    text = path.read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{number}: row is not an object")
        rows.append(row)
    return rows


def real_report(path: Path | None = None) -> None:
    path = ROWS if path is None else path
    rows = load_real(path)
    labeled = []
    skipped = 0
    coerced = 0
    malformed = 0
    ignored = 0
    for row in rows:
        outcome = row.get("outcome")
        if not isinstance(outcome, str):
            malformed += 1
            continue
        sig = row.get("signals")
        if isinstance(sig, list):
            coerced += 1
        if outcome == "skipped":
            skipped += 1
            continue
        if outcome not in BUG and outcome != "empty":
            ignored += 1
            continue
        labeled.append((coerce_signals(sig), 1 if outcome in BUG else 0))
    xs = [x for x, _ in labeled]
    ys = [y for _, y in labeled]
    label = "real rank-rows.jsonl" if path.resolve() == ROWS.resolve() else str(path)
    print(f"=== {label} ===")
    if malformed:
        print(f"malformed={malformed}")
    if ignored:
        print(f"ignored={ignored}")
    if len(xs) < 2 or len(set(ys)) < 2:
        print(
            f"rows={len(rows)} labeled={len(labeled)} bugs={sum(ys)} "
            f"empty={len(ys) - sum(ys)} skipped={skipped} coerced_lists={coerced}"
        )
        print("not enough labeled rows of both classes to score")
        return
    print(
        f"rows={len(rows)} labeled={len(labeled)} bugs={sum(ys)} "
        f"empty={len(ys) - sum(ys)} skipped={skipped} coerced_lists={coerced}"
    )
    for j, name in enumerate(SIGNALS):
        col = [x[j] for x in xs]
        nz = sum(1 for v in col if v)
        print(f"  {name}: nonzero={nz} max={max(col):.0f} alone_auc={auc(col, ys):.3f}")
    hand_scores = [score_signals(x) for x in xs]
    print(f"hand weights {HAND}")
    print(f"hand auc={auc(hand_scores, ys):.3f}  top20_bug_capture={top_capture(hand_scores, ys):.3f}")
    print("one-at-a-time perturbations (auc):")
    for j, name in enumerate(SIGNALS):
        for factor in (0.5, 2.0):
            w = list(HAND)
            w[j] *= factor
            delta = auc([score_signals(x, w) for x in xs], ys) - auc(hand_scores, ys)
            print(f"  {name} x{factor:<3}  delta_auc={delta:+.3f}")
    # Temporal holdout: the file is append-only.
    # Append order is the hunt's clock. A file that stacks every empty row at
    # the end will not split that way into two classes, and the refit is skipped.
    cut = int(len(xs) * 0.7)
    train_x, test_x = xs[:cut], xs[cut:]
    train_y, test_y = ys[:cut], ys[cut:]
    if not train_x or not test_x or len(set(train_y)) < 2 or len(set(test_y)) < 2:
        print("holdout split does not contain both classes; refit comparison skipped")
        return
    # Recent-fix counts are huge next to 0/1 flags. Refit on log1p(count)
    # so a recommended vector is on a comparable scale to the flags.
    def squash(x: list[float]) -> list[float]:
        return [fix_commit_feature(x[0]), *x[1:]]

    fitted_s = fit_logit([squash(x) for x in train_x], train_y, l2=1.0)
    hand_test = auc([score_signals(x) for x in test_x], test_y)
    fit_test = auc([dot(fitted_s, squash(x)) for x in test_x], test_y)
    recommended = scale_to_hand_sum(fitted_s)
    print(f"holdout hand auc={hand_test:.3f}  refit auc={fit_test:.3f}")
    print("refit slopes (log1p commits, then five flags):", " ".join(f"{v:.2f}" for v in fitted_s))
    print("rescaled positive weights summing to 25:", recommended)
    if fit_test + 0.02 < hand_test or math.isnan(fit_test):
        print("real rows do not support replacing the hand weights")
    elif fit_test > hand_test + 0.02:
        print("real holdout prefers the refit vector above")
    else:
        print("real holdout is a tie; keep the hand weights")


def _log_features(x: list[float]) -> list[float]:
    """Same squash the later-row refit used: log1p of the fix-commit count."""
    return [fix_commit_feature(x[0]), *x[1:]]


def _is_all_zero(x: list[float]) -> bool:
    return all(value == 0.0 for value in x)


def labeled_entries(rows: list[dict]) -> list[tuple[str, list[float], int]]:
    """(file, six signals, bug bit) in file order. Skipped and unknown outcomes drop out."""
    entries: list[tuple[str, list[float], int]] = []
    for row in rows:
        outcome = row.get("outcome")
        if not isinstance(outcome, str):
            continue
        if outcome == "skipped" or (outcome not in BUG and outcome != "empty"):
            continue
        file_name = row.get("file")
        file_key = file_name if isinstance(file_name, str) else ""
        entries.append((file_key, coerce_signals(row.get("signals")), 1 if outcome in BUG else 0))
    return entries


def _near(found: tuple[float, ...] | list[float], expected: tuple[float, ...], tol: float) -> bool:
    if len(found) != len(expected):
        return False
    return all(abs(float(left) - right) <= tol for left, right in zip(found, expected))


def reproduce_later_row(
    entries: list[tuple[str, list[float], int]],
) -> tuple[int, list[float], tuple[float, ...]] | None:
    """Refit the first 70 percent of rows, including all-zero rows, on log1p(commits).

    This is the procedure that printed the candidate slopes. It is not the
    unused-file check.
    """
    if len(entries) < 2:
        return None
    cut = int(len(entries) * 0.7)
    train = entries[:cut]
    labels = [label for _, _, label in train]
    if cut < 2 or cut >= len(entries) or len(set(labels)) < 2:
        return None
    slopes = fit_logit([_log_features(signals) for _, signals, _ in train], labels, l2=1.0)
    return cut, slopes, scale_to_hand_sum(slopes)


def _file_keys(file_name: str) -> set[str]:
    """Full path plus the path with the repo folder removed, so copies still match."""
    text = file_name.replace("\\", "/").strip().casefold().lstrip("./")
    if not text:
        return set()
    keys = {text}
    parts = text.split("/")
    if len(parts) > 1:
        keys.add("/".join(parts[1:]))
    return keys


def rows_outside_fit(
    entries: list[tuple[str, list[float], int]],
    used_names: set[str],
) -> tuple[list[tuple[str, list[float], int]], int, int]:
    """Nonzero rows whose file was not in the fit. All-zero rows stay out of the score."""
    used: set[str] = set()
    for name in used_names:
        used |= _file_keys(name)
    kept: list[tuple[str, list[float], int]] = []
    seen = 0
    zeros = 0
    for file_name, signals, label in entries:
        keys = _file_keys(file_name)
        if not keys or keys & used:
            seen += 1
            continue
        if _is_all_zero(signals):
            zeros += 1
            continue
        kept.append((file_name, signals, label))
    return kept, seen, zeros


def unused_holdout_rows(
    entries: list[tuple[str, list[float], int]],
    cut: int,
) -> tuple[list[tuple[str, list[float], int]], int, int]:
    """Rows whose file never appears in the fit, with all-zero signal rows removed.

    A file used by any training row is used, even when that row was all zeros.
    Rows with no file name cannot be shown to be unused, so they stay out.
    """
    used = {file_name for file_name, _, _ in entries[:cut] if file_name}
    kept: list[tuple[str, list[float], int]] = []
    seen = 0
    zeros = 0
    for file_name, signals, label in entries[cut:]:
        if not file_name or file_name in used:
            seen += 1
            continue
        if _is_all_zero(signals):
            zeros += 1
            continue
        kept.append((file_name, signals, label))
    train_files = used
    hold_files = {file_name for file_name, _, _ in kept}
    if train_files & hold_files:
        raise RuntimeError("holdout file also appears in the fit")
    return kept, seen, zeros


def _class_counts(rows: list[tuple[str, list[float], int]]) -> tuple[int, int]:
    bugs = sum(label for _, _, label in rows)
    return bugs, len(rows) - bugs


def _score_pair(
    weights: tuple[float, ...] | list[float],
    rows: list[tuple[str, list[float], int]],
    *,
    logged: bool,
) -> tuple[float, float]:
    signals = [_log_features(x) if logged else x for _, x, _ in rows]
    labels = [label for _, _, label in rows]
    scores = [dot(weights, row) for row in signals]
    return auc(scores, labels), top_capture(scores, labels)


def validate_prompt_swap(path: Path) -> int:
    """Reproduce the candidate fit, then score it on files the fit never used.

    Returns 0 only when the slopes match and both the log refit and the raw
    scaled weights beat the hand weights by more than 0.02 on that holdout.
    This function does not edit the prompt.
    """
    entries = labeled_entries(load_real(path))
    zero_rows = sum(1 for _, signals, _ in entries if _is_all_zero(signals))
    print(f"=== validate {path} ===")
    print(f"labeled={len(entries)} all_zero_rows={zero_rows}")
    reproduced = reproduce_later_row(entries)
    if reproduced is None:
        print("later-row refit could not be reproduced")
        print("prompt swap: no")
        return 2
    cut, slopes, scaled = reproduced
    print(f"fit_rows=first_{cut}_of_{len(entries)} (not the holdout rows)")
    print("reproduced slopes:", " ".join(f"{value:.2f}" for value in slopes))
    print("reproduced scaled:", tuple(scaled))
    slopes_ok = _near(slopes, CANDIDATE_SLOPES, 0.02)
    scaled_ok = _near(scaled, CANDIDATE_SCALED, 0.02)
    print(f"slopes_match={slopes_ok} scaled_match={scaled_ok}")
    observable = [entry for entry in entries if not _is_all_zero(entry[1])]
    obs_bugs, obs_empty = _class_counts(observable)
    print(f"all_zero_excluded rows={len(observable)} bugs={obs_bugs} empty={obs_empty}")
    if obs_bugs and obs_empty:
        obs_hand, obs_top = _score_pair(HAND, observable, logged=True)
        print(f"all_zero_excluded hand auc={obs_hand:.3f} top20={obs_top:.3f}")
        print("all_zero_excluded auc uses training files too; it does not approve a swap")
    else:
        print("all_zero_excluded auc withheld; one class remains")
    holdout, dropped_seen, dropped_zero = unused_holdout_rows(entries, cut)
    bugs, empties = _class_counts(holdout)
    source = "same file, files absent from the fit"
    if bugs == 0 or empties == 0:
        print(
            f"same-file unused rows after dropping zeros: bugs={bugs} empty={empties} "
            f"dropped_all_zero={dropped_zero}"
        )
        print("same-file holdout has one class after zeros are dropped, so it cannot score AUC")
        if path.resolve() == ROWS.resolve():
            print("no second file is available for a signaled empty row")
            print("prompt swap: no")
            return 2
        external = labeled_entries(load_real(ROWS))
        used_names = {file_name for file_name, _, _ in entries[:cut] if file_name}
        holdout, dropped_seen, dropped_zero = rows_outside_fit(external, used_names)
        bugs, empties = _class_counts(holdout)
        source = f"{ROWS} files absent from the fit"
    files = len({file_name for file_name, _, _ in holdout})
    print(
        f"holdout source: {source}; files={files} rows={len(holdout)} "
        f"bugs={bugs} empty={empties} dropped_seen_or_unnamed={dropped_seen} "
        f"dropped_all_zero={dropped_zero}"
    )
    if bugs == 0 or empties == 0:
        print("unused holdout does not contain both classes after dropping all-zero rows")
        print("prompt swap: no")
        return 2
    hand_auc, hand_top = _score_pair(HAND, holdout, logged=True)
    # The installed score dots INITIAL_SLOPES with log1p(commits). The scaled candidate stays on raw signals.
    raw_auc, raw_top = _score_pair(scaled, holdout, logged=False)
    fit_auc, fit_top = _score_pair(slopes, holdout, logged=True)
    print(f"holdout hand raw auc={hand_auc:.3f} top20={hand_top:.3f}")
    print(f"holdout scaled weights on raw signals auc={raw_auc:.3f} top20={raw_top:.3f}")
    print(f"holdout refit slopes on log1p auc={fit_auc:.3f} top20={fit_top:.3f}")
    # The numbers were chosen on the fit rows. This holdout only confirms them.
    raw_ok = not math.isnan(raw_auc) and raw_auc > hand_auc + 0.02
    fit_ok = not math.isnan(fit_auc) and fit_auc > hand_auc + 0.02
    print(f"raw_scaled_beats_hand_by_more_than_0.02={raw_ok} log_refit_beats_hand_by_more_than_0.02={fit_ok}")
    if slopes_ok and scaled_ok and raw_ok and fit_ok:
        print("prompt swap: yes")
        return 0
    print("prompt swap: no")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score hand weights against rank rows.")
    parser.add_argument(
        "--rows",
        type=Path,
        default=None,
        help="JSONL to score. Default is .hive/bug-hunt/rank-rows.jsonl.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Reproduce the candidate refit and score it on files the fit never used. Does not edit the prompt.",
    )
    args = parser.parse_args(argv)
    path = ROWS if args.rows is None else args.rows
    if not path.is_file():
        print(f"rank rows not found: {path}", file=sys.stderr)
        return 1
    if args.validate:
        try:
            return validate_prompt_swap(path)
        except (OSError, ValueError, RuntimeError) as exc:
            print(exc, file=sys.stderr)
            return 1
    try:
        real_report(path)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print()
    sensitivity()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
