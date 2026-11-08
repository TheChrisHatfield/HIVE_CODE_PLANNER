"""Count fix or revert commits that touched the lines a row already flags.

Does not write the locked blend. Does not fit weights.

The count matches recent_fix_commits in shape: an integer over the last
250 commits. File-level revert stays unused. A row with no flagged line
stays at 0.
"""
from __future__ import annotations

import ast
import json
import math
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_detect as det

_LINE = re.compile(r":(\d+)\)\s*$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_ROOTS = {path.name: path for path in det.DEFAULT_REPOS}


def flagged_lines(source: str) -> dict[str, set[int]]:
    """Lines the three static source signals point at. Same rules as python_signals."""
    found = {"wiring_hop": set(), "dead_setting": set(), "split_stores": set()}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    loaded: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            loaded.add(node.attr)
    assigns: dict[str, list[int]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name not in loaded:
                found["wiring_hop"].add(node.lineno)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigns.setdefault(target.id, []).append(node.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigns.setdefault(node.target.id, []).append(node.lineno)
    for name, lines in assigns.items():
        if name.isupper() and name not in loaded:
            found["dead_setting"].update(lines)
        if len(lines) >= 2:
            found["split_stores"].update(lines)
    return found


def scenario_line(scenario: str) -> int | None:
    match = _LINE.search(scenario)
    return int(match.group(1)) if match else None


def row_lines(row: dict, source: str | None) -> set[int]:
    lines: set[int] = set()
    found = scenario_line(str(row.get("scenario", "")))
    if found is not None:
        lines.add(found)
    if source is None:
        return lines
    static = flagged_lines(source)
    signals = row.get("signals") or {}
    for name in ("wiring_hop", "dead_setting", "split_stores"):
        if signals.get(name):
            lines.update(static[name])
    return lines


def _hunks(diff: str) -> list[tuple[int, int, int, int]]:
    parsed = []
    for line in diff.splitlines():
        match = _HUNK.match(line)
        if match is None:
            continue
        old_start = int(match.group(1))
        old_len = int(match.group(2)) if match.group(2) is not None else 1
        new_start = int(match.group(3))
        new_len = int(match.group(4)) if match.group(4) is not None else 1
        parsed.append((old_start, old_len, new_start, new_len))
    return parsed


def _step(lines: set[int], hunks: list[tuple[int, int, int, int]]) -> tuple[bool, set[int]]:
    """Walk one commit backward. True when a tracked line sits in a new-file hunk."""
    ordered = sorted(hunks, key=lambda item: item[2])
    hit = False
    parent: set[int] = set()
    for line in lines:
        if line <= 0:
            continue
        shift = 0
        inside = None
        for old_start, old_len, new_start, new_len in ordered:
            if line >= new_start + max(new_len, 0) and not (new_len == 0 and line == new_start):
                shift += old_len - new_len
                continue
            if new_len > 0 and new_start <= line < new_start + new_len:
                inside = (old_start, old_len, line - new_start)
            break
        if inside is None:
            mapped = line + shift
            if mapped > 0:
                parent.add(mapped)
            continue
        hit = True
        old_start, old_len, offset = inside
        if old_len <= 0:
            continue
        parent.add(old_start + min(offset, old_len - 1))
    return hit, parent


def flagged_line_fix_count(commits: list[tuple[bool, list[tuple[int, int, int, int]]]], lines: set[int]) -> int:
    """How many fix or revert commits in the window changed a flagged line."""
    if not lines:
        return 0
    pending = set(lines)
    count = 0
    for is_event, hunks in commits:
        if not pending:
            break
        hit, pending = _step(pending, hunks)
        if hit and is_event:
            count += 1
    return count


def _git_commits(root: Path, rel: str) -> list[tuple[bool, list[tuple[int, int, int, int]]]]:
    if not (root / ".git").exists():
        return []
    try:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "safe.directory=*",
                "-c",
                f"safe.directory={root.resolve().as_posix()}",
                "-C",
                str(root),
                "log",
                f"-n{det.GIT_COMMITS}",
                "-U0",
                "--pretty=format:%x1e%s%x1f",
                "--",
                rel,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    commits = []
    for chunk in completed.stdout.split("\x1e"):
        if "\x1f" not in chunk:
            continue
        subject, diff = chunk.split("\x1f", 1)
        subject = subject.strip()
        is_revert = subject.lower().startswith("revert")
        is_event = bool(subject) and (is_revert or det._FIX.search(subject) is not None)
        commits.append((is_event, _hunks(diff)))
    return commits


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n == 0:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def main() -> None:
    rows = []
    for line in (Path(__file__).resolve().parents[1] / "sandbox_rank_detect_mixed.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    groups: dict[tuple[str, str], list[int]] = {}
    line_sets: list[set[int]] = []
    for index, row in enumerate(rows):
        file_name = str(row.get("file", ""))
        repo_name, _, rel = file_name.partition("/")
        root = _ROOTS.get(repo_name)
        source = None
        if root is not None and rel:
            source = det._read(root / rel)
        lines = row_lines(row, source)
        line_sets.append(lines)
        if lines and root is not None and rel:
            groups.setdefault((repo_name, rel), [])
    commits: dict[tuple[str, str], list] = {}
    work = []
    for repo_name, rel in groups:
        root = _ROOTS[repo_name]
        work.append((repo_name, rel, root))

    def load(item):
        repo_name, rel, root = item
        return (repo_name, rel), _git_commits(root, rel)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, value in pool.map(load, work):
            commits[key] = value
    counts = []
    for row, lines in zip(rows, line_sets):
        file_name = str(row.get("file", ""))
        repo_name, _, rel = file_name.partition("/")
        history = commits.get((repo_name, rel), [])
        counts.append(flagged_line_fix_count(history, lines))
    labels = [1 if row.get("outcome") != "empty" else 0 for row in rows]
    signal_names = list(det.SIGNALS)
    matrix = {name: [float(row["signals"][name]) for row in rows] for name in signal_names}
    matrix["flagged_line_fix"] = [float(value) for value in counts]
    lit = [value for value in counts if value]
    pos = [(value, label) for value, label in zip(counts, labels) if label == 1]
    neg = [(value, label) for value, label in zip(counts, labels) if label == 0]
    corr = {name: _pearson(matrix["flagged_line_fix"], matrix[name]) for name in signal_names}
    corr["label"] = _pearson(matrix["flagged_line_fix"], [float(value) for value in labels])
    def pack(pairs):
        values = [value for value, _ in pairs]
        return {
            "rows": len(values),
            "lit": sum(1 for value in values if value),
            "zero": sum(1 for value in values if value == 0),
            "mean": round(sum(values) / len(values), 4) if values else None,
            "max": max(values) if values else None,
            "hist": {
                "0": sum(1 for value in values if value == 0),
                "1": sum(1 for value in values if value == 1),
                "2+": sum(1 for value in values if value >= 2),
            },
        }
    print(json.dumps({
        "rows": len(rows),
        "files_queried": len(groups),
        "rows_with_flagged_lines": sum(1 for lines in line_sets if lines),
        "lit": len(lit),
        "max": max(counts) if counts else None,
        "correlation": {key: None if value is None else round(value, 4) for key, value in corr.items()},
        "positives": pack(pos),
        "negatives": pack(neg),
    }))


if __name__ == "__main__":
    main()
