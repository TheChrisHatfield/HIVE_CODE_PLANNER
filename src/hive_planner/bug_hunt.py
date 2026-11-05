"""Continuous bug-hunt agent script (hook: change.bugfix_mode, integration.wiring_audit)."""

from __future__ import annotations

import difflib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DEFAULT_ITERATIONS = 50
DEFAULT_PAUSE_SECONDS = 10
MIN_ITERATIONS = 1
MAX_ITERATIONS = 200

COMMAND_REL = Path(".cursor") / "commands" / "bug-hunt.md"
RULE_REL = Path(".cursor") / "rules" / "bug-hunt.mdc"
PACKET_REL = Path(".hive") / "bug-hunt" / "AGENT_PROMPT.md"
DUAL_LANE_REL = Path(".cursor") / "rules" / "bug-hunt-dual-lane.mdc"
SCRIPTS_REL = Path("scripts") / "bug-hunt.md"
CONTINUE_HOOK_REL = Path(".cursor") / "hooks" / "bug_hunt_continue.py"
HOOKS_JSON_REL = Path(".cursor") / "hooks.json"
CONTINUE_HOOK_COMMAND = "py -3.11 .cursor/hooks/bug_hunt_continue.py"
CONTINUE_HOOK_TIMEOUT = 86400
CONTINUE_HOOK_LOOP_LIMIT = 210
OVERLAY_REL = Path(".hive") / "bug-hunt" / "repo-overlay.md"

# Starting slopes for the ranker. Six-signal logistic fit, seed 0, on the
# locked 603-row blend (twenty stratified splits, fitted median 0.884).
# Order matches the six signals. The first multiplies log1p(fix commits).
# The other five multiply the raw signals. Not the hand weights 3, 5, 5, 4, 4, 4.
INITIAL_SLOPES = (0.7118, 3.3024, 1.0245, -0.1424, 0.0, 0.0)
RANK_ROWS_REL = Path(".hive") / "bug-hunt" / "rank-rows.jsonl"
RANK_PASS_REL = Path(".hive") / "bug-hunt" / "rank-pass.json"
SIGNAL_KEYS = (
    "recent_fix_commits",
    "thin_test",
    "wiring_hop",
    "dead_setting",
    "reverted",
    "split_stores",
)
ANCHOR_VOTES = 20.0
ANCHOR_HALFLIFE_ROWS = 40.0
ROW_DECAY = 0.9
CANDIDATE_FILE_LIMIT = 1200
QUEUE_LIMIT = 50
_PULL_OUTCOMES = frozenset({"committed", "review-failed"})
_PUSH_OUTCOMES = frozenset({"empty"})
TRUST_SEED = 1.0
PLACE_SEED = 0.0
SURPRISE_WINDOW = 10


def fix_commit_feature(count: float) -> float:
    """log1p of the fix-commit count. Zero returns 0. A negative count is refused."""
    value = float(count)
    if value < 0.0:
        raise ValueError(f"fix-commit count must be >= 0, got {count}")
    return math.log1p(value)


def score_signals(
    signals: tuple[float, ...] | list[float],
    slopes: tuple[float, ...] | list[float] | None = None,
) -> float:
    """Score one file. Feature 0 is log1p of the fix-commit count. The other five are raw."""
    if len(signals) != 6:
        raise ValueError(f"score_signals expects 6 signals, got {len(signals)}")
    weights = INITIAL_SLOPES if slopes is None else tuple(slopes)
    if len(weights) != 6:
        raise ValueError(f"score_signals expects 6 slopes, got {len(weights)}")
    features = [fix_commit_feature(signals[0]), *(float(value) for value in signals[1:])]
    return sum(weight * feature for weight, feature in zip(weights, features))


def _finding_count(value: object) -> int:
    """Detector hit count for ranking. Booleans and non-integers are not counts."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            try:
                value = int(text)
            except OverflowError:
                return 0
        else:
            try:
                parsed = float(text)
            except (ValueError, OverflowError):
                return 0
            if math.isnan(parsed) or math.isinf(parsed) or not parsed.is_integer():
                return 0
            try:
                value = int(parsed)
            except (OverflowError, ValueError):
                return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    if isinstance(value, float) and value.is_integer():
        try:
            count = int(value)
        except OverflowError:
            return 0
        return count if count > 0 else 0
    return 0


def rank_queue_score(
    six_score: float,
    findings: object,
    trust_draw: float = 0.0,
    place_draw: float = 0.0,
) -> float:
    """Queue score: six-signal linear mix plus sampled trust and place draws."""
    bit = 1.0 if _finding_count(findings) > 0 else 0.0
    total = float(six_score) + float(trust_draw) * bit + float(place_draw)
    if math.isnan(total) or math.isinf(total):
        return 0.0
    return total


def queue_sort_key(item: dict) -> tuple:
    """Highest mix first, then finding count, then lines."""
    findings = _finding_count(item.get("findings"))
    raw_score = item.get("score")
    try:
        score = 0.0 if raw_score is None else float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
    if math.isnan(score) or math.isinf(score):
        score = 0.0
    raw_lines = item.get("lines")
    if isinstance(raw_lines, bool) or raw_lines is None:
        lines = 0
    else:
        try:
            lines = int(raw_lines)
        except (TypeError, ValueError, OverflowError):
            lines = 0
    return (
        -score,
        -findings,
        -lines,
        str(item.get("file") or ""),
    )


def imaginary_votes(voted_count: int) -> float:
    """Twenty seed votes, halved for every forty voted rows. Not re-added at full strength."""
    count = max(0, int(voted_count))
    return ANCHOR_VOTES * (0.5 ** (count / ANCHOR_HALFLIFE_ROWS))


def _signal_list(raw: object) -> list[float] | None:
    if isinstance(raw, dict):
        try:
            values = [float(raw[key]) for key in SIGNAL_KEYS]
        except (KeyError, TypeError, ValueError):
            return None
    elif isinstance(raw, list) and len(raw) == 6:
        try:
            values = [float(item) for item in raw]
        except (TypeError, ValueError):
            return None
    else:
        return None
    if values[0] < 0.0:
        return None
    if any(math.isnan(value) or math.isinf(value) for value in values):
        return None
    return values


def _vote_rows(rows: list[dict]) -> list[tuple[float, list[float]]]:
    """File order. Skipped rows and rows without six signals cast no vote."""
    voted: list[tuple[float, list[float]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        outcome = str(row.get("outcome") or "").strip().casefold()
        if outcome in _PULL_OUTCOMES:
            sign = 1.0
        elif outcome in _PUSH_OUTCOMES:
            sign = -1.0
        else:
            continue
        signals = _signal_list(row.get("signals"))
        if signals is None:
            continue
        voted.append((sign, [fix_commit_feature(signals[0]), *signals[1:]]))
    return voted


def rebuild_mean(rows: list[dict]) -> tuple[tuple[float, ...], float]:
    """Rebuilt mean and the evidence that sets the bell-curve width.

    Newest voted row counts as 1. Each step older multiplies by 0.9.
    Committed and review-failed pull toward that file's signals. Empty pulls away.
    The denominator is the shrunk seed votes plus those decayed votes.
    Four hundred rows does not freeze this mean.
    """
    voted = _vote_rows(rows)
    anchor = imaginary_votes(len(voted))
    numer = [anchor * slope for slope in INITIAL_SLOPES]
    denom = anchor
    count = len(voted)
    for index, (sign, features) in enumerate(voted):
        weight = ROW_DECAY ** (count - 1 - index)
        denom += weight
        for slot, feature in enumerate(features):
            numer[slot] += sign * weight * feature
    if denom <= 0.0:
        return INITIAL_SLOPES, anchor
    mean = tuple(value / denom for value in numer)
    return mean, denom


def _outcome_sign(row: dict) -> float | None:
    outcome = str(row.get("outcome") or "").strip().casefold()
    if outcome in _PULL_OUTCOMES:
        return 1.0
    if outcome in _PUSH_OUTCOMES:
        return -1.0
    return None


def _surprise_score(row: dict) -> float | None:
    if "score" not in row:
        return None
    raw = row.get("score")
    if raw is None:
        return None
    try:
        score = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(score) or math.isinf(score):
        return None
    return score


def surprise_scale(rows: list[dict]) -> float:
    """1+m from the last ten voted rows versus stored mix scores."""
    voted: list[dict] = []
    for row in rows:
        if isinstance(row, dict) and _outcome_sign(row) is not None:
            voted.append(row)
    window = voted[-SURPRISE_WINDOW:]
    if not window:
        return 1.0
    misses = 0
    for row in window:
        score = _surprise_score(row)
        if score is None:
            continue
        sign = _outcome_sign(row)
        if sign is None:
            continue
        if sign < 0.0 and score > 0.0:
            misses += 1
        elif sign > 0.0 and score <= 0.0:
            misses += 1
    return 1.0 + (misses / len(window))


def rebuild_scalar_mean(
    rows: list[dict],
    seed: float,
    predicate,
) -> tuple[float, float]:
    voted: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        sign = _outcome_sign(row)
        if sign is None or not predicate(row):
            continue
        voted.append(sign)
    anchor = imaginary_votes(len(voted))
    numer = anchor * seed
    denom = anchor
    count = len(voted)
    for index, sign in enumerate(voted):
        weight = ROW_DECAY ** (count - 1 - index)
        denom += weight
        numer += sign * weight
    if denom <= 0.0:
        return float(seed), float(anchor)
    return numer / denom, denom


def rebuild_trust(rows: list[dict]) -> tuple[float, float]:
    return rebuild_scalar_mean(
        rows,
        TRUST_SEED,
        lambda row: _finding_count(row.get("findings")) > 0,
    )


def rebuild_place(rows: list[dict], folder: str) -> tuple[float, float]:
    key = str(folder or ".").casefold()
    return rebuild_scalar_mean(
        rows,
        PLACE_SEED,
        lambda row: _subsystem(str(row.get("file") or "")).casefold() == key,
    )


def draw_width(evidence: float, surprise: float = 1.0) -> float:
    base = 1.0 / math.sqrt(evidence) if evidence > 0.0 else 1.0
    return base * float(surprise)


def thompson_draw(
    mean: tuple[float, ...],
    evidence: float,
    rng: random.Random | None = None,
    surprise: float = 1.0,
) -> tuple[float, ...]:
    """One independent normal sample per slope. The caller discards it."""
    generator = rng if rng is not None else random.Random()
    width = draw_width(evidence, surprise)
    return tuple(generator.gauss(value, width) for value in mean)


def thompson_scalar(
    mean: float,
    evidence: float,
    rng: random.Random | None = None,
    surprise: float = 1.0,
) -> float:
    generator = rng if rng is not None else random.Random()
    return generator.gauss(float(mean), draw_width(evidence, surprise))


def load_rank_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        payload = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, MemoryError):
        return []
    rows: list[dict] = []
    for line in payload.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except (json.JSONDecodeError, MemoryError, RecursionError, OverflowError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def rank_pass(
    path: Path | None = None,
    rng: random.Random | None = None,
) -> dict[str, tuple[float, ...] | float]:
    """Rebuild from rank rows, draw once, and return both. Does not write the draw."""
    rows = load_rank_rows(path if path is not None else RANK_ROWS_REL)
    scale = surprise_scale(rows)
    mean, evidence = rebuild_mean(rows)
    draw = thompson_draw(mean, evidence, rng, scale)
    return {"mean": mean, "draw": draw, "evidence": evidence, "surprise": scale}


def print_rank_pass(path: Path | None = None) -> None:
    """Print this pass's draw. The next call rebuilds from the rows, not from this draw."""
    result = rank_pass(path)
    payload = {
        "draw": [round(float(value), 6) for value in result["draw"]],
        "mean": [round(float(value), 6) for value in result["mean"]],
    }
    print(json.dumps(payload, allow_nan=False))


_WALK_SKIP = {
    ".git",
    ".hg",
    ".hive",
    ".svn",
    ".venv",
    ".vs",
    "__pycache__",
    "CHAT_HISTORY",
    "Library",
    "Logs",
    "Temp",
    "bin",
    "node_modules",
    "obj",
    "site-packages",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".nox",
}
_WALK_SKIP_FOLD = frozenset(name.casefold() for name in _WALK_SKIP)
_RANK_OUTCOMES = frozenset({"committed", "skipped", "empty", "review-failed"})


def _norm_rel(value: str) -> str:
    """Repo-relative posix path. Strip `./` prefixes, not leading dots in `.cursor`."""
    text = str(value).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _opened_key(value: str) -> str:
    return _norm_rel(value).casefold()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    folder = None
    tmp = None
    try:
        folder = tempfile.TemporaryDirectory(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            ignore_cleanup_errors=True,
        )
        tmp = Path(folder.name) / path.name
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        if folder is not None:
            try:
                folder.cleanup()
            except OSError:
                pass


def _load_opened(root: Path) -> list[str]:
    path = root / RANK_PASS_REL
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, MemoryError) as exc:
        raise BugHuntError(f"could not read {RANK_PASS_REL.as_posix()}") from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise BugHuntError(f"{RANK_PASS_REL.as_posix()} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BugHuntError(f"{RANK_PASS_REL.as_posix()} is not a JSON object")
    opened = payload.get("opened")
    if opened is None:
        return []
    if not isinstance(opened, list):
        raise BugHuntError(f"{RANK_PASS_REL.as_posix()} opened list is invalid")
    kept: list[str] = []
    for item in opened:
        if isinstance(item, bool) or not isinstance(item, str):
            continue
        rel = _norm_rel(item)
        if rel:
            kept.append(rel)
    return kept


def _finite_score(value: object) -> float:
    try:
        score = 0.0 if value is None else float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(score) or math.isinf(score):
        return 0.0
    return score


def _queue_item(root: Path, rel: str) -> dict | None:
    path = root / RANK_PASS_REL
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError):
        return None
    if not isinstance(payload, dict):
        return None
    queue = payload.get("queue")
    if not isinstance(queue, list):
        return None
    wanted = _opened_key(rel)
    for item in queue:
        if not isinstance(item, dict):
            continue
        if _opened_key(str(item.get("file") or "")) != wanted:
            continue
        return item
    return None


def _queue_signals(root: Path, rel: str) -> dict[str, float] | None:
    item = _queue_item(root, rel)
    if item is None:
        return None
    signals = _signal_list(item.get("signals"))
    if signals is None:
        return None
    return {key: signals[index] for index, key in enumerate(SIGNAL_KEYS)}


def _previous_top(root: Path) -> str:
    """File the last queue told the pass to open."""
    path = root / RANK_PASS_REL
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError):
        return ""
    if not isinstance(payload, dict):
        return ""
    queue = payload.get("queue")
    if not isinstance(queue, list) or not queue or not isinstance(queue[0], dict):
        return ""
    return _norm_rel(str(queue[0].get("file") or ""))


def _fallback_signals(
    root: Path,
    rel: str,
    history: tuple[dict[str, int], set[str]] | None,
) -> dict[str, float]:
    """Signals for a row that is no longer in the queue. Git counts stay with the file."""
    fixes, reverted = history if history is not None else _git_history(root)
    measured = _signals_for_file(
        root / rel,
        rel,
        fixes=fixes,
        reverted=reverted,
        stems=_test_stems([rel]),
    )
    if measured is None:
        return {key: 0.0 for key in SIGNAL_KEYS}
    return measured[0]


def _take_pass_file(
    root: Path,
    state: dict | None,
    opened: list[str],
    history: tuple[dict[str, int], set[str]] | None,
) -> tuple[list[str], bool]:
    """Record this pass's file. A missing file key uses the queue head so the next file differs."""
    if not isinstance(state, dict):
        return opened, False
    rel = _norm_rel(str(state.get("file") or ""))
    guessed = False
    if not rel:
        rel = _previous_top(root)
        guessed = bool(rel)
    if not rel:
        return opened, False
    opened_keys = {_opened_key(item) for item in opened}
    appended = False
    if _opened_key(rel) not in opened_keys:
        outcome = str(state.get("outcome") or "").strip().casefold()
        if (
            outcome in _RANK_OUTCOMES
            and not guessed
            and _opened_key(_last_rank_file(root)) != _opened_key(rel)
        ):
            signals = _queue_signals(root, rel)
            if signals is None:
                signals = _fallback_signals(root, rel, history)
            scenario = str(state.get("scenario") or "").strip()
            queued = _queue_item(root, rel) or {}
            _append_rank_row(
                root,
                rel,
                signals,
                scenario,
                outcome,
                findings=queued.get("findings"),
                score=queued.get("score"),
            )
            appended = True
        opened = [*opened, rel]
    return opened, appended


def _last_rank_file(root: Path) -> str:
    rows = load_rank_rows(root / RANK_ROWS_REL)
    if not rows:
        return ""
    return _norm_rel(str(rows[-1].get("file") or ""))


def _append_rank_row(
    root: Path,
    rel: str,
    signals: dict[str, float],
    scenario: str,
    outcome: str,
    findings: object = 0,
    score: object = 0.0,
) -> None:
    path = root / RANK_ROWS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "file": rel,
        "signals": signals,
        "scenario": scenario,
        "outcome": outcome,
        "findings": _finding_count(findings),
        "score": _finite_score(score),
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, allow_nan=False) + "\n")


def _detector_ready(mod: object) -> bool:
    """True when the detector exposes every call site used in ranking."""
    return (
        callable(getattr(mod, "findings_for", None))
        and callable(getattr(mod, "python_signals", None))
        and callable(getattr(mod, "parse_git_log", None))
        and isinstance(getattr(mod, "Signals", None), type)
    )


def _detector_allowed_roots() -> list[Path]:
    here = Path(__file__).resolve().parent
    roots = [here]
    try:
        roots.append((Path(__file__).resolve().parents[2] / "scripts").resolve())
    except (IndexError, OSError):
        pass
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            try:
                roots.append(Path(meipass).resolve())
            except OSError:
                pass
    return roots


def _detector_path_trusted(path: Path) -> bool:
    """Only exec the detector file from this package, repo scripts, or a frozen bundle."""
    if path.name != "sandbox_rank_detect.py":
        return False
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if not resolved.is_file():
        return False
    for root in _detector_allowed_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _detector_file_candidates() -> list[Path]:
    here = Path(__file__).resolve()
    candidates = [here.with_name("sandbox_rank_detect.py")]
    try:
        candidates.append(here.parents[2] / "scripts" / "sandbox_rank_detect.py")
    except IndexError:
        pass
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled = [
                Path(meipass) / "hive_planner" / "sandbox_rank_detect.py",
                Path(meipass) / "scripts" / "sandbox_rank_detect.py",
            ]
            candidates = bundled + candidates
    return [path for path in candidates if _detector_path_trusted(path)]


def _load_detector_from_path(path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("hive_sandbox_rank_detect", path)
    if spec is None or spec.loader is None:
        raise BugHuntError(f"sandbox detector could not load ({path})")
    mod = importlib.util.module_from_spec(spec)
    # Dataclass execution reads sys.modules[cls.__module__]. A missing or None
    # entry raises AttributeError on Finding/Signals.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        if sys.modules.get(spec.name) is mod:
            del sys.modules[spec.name]
        raise BugHuntError(f"sandbox detector could not load ({path})") from exc
    return mod


@lru_cache(maxsize=1)
def _sandbox_detect():
    """Load the sandbox findings detector. Offline fitter stays unwired.

    Pip and portable installs import `hive_planner.sandbox_rank_detect`. Editable
    checkouts and frozen datas still fall back to `scripts/sandbox_rank_detect.py`.
    """
    try:
        from hive_planner import sandbox_rank_detect as mod

        if _detector_ready(mod):
            sys.modules.setdefault("hive_sandbox_rank_detect", mod)
            return mod
    except Exception:
        # Any import/init failure still walks the trusted file candidates.
        pass
    candidates = _detector_file_candidates()
    last_error: BugHuntError | None = None
    for path in candidates:
        if not path.is_file():
            continue
        try:
            mod = _load_detector_from_path(path)
        except BugHuntError as exc:
            last_error = exc
            continue
        if _detector_ready(mod):
            return mod
        if sys.modules.get("hive_sandbox_rank_detect") is mod:
            del sys.modules["hive_sandbox_rank_detect"]
        last_error = BugHuntError(f"sandbox detector could not load ({path})")
    if last_error is not None:
        raise last_error
    shown = candidates[0] if candidates else Path("sandbox_rank_detect.py")
    raise BugHuntError(f"sandbox detector is missing ({shown})")


def _candidate_files(root: Path) -> list[Path]:
    found: list[Path] = []
    if not root.is_dir():
        return found
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name
                for name in dirnames
                if name.casefold() not in _WALK_SKIP_FOLD and not name.casefold().startswith(".egg")
            ]
            for name in filenames:
                if name.lower().endswith((".py", ".cs")):
                    found.append(Path(dirpath) / name)
    except MemoryError:
        pass
    found.sort()
    return found[:CANDIDATE_FILE_LIMIT]


def _git_history(root: Path) -> tuple[dict[str, int], set[str]]:
    if not (root / ".git").exists():
        return {}, set()
    try:
        completed = subprocess.run(
            ["git", "-c", "safe.directory=*", "log", "-n", "250", "--pretty=format:%x1e%s%x1f", "--name-only"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, MemoryError):
        return {}, set()
    if completed.returncode != 0:
        return {}, set()
    detect = _sandbox_detect()
    try:
        parsed_fixes, parsed_reverted = detect.parse_git_log(completed.stdout)
        fixes: dict[str, int] = {}
        for rel, count in parsed_fixes.items():
            key = _opened_key(rel)
            fixes[key] = fixes.get(key, 0) + int(count)
        return fixes, {_opened_key(path) for path in parsed_reverted}
    except (TypeError, ValueError, AttributeError, RecursionError, OSError, OverflowError, MemoryError):
        return {}, set()


def _test_stems(rels: list[str]) -> set[str]:
    stems: set[str] = set()
    for rel in rels:
        path = Path(rel)
        name = path.stem.lower()
        parts = [part.lower() for part in path.parts]
        is_test = (
            name in {"test", "tests"}
            or name.startswith("test_")
            or name.endswith("_test")
            or "tests" in parts[:-1]
        )
        if is_test:
            stems.add(name.removeprefix("test_").removesuffix("_test"))
    return stems


def _signals_for_file(
    path: Path,
    rel: str,
    *,
    fixes: dict[str, int],
    reverted: set[str],
    stems: set[str],
) -> tuple[dict[str, float], int, int] | None:
    try:
        if path.stat().st_size > 400_000:
            return None
        source = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError, MemoryError):
        return None
    detect = _sandbox_detect()
    try:
        found = detect.findings_for(path, source)
    except (TypeError, ValueError, AttributeError, OSError, RecursionError, MemoryError):
        return None
    parse_failed = found is None
    if found is None:
        found = []
    elif not isinstance(found, list):
        return None
    thin = 0 if Path(rel).stem.lower() in stems else 1
    finding_count = len(found) + (1 if parse_failed else 0)
    try:
        if path.suffix.lower() == ".py":
            packed = detect.python_signals(source, thin)
        else:
            packed = detect.Signals(thin_test=thin)
        folded = _opened_key(rel)
        packed.recent_fix_commits = int(fixes.get(folded, 0))
        packed.reverted = 1 if folded in reverted else 0
        signals = {key: float(getattr(packed, key)) for key in SIGNAL_KEYS}
        if any(math.isnan(value) or math.isinf(value) for value in signals.values()):
            raise ValueError("non-finite signal")
    except (RecursionError, MemoryError):
        if finding_count == 0:
            return None
        signals = {key: 0.0 for key in SIGNAL_KEYS}
    except (TypeError, ValueError, AttributeError):
        return None
    return signals, source.count("\n") + 1, finding_count


def score_unopened(
    root: Path,
    opened: list[str],
    slopes: tuple[float, ...],
    *,
    files: list[Path] | None = None,
    history: tuple[dict[str, int], set[str]] | None = None,
    limit: int | None = QUEUE_LIMIT,
    trust_draw: float = 0.0,
    place_draws: dict[str, float] | None = None,
) -> list[dict[str, object]]:
    """Score files this hunt has not opened. The slopes are this pass's draw.

    Pass limit=None to rank every qualifying candidate, then persist the top 50.
    """
    root = Path(root)
    chosen = files if files is not None else _candidate_files(root)
    rels = []
    for path in chosen:
        try:
            rels.append(path.resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            rels.append(_norm_rel(str(path)))
    stems = _test_stems(rels)
    fixes, reverted = history if history is not None else _git_history(root)
    closed = {_opened_key(item) for item in opened}
    places = place_draws or {}
    ranked: list[dict[str, object]] = []
    for path, rel in zip(chosen, rels):
        rel = _norm_rel(rel)
        if not rel or _opened_key(rel) in closed:
            continue
        try:
            measured = _signals_for_file(
                path if path.is_file() else root / rel,
                rel,
                fixes=fixes,
                reverted=reverted,
                stems=stems,
            )
            if measured is None:
                continue
            signals, lines, finding_count = measured
            values = [signals[key] for key in SIGNAL_KEYS]
            if not any(values) and finding_count == 0:
                continue
            six_score = score_signals(values, slopes)
            folder = _subsystem(rel)
            place_draw = places.get(folder.casefold(), 0.0)
            combined = rank_queue_score(six_score, finding_count, trust_draw, place_draw)
            ranked.append(
                {
                    "file": rel,
                    "signals": signals,
                    "score": round(combined, 6),
                    "lines": lines,
                    "findings": finding_count,
                }
            )
        except MemoryError:
            continue
    ranked.sort(key=queue_sort_key)
    if limit is None:
        return ranked
    cap = int(limit)
    if cap <= 0:
        return []
    return ranked[:cap]


def _subsystem(rel: str) -> str:
    """First path part after posix normalize. Root files are `.`."""
    text = _norm_rel(rel)
    if not text:
        return "."
    head, sep, _rest = text.partition("/")
    return head if sep else "."


def advance_rank_pass(
    root: Path,
    state: dict | None = None,
    *,
    fresh: bool = False,
    rng: random.Random | None = None,
    files: list[Path] | None = None,
    history: tuple[dict[str, int], set[str]] | None = None,
) -> dict[str, object]:
    """Append this pass's outcome row, rebuild, score unopened files, discard the draw.

    The queue file stores the opened set and the scored files. It does not store the draw.
    The next rebuild reads rank rows only.
    """
    root = Path(root)
    opened = [] if fresh else _load_opened(root)
    opened, appended = _take_pass_file(root, None if fresh else state, opened, history)
    rows = load_rank_rows(root / RANK_ROWS_REL)
    scale = surprise_scale(rows)
    mean, evidence = rebuild_mean(rows)
    draw = thompson_draw(mean, evidence, rng, scale)
    trust_mean, trust_evidence = rebuild_trust(rows)
    trust_draw = thompson_scalar(trust_mean, trust_evidence, rng, scale)
    queue = score_unopened(
        root,
        opened,
        draw,
        files=files,
        history=history,
        limit=None,
        trust_draw=trust_draw,
    )
    place_draws: dict[str, float] = {}
    for item in queue:
        folder = _subsystem(str(item.get("file") or ""))
        key = folder.casefold()
        if key in place_draws:
            continue
        place_mean, place_evidence = rebuild_place(rows, folder)
        place_draws[key] = thompson_scalar(place_mean, place_evidence, rng, scale)
    for item in queue:
        folder = _subsystem(str(item.get("file") or ""))
        signals = item.get("signals")
        values = None
        if isinstance(signals, dict):
            try:
                values = [float(signals[key]) for key in SIGNAL_KEYS]
            except (KeyError, TypeError, ValueError):
                values = None
        six_score = score_signals(values, draw) if values is not None else 0.0
        item["score"] = round(
            rank_queue_score(
                six_score,
                item.get("findings"),
                trust_draw,
                place_draws.get(folder.casefold(), 0.0),
            ),
            6,
        )
    queue.sort(key=queue_sort_key)
    queue = queue[:QUEUE_LIMIT]
    _write_json(root / RANK_PASS_REL, {"opened": opened, "queue": queue})
    top = str(queue[0]["file"]) if queue else ""
    return {"top": top, "appended": appended, "opened": opened}


def save_stopped_outcome(
    root: Path,
    state: dict | None,
    *,
    history: tuple[dict[str, int], set[str]] | None = None,
) -> dict[str, bool]:
    """Write the outcome row when the hunt stops. Does not draw or start another pass.

    Call this before writing continue.json active false, or from a hook that still
    sees a stop token whose active flag is already false.
    """
    root = Path(root)
    prior_opened = _load_opened(root)
    opened, appended = _take_pass_file(root, state, prior_opened, history)
    missing_outcome = False
    if isinstance(state, dict):
        outcome = str(state.get("outcome") or "").strip().casefold()
        missing_outcome = outcome not in _RANK_OUTCOMES and not appended
    path = root / RANK_PASS_REL
    queue: list = []
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError, UnicodeError, MemoryError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("queue"), list):
            closed = {_opened_key(item) for item in opened}
            queue = [
                item
                for item in payload["queue"]
                if isinstance(item, dict) and _opened_key(str(item.get("file") or "")) not in closed
            ]
    payload: dict[str, object] = {"opened": opened, "queue": queue}
    if missing_outcome:
        payload["stop_warning"] = (
            "Stop met without a valid outcome on continue.json; no rank row was appended."
        )
    if appended or opened != prior_opened or missing_outcome:
        _write_json(path, payload)
    return {"appended": appended, "missing_outcome": missing_outcome}


# Explicit phrases plus common typos (also listed in the always-on Cursor rule).
TRIGGER_PHRASES = (
    "bug hunt",
    "bu hunt",
    "bug hun",
    "bung hunt",
    "do a bug hunt",
    "do a bung hunt",
    "bug-hunt",
    "bughunt",
    "/bug-hunt",
    "hunt for bugs",
    "hunt bugs",
    "hunting bugs",
    "run a bug hunt",
    "start a bug hunt",
    "perform a bug hunt",
    "bug hunting",
    "bug hunts",
    "hunt some bugs",
    "hunting for more bugs",
    "run another loop to fix bugs",
    "loop to fix bugs",
)

_COMMAND_QUESTION = re.compile(
    r"(?i)^\s*(how\s+(do\s+i|does|to)|where\s+(is|does)|what\s+(is|does)|does)\b"
)
_DOCS_QUESTION = re.compile(
    r"(?i)\b(?:how\s+(?:do\s+i|does|to)|where\s+(?:is|does)|what\s+(?:is|does))\b.{0,80}?\bbu[gn]g?"
)
# Negations, stop requests, and review-only wording near the hunt phrase are not
# start signals. They must not restart a loop the user is trying to end or inspect.
_HUNT_NAME = r"(?:bu[gn]g?\s*-?\s*hun(?:t(?:s|ing)?)?|bughunt|hunt(?:ing)?\s+for\s+bugs)"
_NEGATED_START = re.compile(
    rf"(?i)(?:\b(?:do\s*n'?t|do\s+not|dont)\s+(?:run|start|begin|launch|perform|want)\s+"
    rf"(?:the\s+|a\s+|another\s+|this\s+)?{_HUNT_NAME}"
    rf"|\bnever\s+(?:(?:run|start|begin|launch|perform)\s+)?"
    rf"(?:the\s+|a\s+|another\s+|this\s+)?{_HUNT_NAME}"
    rf"|\bwithout\s+(?:running|starting|beginning)\s+(?:the\s+|a\s+|another\s+|this\s+)?{_HUNT_NAME}"
    rf"|\bnot\s+using\s+(?:the\s+|a\s+)?{_HUNT_NAME}"
    rf"|\b(?:do\s*n'?t|do\s+not|dont|never)\s+(?:run\s+)?(?:another\s+)?loop\s+to\s+fix\s+bugs)"
)
_STOP_REQUEST = re.compile(
    rf"(?i)(?:\b(?:stop|quit|cancel|abort|pause|halt|skip|disable|kill)\s+"
    rf"(?:the\s+|this\s+|that\s+|a\s+)?{_HUNT_NAME}"
    rf"|(?<!to[\s-])\bend\s+(?:the\s+|this\s+|that\s+|a\s+)?{_HUNT_NAME}"
    rf"|\b(?:wait\s+for|turn\s+off)\s+(?:the\s+|this\s+|that\s+|a\s+)?{_HUNT_NAME})"
)
_REVIEW_ONLY = re.compile(
    r"(?i)^\s*(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?"
    r"(?:review|check|look\s+(?:at|over)|audit|go\s+over|read|examine|"
    r"summarize|summarise|describe|explain|tell\s+me\s+about|walk\s+me\s+through|analyze|analyse|"
    r"inspect|fix\s+(?:the|those|these|this)\s+bugs?\s+in)\b"
)
_REVIEW_OF_HUNT = re.compile(
    r"(?i)\bbug\s+code\s+review\b"
    r"|\b(?:review|audit|explain|summarize|summarise)\b.{0,80}?\b"
    r"(?:bu[gn]g?\s*-?\s*hun(?:t(?:s|ing)?)?|bughunt)\b"
)
_EXPLICIT_START = re.compile(
    rf"(?i)\b(?:run|start|begin|launch|perform|do|execute)\s+"
    rf"(?:the\s+|a\s+|another\s+|this\s+|an\s+)?{_HUNT_NAME}"
    rf"|\b(?:run|start|begin|launch|perform|do|execute)\s+(?:another\s+)?loop\s+to\s+fix\s+bugs"
)
_EXPLICIT_START_NEGATED = re.compile(
    r"(?i)(?:\b(?:not|never)\b|n't)(?:\s+\w+){0,3}\s*$"
)


def _explicit_start_state(raw: str) -> str:
    """`start` when a start verb governs the hunt, `negated` when one was cancelled."""
    saw_negated = False
    for match in _EXPLICIT_START.finditer(raw):
        if _EXPLICIT_START_NEGATED.search(raw[: match.start()]):
            saw_negated = True
            continue
        return "start"
    return "negated" if saw_negated else "none"


_REVIEW_THEN_START = re.compile(
    r"(?i)\b(?:then|and)\s+(?:run|start|begin|perform|do|execute)\b.{0,40}?"
    r"(?:bu[gn]g?\s*-?\s*hun|bughunt|hunt(?:ing)?\s+for\s+bugs|loop\s+to\s+fix\s+bugs)"
)
_ABOUT_HUNT = re.compile(
    r"(?i)^\s*(?:the|this|that|our|your)\s+bu[gn]g?\s*-?\s*hun"
)
_HUNT_BUGS = re.compile(
    r"(?i)\bhunt(?:ing)?(?:\s+(?:for|some|those|these|more|any|the))*\s+bugs?\b"
)
_LOOP_FIX_BUGS = re.compile(
    r"(?i)\b(?:run\s+)?(?:another\s+)?loop\s+to\s+fix\s+bugs\b"
)
_BUG_HUNT = re.compile(r"(?i)\bbu(?:g|ng|n)?\s*-?\s*hun(?:t(?:s|ing)?)?\b")
_SLASH = re.compile(r"(?i)(?:^|\s)/bug-?hunt\b")
_COMPOUND = re.compile(r"(?i)\bbughunt\b")
_ENABLED_QUESTION = re.compile(
    r"(?i)\b(?:is|whether)\b.{0,80}\b(?:enabled|installed)\b"
)


class BugHuntError(Exception):
    """Bug-hunt install failed."""


@dataclass
class BugHuntInstall:
    root: Path
    iterations: int
    command_path: Path
    rule_path: Path
    packet_path: Path
    pause_seconds: int = DEFAULT_PAUSE_SECONDS
    files_written: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "iterations": self.iterations,
            "pause_seconds": self.pause_seconds,
            "command": str(COMMAND_REL).replace("\\", "/"),
            "rule": str(RULE_REL).replace("\\", "/"),
            "packet": str(PACKET_REL).replace("\\", "/"),
            "scripts": str(SCRIPTS_REL).replace("\\", "/"),
            "overlay": str(OVERLAY_REL).replace("\\", "/"),
            "files_written": list(self.files_written),
        }


def validate_iterations(iterations: int) -> int:
    if not isinstance(iterations, int) or isinstance(iterations, bool):
        raise BugHuntError(f"iterations must be an integer, got {iterations!r}")
    if iterations < MIN_ITERATIONS or iterations > MAX_ITERATIONS:
        raise BugHuntError(
            f"iterations must be between {MIN_ITERATIONS} and {MAX_ITERATIONS}, got {iterations}"
        )
    return iterations


def parse_iterations(raw: str | None) -> int:
    text = str(raw or "").strip()
    if not text:
        return DEFAULT_ITERATIONS
    try:
        value = int(text)
    except ValueError:
        try:
            number = float(text)
        except ValueError as exc:
            raise BugHuntError("iterations must be a whole number") from exc
        if not number.is_integer():
            raise BugHuntError("iterations must be a whole number")
        value = int(number)
    return validate_iterations(value)


def validate_pause_seconds(pause: int | None) -> int:
    """Blank means 10 seconds. Zero skips the wait. Any other whole number is the wait."""
    from hive_planner.bug_hunt_continue import MAX_SLEEP_SECONDS

    if pause is None:
        return DEFAULT_PAUSE_SECONDS
    if isinstance(pause, bool) or not isinstance(pause, int):
        raise BugHuntError(f"pause seconds must be a whole number, got {pause!r}")
    if pause < 0:
        raise BugHuntError(f"pause seconds must be 0 or greater, got {pause}")
    if pause > MAX_SLEEP_SECONDS:
        raise BugHuntError(
            f"pause seconds must be {MAX_SLEEP_SECONDS} or less, got {pause}"
        )
    return pause


def parse_pause_seconds(raw: str | None) -> int:
    text = str(raw or "").strip()
    if not text:
        return DEFAULT_PAUSE_SECONDS
    try:
        value = int(text)
    except ValueError:
        try:
            number = float(text)
        except ValueError as exc:
            raise BugHuntError("pause seconds must be a whole number") from exc
        if not number.is_integer():
            raise BugHuntError("pause seconds must be a whole number")
        value = int(number)
    return validate_pause_seconds(value)


def is_bug_hunt_request(text: str) -> bool:
    """True when chat text asks to run a hunt, not when it asks how the command works."""
    if not text or not str(text).strip():
        return False
    raw = str(text).strip()
    has_signal = bool(
        _SLASH.search(raw)
        or _COMPOUND.search(raw)
        or _BUG_HUNT.search(raw)
        or _HUNT_BUGS.search(raw)
        or _LOOP_FIX_BUGS.search(raw)
    )
    if not has_signal:
        return False
    if _COMMAND_QUESTION.search(raw) or _DOCS_QUESTION.search(raw):
        return False
    if _ENABLED_QUESTION.search(raw):
        return False
    # A real start survives a review mention or "not using the bug hunt" later
    # in the same message. Those phrases still reject a message that never starts.
    start_state = _explicit_start_state(raw)
    if start_state == "negated":
        return False
    if start_state != "start" and (_NEGATED_START.search(raw) or _STOP_REQUEST.search(raw)):
        return False
    if (
        start_state != "start"
        and (_REVIEW_ONLY.search(raw) or _REVIEW_OF_HUNT.search(raw))
        and not _REVIEW_THEN_START.search(raw)
    ):
        return False
    if _ABOUT_HUNT.search(raw) and not raw.rstrip().endswith("?"):
        # A sentence about a hunt ("the bug hunts of yesterday") is not a start signal.
        if re.search(
            r"(?i)\b(?:of|was|were|is|did|went|stopped|finished)\b",
            raw,
        ):
            return False
    return True


def resolve_bug_hunt_root(root: Path) -> Path:
    """Directory that receives hunt files. Workspace files resolve to their folder."""
    target = Path(root).resolve()
    if target.is_file() and target.suffix.lower() == ".code-workspace":
        from hive_planner.launcher.service import resolve_linked_project_root

        folder = resolve_linked_project_root(target)
        if folder is None:
            raise BugHuntError(f"workspace has no folder on disk: {target}")
        target = folder
    if not target.is_dir():
        raise BugHuntError(f"repo root is not a directory: {target}")
    return target


def _read_overlay_text(path: Path) -> str:
    """Read a bug-hunt overlay saved as UTF-8 (with or without BOM) or UTF-16.

    UTF-16 LE without a byte-order mark is still the overlay. Those bytes are
    valid UTF-8 because the extra bytes are NULs, so the installed command
    used to contain a null between every character.
    """
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    elif b"\x00" not in raw:
        return raw.decode("utf-8-sig")
    else:
        try:
            text = raw.decode("utf-16-le")
        except UnicodeDecodeError:
            return raw.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read_repo_overlay(root: Path) -> str:
    path = Path(root) / OVERLAY_REL
    if not path.is_file():
        return ""
    try:
        text = _read_overlay_text(path).strip()
    except (OSError, UnicodeError):
        return ""
    return f"\n{text}\n" if text else ""


def _prompt_options(root: Path) -> tuple[bool, str]:
    try:
        target = resolve_bug_hunt_root(root)
    except BugHuntError:
        target = Path(root).resolve()
    return (target / DUAL_LANE_REL).is_file(), _read_repo_overlay(target)


def preview_agent_prompt(
    root: Path,
    iterations: int = DEFAULT_ITERATIONS,
    pause_seconds: int | None = None,
) -> str:
    """Same script text install would write (overlay + dual-lane), without writing files."""
    dual_lane, overlay = _prompt_options(root)
    return render_agent_prompt(
        iterations,
        pause_seconds=pause_seconds,
        dual_lane=dual_lane,
        overlay=overlay,
    )


render_prompt_for_root = preview_agent_prompt


def _pause_section(seconds: int, count: int) -> str:
    if seconds == 0:
        wait = "This run's pause is 0 seconds, so do not wait between passes. The stop hook does not wait."
        sequence = (
            "The hook appends the rank row, then sets active to false, then starts the next inference pass."
        )
    else:
        wait = (
            f"This run's pause is {seconds} seconds. That wait is not skippable. "
            f"The stop hook waits {seconds} seconds."
        )
        sequence = (
            "The hook waits, then appends the rank row, then sets active to false, "
            "then starts the next inference pass."
        )
    return (
        "Each iteration is its own inference pass. "
        f"{wait} "
        "After you write `.hive/bug-hunt/continue.json` with `file`, `scenario`, `outcome`, and these keys, end this turn: "
        f'"active" true, "pause_seconds" {seconds}, "ceiling" {count}, '
        '"committed" the number of committed fixes this hunt has made so far, and '
        '"consecutive_empty" the current run of empty outcomes in a row. '
        "A committed, skipped, or review-failed outcome resets consecutive_empty to 0. "
        "Valid JSON only — no placeholders, no comments. "
        "The hook also stops on those counters, so a pass that ended mid-write does not restart. "
        "Do not start the next bug in this pass. Do not ask the user whether to continue. "
        f"{sequence} "
        "Active false at the start of a pass means the token was used, not that the hunt is over. "
        "Do the iteration. Ending the turn does not stop the hunt when you wrote active true. "
        "When a stop condition is met, write the same file with "
        '"active" false instead. '
        "The hook still appends that pass's rank row first, then will not start another pass."
    )


def _slope_text(value: float) -> str:
    text = f"{value:.4f}"
    if text in {"0.0000", "-0.0000"}:
        return "0.0"
    return text


def render_agent_prompt(
    iterations: int = DEFAULT_ITERATIONS,
    *,
    pause_seconds: int | None = None,
    dual_lane: bool = False,
    overlay: str = "",
) -> str:
    """The bug-hunt script. One iteration is one inference pass, then the run's pause."""
    count = validate_iterations(iterations)
    pause = validate_pause_seconds(pause_seconds)
    pause_text = _pause_section(pause, count)
    s0, s1, s2, s3, s4, s5 = (_slope_text(value) for value in INITIAL_SLOPES)
    base = f"""Stop after two consecutive empty searches, or when no unopened location still qualifies. A record-and-skip is not an empty search. A committed, skipped, or review-failed outcome resets the empty-search count. {count} committed fixes is the ceiling, not a quota. Until a stop condition is met, deep-dive into code logic and functional issues, apply a fix, self-review, commit locally when that review passes, and repeat across separate inference passes.

{pause_text} This ceiling counts committed fixes, not inference passes.

## Where to look

Rank locations before editing. Open the first file in `.hive/bug-hunt/rank-pass.json` that this run has not already opened. One location per iteration. Qualifying means any of the six signals or a detector finding. The ranker has no probability floor. The ranker chooses the queue only. It does not write the patch, choose the commit message, or override the stop rule.

The continue hook rebuilds the six weights, detector trust, and per-folder place attention from `.hive/bug-hunt/rank-rows.jsonl` and scores the unopened files before the pass it starts. A bug-hunt request writes that same queue before the first pass. Open the first file in `.hive/bug-hunt/rank-pass.json`. Do not rebuild the weights yourself. The seed, which a later rebuild starts from, is log1p of recent bug-fix commits × {s0}, a failing or thin test counted once × {s1}, a wiring hop with no call site (UI or event → handler → persisted or rendered result) × {s2}, a setting or flag with no reader × {s3}, a reverted commit × {s4}, two stores for one fact × {s5}. Twenty imaginary votes start on that seed and halve for every forty voted rows of that posterior. They are not added back at full strength. A skipped row casts no vote. Voted rows decay by 0.9 in file order: the newest voted row is one full vote, and each step older multiplies by 0.9. A committed or review-failed row pulls the weights toward that file's signals. An empty row pulls them away. Each pass draws one six-weight sample, one trust sample, and one place sample per candidate folder from a bell curve around those rebuilt means, mixes them, and does not store the draws. Trust starts at 1.0 and votes only on finding files. Place starts at 0.0 per first-path folder. Residual mismatch on stored row scores widens the next bells. About 400 rows from one process is when a recovery is trustworthy. That count does not install a new fixed set and does not freeze the update. Do not fit a logistic regression. Findings are not a seventh six-signal weight and not a fixed bonus. Finding count then line count break remaining ties. The queue keeps the top 50 scored files.

A logic error still qualifies. The ranker has no probability floor. Count a wrong boolean, an inverted condition, an off-by-one bound, a caught error reported as success, or a count that drops or double-counts an item. That signal is qualifying.

One row per opened location, written once, after the outcome is known: file, signals, scenario, outcome (`committed`, `skipped`, `empty`, or `review-failed`), findings, and score. The hook appends that row to `.hive/bug-hunt/rank-rows.jsonl` from the `file`, `scenario`, and `outcome` keys on `.hive/bug-hunt/continue.json`, copying findings and score from that file's `.hive/bug-hunt/rank-pass.json` row along with the signals it scored. Do not append the row yourself. Do not append a second row for the same location in this run. A later hunt may append a new row for that location. Rows from earlier hunts are votes for the next rebuild. An unopened location is not an empty search. The location model treats `committed` and `review-failed` as pulls toward that file's signals. An `empty` row pulls them away. A `skipped` row casts no vote. The classifier treats `committed` and `review-failed` as a real bug.

The hook marks this run's opened set in `.hive/bug-hunt/rank-pass.json` and the queue excludes it. A hunt starts after `active` was written false for a stop condition, and its opened set begins empty. Rows from earlier hunts do not close a location.

## Each iteration

1. Review the next ranked location for a bug you can fix this iteration. A bug qualifies when the code, given a concrete action and state, produces a wrong result.
   - Confirmed: it fails on a path the user can hit now. Wrong result, a throw, a skipped link (UI or event never reaches the handler), success reported when a required step was skipped, or a dead setting.
   - Potential: it has not failed in this session, but you can name the action, the state, and the wrong outcome, and that outcome follows from the code as written. Count these: two readers of the same fact disagree (a live value versus a cache, a remembered path versus the folder the other app polls); a first observation swallows a later event; success is returned before a required step; a value that must be per host, per project, or per file is shared; a stamp, flag, or fingerprint sticks and changes the next run.
   Skip style nits, drive-by refactors, and a guard that does not change a result. "I did not reproduce it this session" is not a reason to skip a potential bug that meets that bar.
2. Classify the named scenario before editing. A confirmed bug that meets the step 1 bar is **fix**, including when the harness is missing. The missing harness is handled at review, not by skipping the edit. A potential bug that needs a product decision, touches a secret, or has no harness is **record-and-skip** before any edit. Any other potential bug is **fix**. Style, complexity, or a scenario the code does not produce is **empty**. Fit a classifier only after at least 30 completed rows in `.hive/bug-hunt/rank-rows.jsonl`, and only when those rows include at least one real-bug outcome (`committed` or `review-failed`) and one other outcome. Otherwise use the rules above and do not invent a probability. When it is fit, it may score P(real bug): at least 0.65 means **fix**, from 0.35 up to 0.65 means **record-and-skip**, below 0.35 means **empty**. That score must not move a confirmed bug off **fix**, and it must not move a potential-bug secret, product decision, or missing harness off **record-and-skip**. The class gates step 3. It does not write the patch.
3. Apply the smallest fix that closes that failure when the class is fix. Follow this repo's theme, connectivity, and validation rules when the change touches them. On record-and-skip or empty, do not edit and do not run the self-review.
4. When a patch exists, self-review it before committing. Do not commit the first draft. This review is not a wait between passes, including when the pause is 0. Finish the review, then choose the outcome. Simulate the user-visible behavior this code already had, including behavior the patch was not meant to change. Walk the call chain from the action that used to work through every function the patch edits, using the same inputs that used to succeed. Example: creating extra command-strip tabs must still show the overflow slider; a follow-up layout pass must not hide it. The review fails if the patch removes, skips, caches off, or permanently replaces that behavior. Rank which tests to run from past diffs that touched the same files and which tests failed. Run the top of that list. The ranker orders the harness. It does not pass this review. The review passes only when all of these hold:
   - The change matches the failure you named.
   - The simulation shows the previous behavior still happens on the path that used to perform it.
   - A test or contract covers the fix when this repo has a harness for that layer, and covers the behavior you had to keep.
   - Wiring audit: the chain from the user-visible action to the handler and the persisted or rendered result is actually called.
   - The commit contains only this fix. Unrelated uncommitted lines in the same file stay in the working tree and stay out of the commit.
5. Choose exactly one outcome, in this order. A **record-and-skip**, a product decision, or a secret does not commit. If that case has a patch, restore only this iteration's uncommitted edits. The outcome is `skipped`, including when the review also fails or the patch cannot be covered. Otherwise an **empty** class does not commit. If that case has edits, restore only this iteration's uncommitted edits. The outcome is `empty`. Otherwise if the review fails, or the patch cannot be covered, restore only this iteration's uncommitted edits and do not commit. The outcome is `review-failed`. Otherwise commit locally with a message that says why. If every touched file differs from HEAD only by this fix, stage those files and commit them. If a touched file also has uncommitted lines that are not this fix, do not stage that mix and do not stash the repository. Before editing, copy each such file to `.hive/bug-hunt/isolate/` (write an empty snapshot when the file did not exist). After the review passes, commit only this fix by running `py -3.11 -m hive_planner bug-hunt-commit --message "<why>" --snapshot <repo-relative-path>=<snapshot-path>`. Repeat `--snapshot` once per file. The command merges this iteration's edit onto HEAD, commits that result alone, and writes the pre-commit working tree back so the unrelated lines remain uncommitted. It does not stage or stash any other path, so another hunt on another file is left in place. When that commit exists and contains only this fix, the outcome is `committed`. When the command cannot separate the fix from those lines, it does not commit. Restore nothing it already restored, and use `review-failed`. If that commit fails, restore only this iteration's uncommitted edits and use `review-failed` instead. A failed review is not an empty search. It is `skipped` only when this step already chose `skipped`. Every other failed review is `review-failed`. Do not push, open a pull request, or upload to a remote.
6. Write `.hive/bug-hunt/continue.json` as the pause section says, and include `file` (the path you opened), `scenario`, and `outcome`. The hook appends the rank row from those keys and the signals it scored. Do not append `.hive/bug-hunt/rank-rows.jsonl` yourself. Set active true when the hunt should continue, active false when a stop condition is met. If this pass began with active false, that only means the hook already used the previous token. End this turn. Do not start the next iteration in this pass. Do not ask the user whether to continue. The stop hook waits the pause (0 means it does not wait) and starts the next inference pass when you wrote active true. An empty search is an opened location classified **empty**, or an opened location with neither a confirmed bug nor a potential bug. Record-and-skip is not an empty search. A committed, skipped, or review-failed outcome resets the empty-search count. Drop the location from the queue. That outcome is the one written to `.hive/bug-hunt/rank-rows.jsonl`.

## Stop

Stop after {count} committed fixes, after two consecutive empty searches, or when no unopened location still qualifies. Qualifying means any of the six signals or a detector finding. The ranker has no probability floor. Two consecutive empty searches means two empty outcomes in a row. A committed, skipped, or review-failed outcome resets that count. Report the commits, what each one fixed (confirmed or potential, and the scenario), anything you recorded and skipped, and any opened location that had neither a confirmed bug nor a potential bug. Do not invent a scenario the code does not actually produce. Do not push.
"""
    extra = ""
    if dual_lane:
        extra += """
## This repo - dual-lane (phone + Z Fold)

- Prefer **universal** fixes in shared layers (`services/search`, `core:data`, shared UI). Only touch fold shell for selection / two-pane / cover-to-unfold / width.
- Classify each committed fix: `universal` | `phone-wiring` | `fold-wiring`.
- One location per iteration still holds. Self-review and commit that one fix, then end the turn. Do not start a second bug in this pass.
- Automated gate when possible: `services/search` pytest, Android unit tests, root pytest, `hive_planner ci-check`.
- Do not mark a hunt cycle release-ready if nav/fold wiring changed and only one device lane was exercised.
"""
    if overlay:
        extra += overlay if overlay.startswith("\n") else f"\n{overlay}\n"
    return base + extra


def render_cursor_rule() -> str:
    """Always-on trigger so a chat request to hunt bugs starts the installed script."""
    listed = ", ".join(f'"{p}"' for p in TRIGGER_PHRASES)
    return f"""---
description: Start the bug-hunt loop when the user asks to hunt bugs in any chat in this repo
alwaysApply: true
---

# Bug hunt trigger

When the user asks to run a bug hunt in any chat on this repo — the message is or clearly requests a bug hunt, including typos and derivatives such as {listed} — read `.cursor/commands/bug-hunt.md` and do one iteration of that script in this turn, then end the turn. If that file is missing, read `scripts/bug-hunt.md`. One iteration is one inference pass. Write the continue file named in that script (`file`, `scenario`, `outcome`, pause, ceiling, committed, consecutive_empty) and end the turn. The stop hook appends the rank row from that continue file. The stop hook waits the script's pause: a positive number of seconds is not skippable, and 0 means it does not wait. Then the hook starts the next inference pass. Do not ask the user to continue. Do not stop after one bug by starting the next bug in this same turn. End the turn after the iteration. The hook starts the next pass unless a stop condition in the script is met. Do not reply with instructions for how to invoke the command.

Match intent, not only an exact string: "please hunt for bugs", "start hunting bugs", "run a bug-hunt", or "/bug-hunt" are start signals. A question about the command itself (whether it works, where the file is, how to install it) is not a start signal. A request to stop, cancel, pause, skip, disable, or wait for the hunt is not a start signal. A request to review, summarize, audit, or explain the bug hunt script is not a start signal. "end to end bug hunt" and a start after another clause ("stop explaining and run a bug hunt") are start signals.
"""


def render_cursor_command(
    iterations: int = DEFAULT_ITERATIONS,
    *,
    pause_seconds: int | None = None,
    dual_lane: bool = False,
    overlay: str = "",
) -> str:
    count = validate_iterations(iterations)
    body = render_agent_prompt(
        count,
        pause_seconds=pause_seconds,
        dual_lane=dual_lane,
        overlay=overlay,
    )
    return (
        "---\n"
        "description: Continuous bug hunt (bug hunt, bug hun, bung hunt, do a bug hunt) — "
        "find, fix, self-review, commit locally, repeat.\n"
        "---\n\n"
        f"{body}"
    )


def _write_if_needed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    normalized = content.replace("\r\n", "\n")
    if path.is_file():
        try:
            current = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeDecodeError):
            current = None
        if current == normalized:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(normalized, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return True


def missing_bug_hunt_artifacts(root: Path) -> list[str]:
    """Relative paths that must exist after a successful install."""
    try:
        target = resolve_bug_hunt_root(root)
    except BugHuntError:
        target = Path(root).resolve()
    missing: list[str] = []
    for rel in (COMMAND_REL, RULE_REL, PACKET_REL, SCRIPTS_REL, CONTINUE_HOOK_REL):
        if not (target / rel).is_file():
            missing.append(rel.as_posix())
    for event in ("stop", "beforeSubmitPrompt"):
        if not _continue_hook_registered(target, event):
            missing.append(f"{HOOKS_JSON_REL.as_posix()}#{event}:{CONTINUE_HOOK_COMMAND}")
    return missing


def render_continue_hook() -> str:
    """Standalone stop-hook source. Same file the package runs."""
    candidates = [Path(__file__).with_name("bug_hunt_continue.py")]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "hive_planner" / "bug_hunt_continue.py")
    for source in candidates:
        if source.is_file():
            return source.read_text(encoding="utf-8")
    raise BugHuntError(
        "Bug hunt continue hook is not in this Hive Planner build "
        f"({candidates[0]}). Rebuild the portable app so that file is packaged."
    )


def _read_hooks_json_text(path: Path) -> str:
    """Read hooks.json saved as UTF-8 (with or without BOM) or UTF-16.

    UTF-16 LE without a byte-order mark decodes as UTF-8 with a null between
    every character, so install used to refuse a file Cursor had saved that way.
    """
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    text = raw.decode("utf-8-sig")
    if "\x00" not in text:
        return text
    try:
        return raw.decode("utf-16-le")
    except UnicodeError:
        return text


def _hooks_json_is_plain_utf8(path: Path) -> bool:
    """True when Cursor can JSON.parse the file (UTF-8, no BOM)."""
    raw = path.read_bytes()
    if raw.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")):
        return False
    if b"\x00" in raw:
        return False
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _continue_hook_registered(root: Path, event: str = "stop") -> bool:
    path = Path(root) / HOOKS_JSON_REL
    if not path.is_file():
        return False
    if not _hooks_json_is_plain_utf8(path):
        return False
    try:
        data = json.loads(_read_hooks_json_text(path))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    hooks = data.get("hooks") if isinstance(data, dict) else None
    items = hooks.get(event) if isinstance(hooks, dict) else None
    if not isinstance(items, list):
        return False
    return any(
        isinstance(item, dict) and item.get("command") == CONTINUE_HOOK_COMMAND for item in items
    )


def _hooks_document(root: Path) -> dict:
    """Parse hooks.json. A broken file raises before any install write."""
    path = Path(root) / HOOKS_JSON_REL
    if path.is_file():
        try:
            data = json.loads(_read_hooks_json_text(path))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BugHuntError(f"existing hooks.json is not valid JSON: {path}") from exc
    else:
        data = {"version": 1, "hooks": {}}
    if not isinstance(data, dict):
        raise BugHuntError(f"existing hooks.json is not a JSON object: {path}")
    return data


def continue_hook_loop_limit(iterations: int = DEFAULT_ITERATIONS) -> int:
    """Passes the stop hook may chain. Skips do not count toward the fix ceiling.

    The default ceiling of 50 keeps a 160-pass spare (210 total). Doubling the
    ceiling and then taking max(210, that) shrinks the spare to almost nothing
    once the ceiling passes 105.
    """
    count = validate_iterations(iterations)
    spare = CONTINUE_HOOK_LOOP_LIMIT - DEFAULT_ITERATIONS
    return max(CONTINUE_HOOK_LOOP_LIMIT, count + spare)


def _raise_prompt_rank_timeout(prompt_hooks: list) -> bool:
    """Give the first-pass queue the same budget as the stop hook. True when a timeout changed."""
    raised = False
    for item in prompt_hooks:
        if not isinstance(item, dict) or item.get("command") != CONTINUE_HOOK_COMMAND:
            continue
        current = item.get("timeout")
        if not isinstance(current, int) or isinstance(current, bool) or current < CONTINUE_HOOK_TIMEOUT:
            item["timeout"] = CONTINUE_HOOK_TIMEOUT
            raised = True
    return raised


def ensure_continue_hook(
    root: Path,
    *,
    pause_seconds: int = 0,
    iterations: int = DEFAULT_ITERATIONS,
) -> bool:
    """Add the bug-hunt stop hook without removing other hook events. True if the file changed."""
    path = Path(root) / HOOKS_JSON_REL
    data = _hooks_document(root)
    data.setdefault("version", 1)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    stop = hooks.get("stop")
    if not isinstance(stop, list):
        stop = []
        hooks["stop"] = stop
    prompt_hooks = hooks.get("beforeSubmitPrompt")
    if not isinstance(prompt_hooks, list):
        prompt_hooks = []
        hooks["beforeSubmitPrompt"] = prompt_hooks
    prompt_missing = not any(
        isinstance(item, dict) and item.get("command") == CONTINUE_HOOK_COMMAND for item in prompt_hooks
    )
    needed_timeout = max(CONTINUE_HOOK_TIMEOUT, max(0, pause_seconds) + 30)
    needed_limit = continue_hook_loop_limit(iterations)
    entry = {
        "command": CONTINUE_HOOK_COMMAND,
        "timeout": needed_timeout,
        "loop_limit": needed_limit,
    }
    for item in stop:
        if isinstance(item, dict) and item.get("command") == CONTINUE_HOOK_COMMAND:
            changed = False
            current = item.get("timeout")
            if not isinstance(current, int) or isinstance(current, bool) or current < needed_timeout:
                item["timeout"] = needed_timeout
                changed = True
            current_limit = item.get("loop_limit")
            # A reinstall must not shrink the chain an active hunt is already using.
            if (
                not isinstance(current_limit, int)
                or isinstance(current_limit, bool)
                or current_limit < needed_limit
            ):
                item["loop_limit"] = needed_limit
                changed = True
            if not changed:
                if prompt_missing:
                    prompt_hooks.append({"command": CONTINUE_HOOK_COMMAND, "timeout": CONTINUE_HOOK_TIMEOUT})
                    changed = True
                elif _raise_prompt_rank_timeout(prompt_hooks):
                    changed = True
                if not changed and _hooks_json_is_plain_utf8(path):
                    return False
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(path.name + ".tmp")
                tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
                tmp.replace(path)
                return True
            if prompt_missing:
                prompt_hooks.append({"command": CONTINUE_HOOK_COMMAND, "timeout": CONTINUE_HOOK_TIMEOUT})
            else:
                _raise_prompt_rank_timeout(prompt_hooks)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
            tmp.replace(path)
            return True
    stop.append(entry)
    if prompt_missing:
        prompt_hooks.append({"command": CONTINUE_HOOK_COMMAND, "timeout": CONTINUE_HOOK_TIMEOUT})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)
    return True


def install_bug_hunt(
    root: Path,
    iterations: int = DEFAULT_ITERATIONS,
    *,
    pause_seconds: int | None = None,
    force: bool = True,
) -> BugHuntInstall:
    count = validate_iterations(iterations)
    pause = validate_pause_seconds(pause_seconds)
    target = resolve_bug_hunt_root(root)
    _hooks_document(target)

    dual_lane, overlay = _prompt_options(target)
    prompt = render_agent_prompt(
        count,
        pause_seconds=pause,
        dual_lane=dual_lane,
        overlay=overlay,
    )
    command_path = target / COMMAND_REL
    rule_path = target / RULE_REL
    packet_path = target / PACKET_REL
    scripts_path = target / SCRIPTS_REL
    written: list[str] = []
    pairs = (
        (
            command_path,
            render_cursor_command(count, pause_seconds=pause, dual_lane=dual_lane, overlay=overlay),
            COMMAND_REL,
        ),
        (rule_path, render_cursor_rule(), RULE_REL),
        (packet_path, prompt, PACKET_REL),
        (scripts_path, prompt, SCRIPTS_REL),
    )
    for path, content, rel in pairs:
        if _write_if_needed(path, content, force=force):
            written.append(rel.as_posix())
    hook_path = target / CONTINUE_HOOK_REL
    if _write_if_needed(hook_path, render_continue_hook(), force=force):
        written.append(CONTINUE_HOOK_REL.as_posix())
    if ensure_continue_hook(target, pause_seconds=pause, iterations=count):
        written.append(HOOKS_JSON_REL.as_posix())
    return BugHuntInstall(
        root=target,
        iterations=count,
        pause_seconds=pause,
        command_path=command_path,
        rule_path=rule_path,
        packet_path=packet_path,
        files_written=written,
    )


def _repo_relative(root: Path, rel: str) -> str:
    """Repo-relative posix path. Rejects a path that leaves the repository."""
    candidate = (root / rel).resolve()
    base = root.resolve()
    if candidate != base and base not in candidate.parents:
        raise BugHuntError(f"snapshot path leaves the repository: {rel}")
    return candidate.relative_to(base).as_posix()


def _git_blob(root: Path, rel: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{rel}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _changed_spans(before: list[bytes], other: list[bytes]) -> list[tuple]:
    matcher = difflib.SequenceMatcher(a=before, b=other, autojunk=False)
    return [op for op in matcher.get_opcodes() if op[0] != "equal"]


def _spans_conflict(left: tuple, right: tuple) -> bool:
    """True when both sides edit the same lines, including two inserts at one point."""
    if left[1] == left[2] == right[1] == right[2]:
        return True
    return left[1] < right[2] and right[1] < left[2]


def _as_lf(data: bytes) -> bytes:
    """Compare and merge in LF so a CRLF working tree does not look like a full rewrite."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _match_newlines(merged_lf: bytes, style: bytes) -> bytes:
    if b"\r\n" in style:
        return merged_lf.replace(b"\n", b"\r\n")
    return merged_lf


def _merge_onto_head(head: bytes, before: bytes, after: bytes) -> bytes | None:
    """HEAD plus the before→after edit. None when that edit overlaps other changes."""
    head_bytes = b"" if head is None else head
    before_n = _as_lf(before)
    head_n = _as_lf(head_bytes)
    after_n = _as_lf(after)
    if before_n == head_n:
        merged = after_n
    else:
        merged = _merge_lf_lines(head_n, before_n, after_n)
        if merged is None:
            return None
    style = after if head is None else head_bytes
    return _match_newlines(merged, style)


def _merge_lf_lines(head_n: bytes, before_n: bytes, after_n: bytes) -> bytes | None:
    before_lines = before_n.splitlines(keepends=True)
    head_lines = head_n.splitlines(keepends=True)
    after_lines = after_n.splitlines(keepends=True)
    head_ops = _changed_spans(before_lines, head_lines)
    fix_ops = _changed_spans(before_lines, after_lines)
    for head_op in head_ops:
        for fix_op in fix_ops:
            if _spans_conflict(head_op, fix_op):
                return None
    chosen = [(op, head_lines) for op in head_ops] + [(op, after_lines) for op in fix_ops]
    chosen.sort(key=lambda item: (item[0][1], item[0][2]))
    merged: list[bytes] = []
    index = 0
    for op, source in chosen:
        _tag, start, end, new_start, new_end = op
        merged.extend(before_lines[index:start])
        merged.extend(source[new_start:new_end])
        index = end
    merged.extend(before_lines[index:])
    return b"".join(merged)


def _acquire_commit_lock(root: Path) -> Path | None:
    """One isolate commit at a time so two hunts cannot drop each other's files."""
    lock = root / ".hive" / "bug-hunt" / "commit.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + 60
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 0
            if age > 120:
                stolen = lock.with_name(f"{lock.name}.steal-{os.getpid()}")
                try:
                    os.replace(lock, stolen)
                except OSError:
                    time.sleep(0.05)
                    continue
                try:
                    stolen.unlink()
                except OSError:
                    pass
                continue
            if time.time() > deadline:
                return None
            time.sleep(0.05)
            continue
        os.close(fd)
        return lock


def commit_isolated_fix(
    root: Path,
    *,
    message: str,
    snapshots: dict[str, Path],
) -> dict:
    """Commit this iteration's edit and leave unrelated lines in the working tree.

    Each snapshot is the file as it was before this iteration edited it. The
    working tree is the file after the edit. The commit is HEAD plus that
    edit. Other paths are not staged and the stash is not used.
    """
    if not message.strip():
        raise BugHuntError("commit message is empty")
    if not snapshots:
        raise BugHuntError("no snapshot files were given")
    repo = root.resolve()
    prepared: list[tuple[str, bytes, bytes]] = []
    for rel, snapshot in snapshots.items():
        relative = _repo_relative(repo, rel)
        target = repo / relative
        if not target.is_file():
            raise BugHuntError(f"working tree file is missing: {relative}")
        if not snapshot.is_file():
            raise BugHuntError(f"snapshot is missing: {snapshot}")
        before = snapshot.read_bytes()
        after = target.read_bytes()
        if before == after:
            continue
        if _merge_onto_head(_git_blob(repo, relative), before, after) is None:
            return {
                "ok": False,
                "error": f"fix could not be separated from unrelated changes: {relative}",
            }
        prepared.append((relative, before, after))
    if not prepared:
        return {"ok": False, "error": "this iteration did not change the snapshot files"}
    lock = _acquire_commit_lock(repo)
    if lock is None:
        return {"ok": False, "error": "another isolate commit is still running"}
    index_path: Path | None = None
    try:
        fresh: list[tuple[str, bytes, bytes]] = []
        for relative, before, after in prepared:
            merged = _merge_onto_head(_git_blob(repo, relative), before, after)
            if merged is None:
                return {
                    "ok": False,
                    "error": f"fix could not be separated from unrelated changes: {relative}",
                }
            fresh.append((relative, merged, after))
        index_fd, index_name = tempfile.mkstemp(prefix="hive-bug-hunt-index-")
        os.close(index_fd)
        index_path = Path(index_name)
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(index_path)
        read_tree = subprocess.run(
            ["git", "read-tree", "HEAD"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if read_tree.returncode != 0:
            detail = (read_tree.stderr or read_tree.stdout).strip()
            return {"ok": False, "error": detail or "git read-tree failed"}
        for relative, merged, _after in fresh:
            (repo / relative).write_bytes(merged)
            added = subprocess.run(
                ["git", "add", "--", relative],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if added.returncode != 0:
                detail = (added.stderr or added.stdout).strip()
                return {"ok": False, "error": detail or f"git add failed: {relative}"}
        committed = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if committed.returncode != 0:
            detail = (committed.stderr or committed.stdout).strip()
            return {"ok": False, "error": detail or "git commit failed"}
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        # The commit used a private index. Point the real index at the new
        # blob for these paths only, so other staged files stay staged and
        # this file is not left staged as a revert of the commit.
        main_env = os.environ.copy()
        main_env.pop("GIT_INDEX_FILE", None)
        for relative, _merged, _after in fresh:
            listed = subprocess.run(
                ["git", "ls-tree", "HEAD", "--", relative],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            info = listed.stdout.strip().split()
            if listed.returncode != 0 or len(info) < 3:
                return {"ok": False, "error": f"could not read committed blob: {relative}"}
            mode, blob = info[0], info[2]
            updated = subprocess.run(
                ["git", "update-index", "--cacheinfo", f"{mode},{blob},{relative}"],
                cwd=repo,
                env=main_env,
                capture_output=True,
                text=True,
                check=False,
            )
            if updated.returncode != 0:
                detail = (updated.stderr or updated.stdout).strip()
                return {"ok": False, "error": detail or f"could not update the index: {relative}"}
        return {
            "ok": True,
            "commit": sha.stdout.strip(),
            "files": [relative for relative, _merged, _after in fresh],
        }
    finally:
        for relative, _before, after in prepared:
            (repo / relative).write_bytes(after)
        if index_path is not None:
            try:
                index_path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            lock.unlink()
        except OSError:
            pass
