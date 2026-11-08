"""Hard-negative rows for the rank sandbox.

A row is a file the detector parses and does not flag, whose signals light
one or two of the six names. Outcome stays empty. Existing mixed rows and
Hive logs are not read for writing and are not modified.

    py -3.11 scripts/sandbox_rank_hard_negatives.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sandbox_rank_detect as det

OUT = Path(__file__).resolve().parent / "sandbox_rank_hard_negatives.jsonl"
TARGET = 400
CAP = 40


def _signals_for(path: Path, root: Path, source: str, stems: set[str], fixes: dict[str, int], reverted: set[str]) -> det.Signals:
    rel = path.relative_to(root).as_posix()
    if path.suffix.lower() == ".py":
        signals = det.python_signals(source, 1 if det.is_thin(path, root, stems) else 0)
    else:
        signals = det.Signals(thin_test=1 if det.is_thin(path, root, stems) else 0)
    signals.recent_fix_commits = fixes.get(rel.casefold(), 0)
    if rel.casefold() in reverted:
        signals.reverted = 1
    return signals


def _lit(signals: det.Signals) -> tuple[str, ...]:
    values = signals.as_dict()
    return tuple(name for name in det.SIGNALS if values[name])


def collect() -> list[dict[str, object]]:
    buckets: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for root in det.DEFAULT_REPOS:
        if not root.is_dir():
            print(f"missing {root}", file=sys.stderr)
            continue
        paths = det.iter_source(root)
        stems = det.test_stems(paths, root)
        fixes, reverted = det.git_history(root)
        fix_lookup: dict[str, int] = {}
        for key, value in fixes.items():
            folded = key.casefold()
            fix_lookup[folded] = fix_lookup.get(folded, 0) + value
        revert_lookup = {key.casefold() for key in reverted}
        repo_name = root.name
        for path in paths:
            source = det._read(path)
            if source is None:
                continue
            found = det.findings_for(path, source)
            if found is None or found:
                continue
            signals = _signals_for(path, root, source, stems, fix_lookup, revert_lookup)
            lit = _lit(signals)
            if not 1 <= len(lit) <= 2:
                continue
            rel = path.relative_to(root).as_posix()
            buckets[lit].append(
                {
                    "file": f"{repo_name}/{rel}",
                    "signals": signals.as_dict(),
                    "weighted_sum": signals.weighted_sum(),
                    "scenario": f"hard-negative: no static defect; signals {','.join(lit)} ({rel})",
                    "outcome": "empty",
                }
            )
    for key in sorted(buckets):
        print(f"available {len(buckets[key]):4}  {','.join(key)}", file=sys.stderr)
    chosen: list[dict[str, object]] = []
    for key in sorted(buckets):
        rows = buckets[key]
        rows.sort(key=lambda row: str(row["file"]))
        chosen.extend(rows[:CAP])
    if len(chosen) > TARGET:
        # Keep every pattern, then trim the largest buckets.
        by_key: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
        for row in chosen:
            values = row["signals"]
            key = tuple(name for name in det.SIGNALS if values[name])
            by_key[key].append(row)
        while sum(len(rows) for rows in by_key.values()) > TARGET:
            biggest = max(by_key, key=lambda item: len(by_key[item]))
            if len(by_key[biggest]) <= 1:
                break
            by_key[biggest].pop()
        chosen = [row for key in sorted(by_key) for row in by_key[key]]
    return chosen


def main() -> int:
    rows = collect()
    text = "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows)
    OUT.write_text(text, encoding="utf-8")
    counts = {name: 0 for name in det.SIGNALS}
    for row in rows:
        for name in det.SIGNALS:
            if row["signals"][name]:
                counts[name] += 1
    print(f"hard_negatives={len(rows)} path={OUT}")
    for name in det.SIGNALS:
        print(f"  {name}={counts[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
