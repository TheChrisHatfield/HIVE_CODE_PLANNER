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
import uuid
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
RECOVERY_REL = Path(".hive") / "bug-hunt" / "recovery.json"
CALIBRATION_REL = Path(".hive") / "bug-hunt" / "calibration.jsonl"
SLOPE_WINDOWS_REL = Path(".hive") / "bug-hunt" / "slope-windows.json"
PLACE_LOCAL_REL = Path(".hive") / "bug-hunt" / "place-local.json"
PLACE_PENDING_REL = Path(".hive") / "bug-hunt" / "place-local.pending.json"
DONORS_REL = Path(".hive") / "bug-hunt" / "donors.json"
WINDOW_VOTE_LIMIT = 200
_UNSTAMPED_CLOSED = "__unstamped__"
SIGNAL_KEYS = (
    "recent_fix_commits",
    "thin_test",
    "wiring_hop",
    "dead_setting",
    "reverted",
    "split_stores",
)
ANCHOR_VOTES = 20.0
# Real votes share the residual with this prior, not with the twenty width votes.
# One committed signal moves its slope by about one third of that signal.
RESIDUAL_PRIOR = 2.0
ANCHOR_HALFLIFE_ROWS = 40.0
ROW_DECAY = 0.9
CANDIDATE_FILE_LIMIT = 1200
QUEUE_LIMIT = 50
_PULL_OUTCOMES = frozenset({"committed", "review-failed"})
_PUSH_OUTCOMES = frozenset({"empty"})
TRUST_SEED = 1.0
PLACE_SEED = 0.0
SURPRISE_WINDOW = 10
EXPLORATION_CAP = 0.25
ATTRIBUTION_VERSION = 1
ATTRIBUTION_ROW_LIMIT = 4096
SUPPORTED_OVERRIDE_SUFFIXES = frozenset({".py", ".pyi", ".cs"})
RECOVERY_LENSES = (
    "ui-event",
    "configuration",
    "wiring",
    "persistence",
    "error-reporting",
    "test-contract",
)


def fix_commit_feature(count: float) -> float:
    """log1p of the fix-commit count. Zero returns 0. A negative count is refused."""
    try:
        value = float(count)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"fix-commit count must be numeric, got {count!r}") from exc
    if value < 0.0:
        raise ValueError(f"fix-commit count must be >= 0, got {count}")
    if not math.isfinite(value):
        return math.log(sys.float_info.max)
    feature = math.log1p(value)
    if not math.isfinite(feature):
        return math.log(sys.float_info.max)
    return feature


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
    try:
        features = [fix_commit_feature(signals[0]), *(float(value) for value in signals[1:])]
        total = sum(weight * feature for weight, feature in zip(weights, features))
    except (TypeError, OverflowError) as exc:
        raise ValueError("score_signals received a non-numeric signal or slope") from exc
    if not math.isfinite(total):
        return 0.0
    return total


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


# The six-signal mix, trust, and place stay in the score, but their sum is
# squashed into this range once bug likelihood is applied. A three-line file
# with a long fix history cannot outrun a larger defect surface.
ACTIVITY_CAP = 4.0
# Line, branch, and call mass saturate here. Past this, more raw size does not
# outrank a smaller file that has detector findings.
SURFACE_CAP = 4.0
# Missing-test step. A finding file must clear this plus both caps, because a
# clean file can sit just under the activity cap and the surface cap and still
# take this step.
UNTESTED_STEP = 1.0
# Same byte ceiling as the candidate walk. A saved row does not get a bigger read.
FILE_BYTE_CAP = 400_000

_BRANCH_LINE = re.compile(
    r"(?m)^[ \t]*(?:if|elif|else|for|while|except|finally|with|case|catch|switch)\b"
)
_CALL_SITE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_DEF_OR_CLASS = re.compile(r"(?m)^[ \t]*(?:async[ \t]+)?(?:def|class)\b")
_NOT_A_CALL = frozenset(
    {
        "if",
        "elif",
        "else",
        "for",
        "while",
        "except",
        "finally",
        "with",
        "case",
        "catch",
        "switch",
        "return",
        "yield",
        "assert",
        "raise",
        "await",
        "lambda",
        "and",
        "or",
        "not",
        "in",
        "is",
    }
)


def _activity_mix(six_score: float, findings: object, trust_draw: float, place_draw: float) -> float:
    bit = 1.0 if _finding_count(findings) > 0 else 0.0
    try:
        place = float(place_draw)
        if not math.isfinite(place) or place < 0.0:
            place = 0.0
        total = float(six_score) + float(trust_draw) * bit + place
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if math.isnan(total) or math.isinf(total):
        return 0.0
    return total


def _log1p_count(count: int) -> float:
    """log1p that stays finite. A huge count must not abort the place rescore."""
    try:
        value = math.log1p(count)
    except OverflowError:
        return math.log(sys.float_info.max)
    if not math.isfinite(value):
        return math.log(sys.float_info.max)
    return value


def _squash_open(value: float, cap: float) -> float:
    """Tanh into (-cap, cap). A float that saturates to the endpoint steps inside."""
    if math.isnan(value) or math.isinf(value) or cap <= 0:
        return 0.0
    squashed = cap * math.tanh(value / cap)
    if squashed >= cap:
        return math.nextafter(cap, 0.0)
    if squashed <= -cap:
        return math.nextafter(-cap, 0.0)
    return squashed


def _squash_activity(activity: float) -> float:
    """Map the activity mix into (-ACTIVITY_CAP, ACTIVITY_CAP). Order is kept."""
    return _squash_open(activity, ACTIVITY_CAP)


def _nonneg_count(value: object) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if math.isnan(number) or math.isinf(number) or number < 0:
        return 0.0
    return number


def _count_surface(source: str) -> tuple[int, int]:
    """Branch lines and call sites. These are bug-likelihood counts, not learned weights."""
    try:
        calls = 0
        for line in source.splitlines():
            names = [name for name in _CALL_SITE.findall(line) if name not in _NOT_A_CALL]
            if _DEF_OR_CLASS.match(line) and names:
                names = names[1:]
            calls += len(names)
        return len(_BRANCH_LINE.findall(source)), calls
    except (RecursionError, MemoryError):
        return 0, 0


def _is_test_rel(rel: str) -> bool:
    path = Path(rel)
    name = path.stem.lower()
    parts = [part.lower() for part in path.parts]
    return (
        name in {"test", "tests"}
        or name.startswith("test_")
        or name.endswith("_test")
        or "tests" in parts[:-1]
    )


def bug_likelihood(
    *,
    lines: object,
    branches: object,
    calls: object,
    findings: object,
    untested: bool,
) -> float:
    """Fixed defect-surface term. Not a seventh learned slope.

    Lines, branch lines, and call sites share one squashed surface so a long
    file cannot bury a smaller one that has findings. Findings stay outside
    that cap. A test file does not take the missing-test step.
    """
    surface = (
        math.log1p(_nonneg_count(lines))
        + math.log1p(_nonneg_count(branches))
        + 0.5 * math.log1p(_nonneg_count(calls))
    )
    if not math.isfinite(surface):
        surface = 0.0
    else:
        surface = _squash_open(surface, SURFACE_CAP)
    found = _finding_count(findings)
    # Activity lives in (-ACTIVITY_CAP, ACTIVITY_CAP). Surface is non-negative
    # and stays under SURFACE_CAP. One finding has to clear the whole activity
    # span, that surface cap, and the missing-test step.
    # Extra findings still add log1p.
    finding_step = (
        (2 * ACTIVITY_CAP) + SURFACE_CAP + UNTESTED_STEP if found else 0.0
    )
    total = surface + finding_step + _log1p_count(found) + (UNTESTED_STEP if untested else 0.0)
    if not math.isfinite(total):
        return 0.0
    return total


def _stored_likelihood(item: dict) -> float | None:
    """Finite likelihood already stored on a queue row. A missing key is not zero."""
    if "likelihood" not in item:
        return None
    value = item.get("likelihood")
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if math.isnan(number) or math.isinf(number) or number < 0:
        return None
    return number


def _path_inside_root(root: Path, rel: str) -> Path | None:
    """Repo file for a saved row. Absolute paths and `..` segments are not read."""
    if not rel or rel.startswith("/") or rel.startswith("\\"):
        return None
    parts = rel.split("/")
    if any(part == ".." or ":" in part for part in parts):
        return None
    try:
        path = (Path(root) / rel).resolve()
        path.relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return None
    return path


def _validated_override(root: Path, state: dict | None) -> tuple[str, str]:
    if not isinstance(state, dict) or not state.get("requested_file"):
        return "", ""
    raw = str(state.get("requested_file") or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or ":" in raw:
        return "", "requested_file must be a repository-relative source path"
    path = _path_inside_root(root, raw)
    if path is None:
        return "", "requested_file resolves outside the repository"
    if path.suffix.casefold() not in SUPPORTED_OVERRIDE_SUFFIXES:
        return "", "requested_file has an unsupported source type"
    if not path.is_file():
        return "", "requested_file does not exist or is not a file"
    requested_line = state.get("requested_line")
    if requested_line is not None:
        if isinstance(requested_line, bool):
            return "", "requested_line must be a positive integer"
        if isinstance(requested_line, float) and not requested_line.is_integer():
            return "", "requested_line must be a positive integer"
        try:
            line = int(requested_line)
        except (TypeError, ValueError, OverflowError):
            return "", "requested_line must be a positive integer"
        if line <= 0:
            return "", "requested_line must be a positive integer"
        try:
            line_count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except (OSError, UnicodeError, MemoryError, RecursionError):
            return "", "requested_file could not be read"
        if line_count <= 0 or line > line_count:
            return "", "requested_line is outside the file"
    return _norm_rel(raw), ""


def _stored_likelihood_matches(stored: float, findings: object) -> bool:
    """False when a saved likelihood cannot belong to the current finding step."""
    found = _finding_count(findings)
    floor = (2 * ACTIVITY_CAP) + SURFACE_CAP + UNTESTED_STEP
    if found:
        return stored + 1e-6 >= floor + _log1p_count(found)
    return stored < floor


def _likelihood_from_row(root: Path, item: dict) -> float:
    """Likelihood for a place rescore. An old row with no key is rebuilt from the file."""
    stored = _stored_likelihood(item)
    if stored is not None and _stored_likelihood_matches(stored, item.get("findings")):
        return stored
    rel = _norm_rel(str(item.get("file") or ""))
    lines = item.get("lines")
    findings = item.get("findings")
    branches = 0
    calls = 0
    path = _path_inside_root(root, rel)
    try:
        oversized = path is not None and path.is_file() and path.stat().st_size > FILE_BYTE_CAP
    except OSError:
        oversized = True
    if path is not None and path.is_file() and not oversized:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError, MemoryError, RecursionError):
            source = None
        if source is not None:
            branches, calls = _count_surface(source)
            lines = source.count("\n") + 1
    signals = item.get("signals")
    thin_value = 0.0
    if isinstance(signals, dict):
        try:
            thin_value = float(signals.get("thin_test", 0.0))
        except (TypeError, ValueError):
            thin_value = 0.0
    untested = math.isfinite(thin_value) and thin_value > 0 and not _is_test_rel(rel)
    return bug_likelihood(
        lines=lines,
        branches=branches,
        calls=calls,
        findings=findings,
        untested=untested,
    )


def rank_queue_score(
    six_score: float,
    findings: object,
    trust_draw: float = 0.0,
    place_draw: float = 0.0,
    likelihood: float | None = None,
) -> float:
    """Activity mix, plus bug likelihood when this pass supplies it.

    Omitting likelihood returns the raw mix, which is what the six-weight tests
    lock. The queue always passes likelihood and then squashes the mix into
    the open interval (-ACTIVITY_CAP, ACTIVITY_CAP) before adding that term.
    """
    activity = _activity_mix(six_score, findings, trust_draw, place_draw)
    if likelihood is None:
        return activity
    like = _nonneg_count(likelihood)
    blended = _squash_activity(activity) + like
    if math.isnan(blended) or math.isinf(blended):
        return 0.0
    return blended


def _posterior_uncertainty(evidence: object) -> float:
    try:
        value = float(evidence)
    except (TypeError, ValueError, OverflowError):
        value = 20.0
    if not math.isfinite(value) or value < 20.0:
        value = 20.0
    return min(1.0, math.sqrt(20.0 / value))


def _coverage_novelty(file_votes: object, place_votes: object) -> float:
    def novelty(value: object) -> float:
        try:
            count = max(0, int(value))
        except (TypeError, ValueError, OverflowError):
            count = 0
        return 1.0 / (1.0 + count)

    return (novelty(file_votes) + novelty(place_votes)) / 2.0


def exploration_bonus(
    evidence_six: object,
    evidence_trust: object,
    evidence_place: object,
    file_votes: object,
    place_votes: object,
) -> float:
    """Bounded uncertainty/coverage exploration term from the R10 contract."""
    uncertainty = (
        _posterior_uncertainty(evidence_six)
        + _posterior_uncertainty(evidence_trust)
        + _posterior_uncertainty(evidence_place)
    ) / 3.0
    bonus = EXPLORATION_CAP * uncertainty * _coverage_novelty(file_votes, place_votes)
    return bonus if math.isfinite(bonus) else 0.0


def _voted_rows_for(rows: list[dict], rel: str, folder: str) -> tuple[int, int]:
    file_key = _opened_key(rel)
    folder_key = str(folder or ".").casefold()
    file_votes = 0
    place_votes = 0
    for row in rows:
        if not isinstance(row, dict) or _outcome_sign(row) is None:
            continue
        row_file = _norm_rel(str(row.get("file") or ""))
        if _opened_key(row_file) == file_key:
            file_votes += 1
        if _subsystem(row_file).casefold() == folder_key:
            place_votes += 1
    return file_votes, place_votes


def _attribution(
    *,
    rel: str,
    mode: str,
    values: list[float],
    draw: tuple[float, ...] | list[float],
    findings: object,
    trust_draw: float,
    place_draw: float,
    likelihood: float,
    exploit_score: float,
    exploration: float,
) -> dict:
    names = list(SIGNAL_KEYS)
    features = [fix_commit_feature(values[0]), *values[1:]]
    components = {
        name: float(draw[index]) * float(value)
        for index, (name, value) in enumerate(zip(names, features))
    }
    components["detector_trust"] = (
        float(trust_draw) if _finding_count(findings) > 0 else 0.0
    )
    components["place"] = max(0.0, float(place_draw))
    raw_activity = sum(components.values())
    likelihood_component = max(0.0, float(likelihood))
    raw_surface = raw_activity + likelihood_component
    all_components = {
        **components,
        "likelihood": likelihood_component,
        "exploration": float(exploration),
    }
    top = sorted(all_components, key=lambda name: (-abs(all_components[name]), name))
    return {
        "attribution_version": ATTRIBUTION_VERSION,
        "mode": mode,
        "six_signal": {
            **{name: components[name] for name in names},
            "total": sum(components[name] for name in names),
        },
        "detector_trust": components["detector_trust"],
        "place": components["place"],
        "likelihood": max(0.0, float(likelihood)),
        "exploration": float(exploration),
        "raw_activity_total": raw_activity,
        "raw_surface_total": raw_surface,
        "exploit_score": float(exploit_score),
        "final_score": float(exploit_score) + float(exploration),
        "top": top,
        "file": rel,
    }


def queue_sort_key(item: dict) -> tuple:
    """Highest mix first, then finding count, then lines."""
    findings = _finding_count(item.get("findings"))
    raw_score = item.get("score")
    if isinstance(raw_score, bool) or raw_score is None:
        score = 0.0
    else:
        try:
            score = float(raw_score)
        except (TypeError, ValueError, OverflowError):
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
    try:
        count = max(0, int(voted_count))
    except (TypeError, ValueError, OverflowError):
        count = 0
    return ANCHOR_VOTES * (0.5 ** (count / ANCHOR_HALFLIFE_ROWS))


def _signal_list(raw: object) -> list[float] | None:
    if isinstance(raw, dict):
        slots = [raw.get(key) for key in SIGNAL_KEYS]
        if any(key not in raw for key in SIGNAL_KEYS):
            return None
    elif isinstance(raw, (list, tuple)) and len(raw) == 6 and not isinstance(raw, (str, bytes)):
        slots = list(raw)
    else:
        return None
    if any(isinstance(item, bool) or item is None for item in slots):
        return None
    try:
        values = [float(item) for item in slots]
    except (TypeError, ValueError, OverflowError):
        return None
    if values[0] < 0.0:
        return None
    if any(math.isnan(value) or math.isinf(value) for value in values):
        return None
    return values


def _draw_list(raw: object) -> list[float] | None:
    """Six finite draw slopes stored on a row. Unlike file signals, a slope may be negative."""
    if isinstance(raw, bool) or not isinstance(raw, (list, tuple)) or len(raw) != 6:
        return None
    values: list[float] = []
    for item in raw:
        if isinstance(item, bool) or item is None:
            return None
        try:
            number = float(item)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(number):
            return None
        values.append(number)
    return values


def _vote_rows(rows: list[dict]) -> list[tuple[float, list[float]]]:
    """File order. Skipped rows and rows without six signals cast no vote.

    Credit is the file signal. A zero signal stays zero. A row whose features
    are all zero is not a six-slope vote. A stored draw does not move it, and
    it does not pull a slope through the floor.
    """
    voted: list[tuple[float, list[float]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        outcome = str(row.get("outcome") or "").strip().casefold()
        if outcome in _PULL_OUTCOMES:
            sign = 1.0
        elif outcome in _PUSH_OUTCOMES:
            sign = -_empty_confidence(row)
        else:
            continue
        signals = _signal_list(row.get("signals"))
        if signals is None:
            continue
        features = [fix_commit_feature(signals[0]), *signals[1:]]
        if not any(feature != 0.0 for feature in features):
            continue
        voted.append((sign, features))
    return voted


def _empty_confidence(row: dict) -> float:
    """Return the finite confidence multiplier for an empty outcome."""
    if str(row.get("outcome") or "").strip().casefold() != "empty":
        return 1.0
    raw = row.get("empty_confidence", 1.0)
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return 1.0
    if not math.isfinite(value):
        return 1.0
    return min(1.0, max(0.0, value))


def _floored_slope(seed: float, value: float) -> float:
    """A non-negative seed is not taken below 0. A negative seed is not taken lower."""
    if not math.isfinite(value):
        return seed
    if seed >= 0.0:
        return value if value > 0.0 else 0.0
    return value if value > seed else seed


def rebuild_mean(
    rows: list[dict],
    *,
    seed: tuple[float, ...] | None = None,
    closed_ids: set[str] | None = None,
) -> tuple[tuple[float, ...], float]:
    """Rebuilt mean and the evidence that sets the bell-curve width.

    The seed stays an offset. Real votes add a residual. They are not averaged
    with the seed, so a seed of 3.3 is not diluted down toward the size of a
    0/1 signal. The residual divisor is RESIDUAL_PRIOR plus decayed vote weight.
    Imaginary votes still set the draw width and are not in that divisor.
    Newest voted row counts as 1. Each step older multiplies by 0.9.
    Committed and review-failed pull toward that file's signals. Empty pulls away.
    Four hundred rows does not freeze this mean.
    """
    base = INITIAL_SLOPES if seed is None else tuple(seed)
    if len(base) != len(INITIAL_SLOPES):
        base = INITIAL_SLOPES
    voted = _vote_rows(_rows_outside_closed(rows, closed_ids))
    anchor = imaginary_votes(len(voted))
    residual = [0.0] * len(INITIAL_SLOPES)
    weight_sum = 0.0
    count = len(voted)
    for index, (sign, features) in enumerate(voted):
        weight = ROW_DECAY ** (count - 1 - index)
        weight_sum += weight
        for slot, feature in enumerate(features):
            residual[slot] += sign * weight * feature
    evidence = anchor + weight_sum
    if evidence <= 0.0 or not math.isfinite(evidence):
        return tuple(base), anchor
    divisor = RESIDUAL_PRIOR + weight_sum
    if divisor <= 0.0 or not math.isfinite(divisor):
        return tuple(base), evidence
    mean_values: list[float] = []
    for seed_value, numer in zip(base, residual):
        shifted = seed_value + (numer / divisor)
        if not math.isfinite(shifted):
            return tuple(base), evidence
        mean_values.append(_floored_slope(seed_value, shifted))
    return tuple(mean_values), evidence


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
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        score = float(raw)
    except (TypeError, ValueError, OverflowError):
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
        sign = _outcome_sign(row)
        if sign is None:
            continue
        if score is None:
            if "findings" not in row and "score" not in row:
                misses += 1
            continue
        if sign < 0.0 and score > 0.0:
            misses += 1
        elif sign > 0.0 and score <= 0.0:
            misses += 1
    return 1.0 + (misses / len(window))


def _rows_outside_closed(rows: list[dict], closed_ids: set[str] | None) -> list[dict]:
    """Closed-window rows are not votes. A row with no window id still votes unless marked."""
    if not closed_ids:
        return rows
    drop_unstamped = _UNSTAMPED_CLOSED in closed_ids
    closed = closed_ids - {_UNSTAMPED_CLOSED}
    open_rows: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            open_rows.append(row)
            continue
        window = row.get("window")
        if drop_unstamped and not (isinstance(window, str) and window):
            continue
        if isinstance(window, str) and window in closed:
            continue
        open_rows.append(row)
    return open_rows


def rebuild_scalar_mean(
    rows: list[dict],
    seed: float,
    predicate,
    *,
    floor_at_zero: bool = False,
    closed_ids: set[str] | None = None,
) -> tuple[float, float]:
    """Residual on the seed. Imaginary votes set the width and are not in the divisor."""
    try:
        start = float(seed)
    except (TypeError, ValueError, OverflowError):
        start = 0.0
    if not math.isfinite(start):
        start = 0.0
    voted: list[float] = []
    for row in _rows_outside_closed(rows, closed_ids):
        if not isinstance(row, dict):
            continue
        sign = _outcome_sign(row)
        if sign is None or not predicate(row):
            continue
        voted.append(sign * _empty_confidence(row))
    anchor = imaginary_votes(len(voted))
    numer = 0.0
    weight_sum = 0.0
    count = len(voted)
    for index, sign in enumerate(voted):
        weight = ROW_DECAY ** (count - 1 - index)
        weight_sum += weight
        numer += sign * weight
    evidence = anchor + weight_sum
    divisor = RESIDUAL_PRIOR + weight_sum
    if divisor <= 0.0 or not math.isfinite(divisor) or not math.isfinite(evidence):
        return start, float(anchor)
    mean = start + (numer / divisor)
    if not math.isfinite(mean):
        return start, evidence
    if floor_at_zero and mean < 0.0:
        mean = 0.0
    if start < 0.0 and mean < start:
        mean = start
    return mean, evidence


def _trust_votes(row: dict) -> bool:
    """Explicit findings of 0 do not vote. A row that omits the key still does."""
    if "findings" not in row:
        return True
    return _finding_count(row.get("findings")) > 0


def rebuild_trust(
    rows: list[dict],
    *,
    seed: float | None = None,
    closed_ids: set[str] | None = None,
) -> tuple[float, float]:
    start = TRUST_SEED if seed is None else seed
    return rebuild_scalar_mean(
        rows,
        start,
        _trust_votes,
        floor_at_zero=True,
        closed_ids=closed_ids,
    )


def rebuild_place(
    rows: list[dict],
    folder: str,
    *,
    seed: float | None = None,
    closed_ids: set[str] | None = None,
) -> tuple[float, float]:
    key = str(folder or ".").casefold()
    start = PLACE_SEED if seed is None else seed
    return rebuild_scalar_mean(
        rows,
        start,
        lambda row: _subsystem(str(row.get("file") or "")).casefold() == key,
        floor_at_zero=True,
        closed_ids=closed_ids,
    )


def draw_width(evidence: float, surprise: float = 1.0) -> float:
    try:
        scale = float(surprise)
    except (TypeError, ValueError, OverflowError):
        scale = 1.0
    if math.isnan(scale) or math.isinf(scale) or scale < 0.0:
        scale = 1.0
    try:
        mass = float(evidence)
    except (TypeError, ValueError, OverflowError):
        mass = 0.0
    if math.isnan(mass) or mass <= 0.0:
        base = 1.0
    else:
        base = 1.0 / math.sqrt(mass)
    if not math.isfinite(base):
        base = 1.0
    return base * scale


def thompson_draw(
    mean: tuple[float, ...],
    evidence: float,
    rng: random.Random | None = None,
    surprise: float = 1.0,
) -> tuple[float, ...]:
    """One independent normal sample per slope. The caller discards it."""
    generator = rng if rng is not None else random.Random()
    width = draw_width(evidence, surprise)
    if not math.isfinite(width):
        width = 1.0
    try:
        slopes = tuple(float(value) for value in mean)
    except (TypeError, ValueError, OverflowError):
        slopes = INITIAL_SLOPES
    else:
        if len(slopes) != 6 or any(not math.isfinite(value) for value in slopes):
            slopes = INITIAL_SLOPES
    return tuple(generator.gauss(value, width) for value in slopes)


def thompson_scalar(
    mean: float,
    evidence: float,
    rng: random.Random | None = None,
    surprise: float = 1.0,
) -> float:
    generator = rng if rng is not None else random.Random()
    width = draw_width(evidence, surprise)
    if not math.isfinite(width):
        width = 1.0
    try:
        center = float(mean)
    except (TypeError, ValueError, OverflowError):
        center = 0.0
    if not math.isfinite(center):
        center = 0.0
    return generator.gauss(center, width)


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
    """Rebuild six-signal and trust posteriors and draw both. Does not write the draws.

    Place draws need unopened candidate folders, so they live in `advance_rank_pass`.
    """
    log_path = path if path is not None else RANK_ROWS_REL
    rows = load_rank_rows(log_path)
    repo = _rank_log_root(Path(log_path))
    if repo is not None:
        closed_ids, slope_seed, trust_seed, _place_seeds = _learning_context(repo)
    else:
        closed_ids, slope_seed, trust_seed = set(), None, None
    open_rows = _rows_outside_closed(rows, closed_ids)
    scale = surprise_scale(open_rows)
    mean, evidence = rebuild_mean(rows, seed=slope_seed, closed_ids=closed_ids)
    draw = thompson_draw(mean, evidence, rng, scale)
    trust_mean, trust_evidence = rebuild_trust(rows, seed=trust_seed, closed_ids=closed_ids)
    trust_draw = thompson_scalar(trust_mean, trust_evidence, rng, scale)
    return {
        "mean": mean,
        "draw": draw,
        "evidence": evidence,
        "surprise": scale,
        "trust_mean": trust_mean,
        "trust_draw": trust_draw,
        "trust_evidence": trust_evidence,
    }


def print_rank_pass(path: Path | None = None) -> None:
    """Print this pass's six-signal and trust draws. The next call rebuilds from rows."""
    result = rank_pass(path)
    payload = {
        "draw": [round(float(value), 6) for value in result["draw"]],
        "mean": [round(float(value), 6) for value in result["mean"]],
        "trust_draw": round(float(result["trust_draw"]), 6),
        "trust_mean": round(float(result["trust_mean"]), 6),
    }
    print(json.dumps(payload, allow_nan=False))


_WALK_SKIP = {
    ".git",
    ".hg",
    ".hive",
    ".cursor",
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
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
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
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        score = float(value)
    except (TypeError, ValueError, OverflowError):
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
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
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


def _rel_for_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return _norm_rel(str(path))


def _fallback_signals(
    root: Path,
    rel: str,
    history: tuple[dict[str, int], set[str]] | None,
    files: list[Path] | None = None,
) -> dict[str, float]:
    """Signals for a row that is no longer in the queue. Git counts stay with the file."""
    root = Path(root)
    chosen = files if files is not None else _candidate_files(root)
    rels = [_rel_for_path(root, path) for path in chosen]
    rels.append(rel)
    fixes, reverted = history if history is not None else _git_history(root)
    measured = _signals_for_file(
        root / rel,
        rel,
        fixes=fixes,
        reverted=reverted,
        stems=_test_stems(rels),
    )
    if measured is None:
        return {key: 0.0 for key in SIGNAL_KEYS}
    return measured[0]


def _take_pass_file(
    root: Path,
    state: dict | None,
    opened: list[str],
    history: tuple[dict[str, int], set[str]] | None,
    files: list[Path] | None = None,
) -> tuple[list[str], bool]:
    """Record this pass's named file. A blank file key does not take the queue head."""
    if not isinstance(state, dict):
        return opened, False
    rel = _norm_rel(str(state.get("file") or ""))
    if not rel:
        return opened, False
    opened_keys = {_opened_key(item) for item in opened}
    appended = False
    if _opened_key(rel) not in opened_keys:
        outcome = str(state.get("outcome") or "").strip().casefold()
        if outcome in _RANK_OUTCOMES:
            signals = _queue_signals(root, rel)
            if signals is None:
                signals = _fallback_signals(root, rel, history, files=files)
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
                draw=_load_pass_draw(root),
                attribution=queued.get("attribution"),
                empty_confidence=state.get("empty_confidence"),
                recovery_lens=state.get("recovery_lens") or queued.get("recovery_lens"),
            )
            opened = [*opened, rel]
            _persist_opened(root, opened)
            appended = True
        else:
            opened = [*opened, rel]
            _persist_opened(root, opened)
    return opened, appended


def _persist_opened(root: Path, opened: list[str]) -> None:
    """Keep the opened set even if a later queue rewrite fails."""
    path = root / RANK_PASS_REL
    queue: list = []
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("queue"), list):
            closed = {_opened_key(item) for item in opened}
            queue = [
                _queue_row_for_write(item)
                for item in payload["queue"]
                if isinstance(item, dict)
                and _opened_key(str(item.get("file") or "")) not in closed
            ]
    payload: dict[str, object] = {"opened": opened, "queue": queue}
    stored_draw = _load_pass_draw(root)
    if stored_draw is not None:
        payload["draw"] = stored_draw
    _write_json(path, payload)


def _queue_row_for_write(item: dict) -> dict:
    """Keep only JSON-safe ranking fields so a stale queue cannot block a write."""
    raw_lines = item.get("lines")
    if isinstance(raw_lines, bool) or raw_lines is None:
        lines = 0
    else:
        try:
            lines = int(raw_lines)
        except (TypeError, ValueError, OverflowError):
            lines = 0
    parsed = _signal_list(item.get("signals"))
    if parsed is None:
        stored_signals = {key: 0.0 for key in SIGNAL_KEYS}
    else:
        stored_signals = {key: parsed[index] for index, key in enumerate(SIGNAL_KEYS)}
    row = {
        "file": _norm_rel(str(item.get("file") or "")),
        "signals": stored_signals,
        "score": _finite_score(item.get("score")),
        "findings": _finding_count(item.get("findings")),
        "lines": lines,
    }
    if "empty_confidence" in item:
        row["empty_confidence"] = _empty_confidence(
            {"outcome": "empty", "empty_confidence": item.get("empty_confidence")}
        )
    lens = item.get("recovery_lens")
    if isinstance(lens, str) and lens in RECOVERY_LENSES:
        row["recovery_lens"] = lens
    stored_likelihood = _stored_likelihood(item)
    if stored_likelihood is not None:
        row["likelihood"] = stored_likelihood
    attribution = item.get("attribution")
    if isinstance(attribution, dict) and attribution.get("attribution_version") == ATTRIBUTION_VERSION:
        try:
            encoded = json.dumps(attribution, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError, OverflowError):
            encoded = ""
        if encoded and len(encoded.encode("utf-8")) <= ATTRIBUTION_ROW_LIMIT:
            row["attribution"] = attribution
            try:
                row_size = len(json.dumps(row, allow_nan=False, separators=(",", ":")).encode("utf-8"))
            except (TypeError, ValueError, OverflowError):
                row_size = ATTRIBUTION_ROW_LIMIT + 1
            if row_size > ATTRIBUTION_ROW_LIMIT:
                row.pop("attribution", None)
    return row


def _empty_windows() -> dict:
    return {"open": {"id": "", "count": 0}, "closed": []}


def _read_windows(root: Path) -> tuple[dict, bool]:
    """Load the archive. A corrupt file is not treated as an empty one that can be written back."""
    path = root / SLOPE_WINDOWS_REL
    if not path.is_file():
        return _empty_windows(), True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
        return _empty_windows(), False
    if not isinstance(payload, dict):
        return _empty_windows(), False
    opened = payload.get("open")
    if not isinstance(opened, dict):
        opened = {"id": "", "count": 0}
    closed = payload.get("closed")
    if not isinstance(closed, list):
        return _empty_windows(), False
    return {"open": opened, "closed": [item for item in closed if isinstance(item, dict)]}, True


def _load_windows(root: Path) -> dict:
    state, _writable = _read_windows(root)
    return state


def _write_windows(root: Path, state: dict) -> None:
    _write_json(root / SLOPE_WINDOWS_REL, state)


def _closed_ids(state: dict) -> set[str]:
    found: set[str] = set()
    for item in state.get("closed") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id"):
            found.add(item["id"])
    return found


def _window_vote(outcome: str) -> bool:
    return outcome in _PULL_OUTCOMES or outcome in _PUSH_OUTCOMES


def _count_window_rows(root: Path, window_id: str) -> int:
    count = 0
    for row in load_rank_rows(root / RANK_ROWS_REL):
        if row.get("window") != window_id:
            continue
        if _window_vote(str(row.get("outcome") or "").strip().casefold()):
            count += 1
    return count


def _closed_record_usable(item: object) -> bool:
    """A closed record votes in a blend only at 200 cycles, finite, and on the floor."""
    if not isinstance(item, dict) or item.get("cycles") != WINDOW_VOTE_LIMIT:
        return False
    raw = item.get("slopes")
    if not isinstance(raw, list) or len(raw) != len(INITIAL_SLOPES):
        return False
    try:
        values = [float(value) for value in raw]
        trust = float(item.get("trust"))
    except (TypeError, ValueError, OverflowError):
        return False
    if any(not math.isfinite(value) for value in values) or not math.isfinite(trust) or trust < 0.0:
        return False
    for seed, value in zip(INITIAL_SLOPES, values):
        floor = 0.0 if seed >= 0.0 else seed
        if value < floor:
            return False
    return True


def _blend_closed(records: list[dict]) -> tuple[tuple[float, ...], float] | None:
    """Newest of the last five usable windows weighs 1, then 1/2, 1/4, 1/8, 1/16."""
    usable = [item for item in records if _closed_record_usable(item)]
    if not usable:
        return None
    chosen = list(reversed(usable[-5:]))
    weights = [1.0, 0.5, 0.25, 0.125, 0.0625][: len(chosen)]
    scale = sum(weights)
    slopes = [0.0] * len(INITIAL_SLOPES)
    trust = 0.0
    for weight, item in zip(weights, chosen):
        values = [float(value) for value in item["slopes"]]
        item_trust = float(item["trust"])
        for index, value in enumerate(values):
            slopes[index] += weight * value
        trust += weight * item_trust
    return tuple(value / scale for value in slopes), trust / scale


def _shrink_toward_seed(slopes: tuple[float, ...], trust: float) -> tuple[tuple[float, ...], float]:
    """Keep the archived blend. Do not pull it back toward the original seed."""
    trust_offset = trust if math.isfinite(trust) and trust > 0.0 else 0.0
    return slopes, trust_offset


def _git_toplevel(start: Path) -> Path | None:
    folder = start if start.is_dir() else start.parent
    proc = subprocess.run(
        ["git", "-C", str(folder), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    text = proc.stdout.strip()
    if not text:
        return None
    return Path(text)


def _committed_json(repo: Path, relative: str) -> dict | None:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        payload = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, MemoryError, RecursionError):
        return None
    return payload if isinstance(payload, dict) else None


def _donor_records(root: Path, entry: object) -> list[dict]:
    """One donor entry. The committed archive wins over a dirty working tree."""
    if not isinstance(entry, str) or not entry.strip():
        return []
    candidate = Path(entry.strip())
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        return []
    try:
        own_archive = (root / SLOPE_WINDOWS_REL).resolve()
    except OSError:
        own_archive = root / SLOPE_WINDOWS_REL
    repo = _git_toplevel(resolved)
    if repo is None:
        return []
    if resolved.is_file():
        try:
            relative = resolved.resolve().relative_to(repo.resolve()).as_posix()
            archive = resolved.resolve()
        except (OSError, ValueError):
            return []
    else:
        relative = SLOPE_WINDOWS_REL.as_posix()
        archive = repo / SLOPE_WINDOWS_REL
        try:
            archive = archive.resolve()
        except OSError:
            return []
    if archive == own_archive:
        return []
    payload = _committed_json(repo, relative)
    if payload is None:
        return []
    closed = payload.get("closed")
    if not isinstance(closed, list):
        return []
    return [item for item in closed if _closed_record_usable(item)]


def _donor_closed(root: Path) -> list[dict]:
    """First listed donor with a valid committed window. Later entries are fallbacks."""
    path = root / DONORS_REL
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
        return []
    if not isinstance(payload, dict):
        return []
    donors = payload.get("donors")
    if not isinstance(donors, list):
        return []
    for entry in donors:
        records = _donor_records(root, entry)
        if records:
            return records
    return []


def _learning_offsets(root: Path, state: dict) -> tuple[tuple[float, ...], float]:
    closed = [item for item in (state.get("closed") or []) if isinstance(item, dict)]
    blended = _blend_closed(closed)
    if blended is None:
        blended = _blend_closed(_donor_closed(root))
    if blended is None:
        return INITIAL_SLOPES, TRUST_SEED
    return _shrink_toward_seed(*blended)


def _load_place_local(root: Path) -> dict[str, float]:
    path = root / PLACE_LOCAL_REL
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
        return {}
    if not isinstance(payload, dict):
        return {}
    places: dict[str, float] = {}
    for key, value in payload.items():
        if key == "archive_commit_pending" or not isinstance(key, str):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(number):
            places[key.casefold()] = number
    return places


def _place_pending(root: Path) -> bool:
    path = root / PLACE_LOCAL_REL
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
        return False
    return isinstance(payload, dict) and payload.get("archive_commit_pending") is True


def _set_place_pending(root: Path, pending: bool) -> None:
    places = _load_place_local(root)
    payload: dict[str, object] = dict(places)
    if pending:
        payload["archive_commit_pending"] = True
    _write_json(root / PLACE_LOCAL_REL, payload)


def _open_window_id(state: dict) -> str:
    opened = state.get("open") if isinstance(state.get("open"), dict) else {}
    window_id = opened.get("id") if isinstance(opened, dict) else ""
    if not isinstance(window_id, str):
        return ""
    return window_id


def _ensure_open_window(root: Path) -> str:
    state, writable = _read_windows(root)
    if not writable:
        return ""
    window_id = _open_window_id(state)
    if not window_id or window_id in _closed_ids(state):
        window_id = "w-" + uuid.uuid4().hex[:12]
        state["open"] = {"id": window_id, "count": 0}
        _write_windows(root, state)
    return window_id


def _current_place_map(root: Path, rows: list[dict], closed_ids: set[str]) -> dict[str, float]:
    saved = _load_place_local(root)
    folders: set[str] = set(saved)
    for row in _rows_outside_closed(rows, closed_ids):
        if not isinstance(row, dict) or _outcome_sign(row) is None:
            continue
        folders.add(_subsystem(str(row.get("file") or "")).casefold())
    mapped: dict[str, float] = {}
    for folder in sorted(folders):
        mean, _evidence = rebuild_place(
            rows,
            folder,
            seed=saved.get(folder, PLACE_SEED),
            closed_ids=closed_ids,
        )
        mapped[folder] = mean
    return mapped


def _worktree_matches_head(repo: Path, relative: str) -> bool:
    """True when the worktree bytes are already the HEAD blob. A stale index still matches."""
    head = subprocess.run(
        ["git", "rev-parse", f"HEAD:{relative}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if head.returncode != 0 or not head.stdout.strip():
        return False
    hashed = subprocess.run(
        ["git", "hash-object", "--path", relative, "--", relative],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return hashed.returncode == 0 and hashed.stdout.strip() == head.stdout.strip()


def _commit_slope_archive(root: Path) -> dict[str, object]:
    """Commit only the slope archive. No push. Other files stay unstaged."""
    repo = root.resolve()
    relative = SLOPE_WINDOWS_REL.as_posix()
    if not (repo / ".git").exists():
        return {"ok": True, "skipped": "no git"}
    if not (repo / SLOPE_WINDOWS_REL).is_file():
        return {"ok": False, "error": "slope archive is missing"}
    if _worktree_matches_head(repo, relative):
        return {"ok": True, "already": True}
    lock = _acquire_commit_lock(repo)
    if lock is None:
        return {"ok": False, "error": "another isolate commit is still running"}
    index_path: Path | None = None
    try:
        index_fd, index_name = tempfile.mkstemp(prefix="hive-bug-hunt-window-")
        os.close(index_fd)
        index_path = Path(index_name)
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(index_path)
        has_head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        read_cmd = ["git", "read-tree", "HEAD" if has_head.returncode == 0 else "--empty"]
        read_tree = subprocess.run(
            read_cmd,
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if read_tree.returncode != 0:
            detail = (read_tree.stderr or read_tree.stdout).strip()
            return {"ok": False, "error": detail or "git read-tree failed"}
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
            return {"ok": False, "error": detail or "git add failed"}
        committed = subprocess.run(
            ["git", "commit", "-m", "bug-hunt: archive slope window"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if committed.returncode != 0:
            detail = (committed.stderr or committed.stdout).strip()
            return {"ok": False, "error": detail or "git commit failed"}
        listed = subprocess.run(
            ["git", "ls-tree", "HEAD", "--", relative],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        info = listed.stdout.strip().split()
        if listed.returncode != 0 or len(info) < 3:
            return {"ok": False, "error": "could not read committed blob"}
        main_env = os.environ.copy()
        main_env.pop("GIT_INDEX_FILE", None)
        updated = subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo", f"{info[0]},{info[2]},{relative}"],
            cwd=repo,
            env=main_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if updated.returncode != 0:
            if _worktree_matches_head(repo, relative):
                return {"ok": True, "already": True}
            detail = (updated.stderr or updated.stdout).strip()
            return {"ok": False, "error": detail or "could not update the index"}
        return {"ok": True}
    finally:
        if index_path is not None:
            index_path.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def _rows_for_close(rows: list[dict], window_id: str) -> list[dict]:
    """The closing mean uses the first 200 voted rows of this id, not a late joiner."""
    kept: list[dict] = []
    used = 0
    for row in rows:
        if (
            isinstance(row, dict)
            and row.get("window") == window_id
            and _window_vote(str(row.get("outcome") or "").strip().casefold())
        ):
            if used >= WINDOW_VOTE_LIMIT:
                continue
            used += 1
        kept.append(row)
    return kept


def _place_payload(payload: dict) -> dict[str, float]:
    places: dict[str, float] = {}
    for key, value in payload.items():
        if key in {"archive_commit_pending", "window"} or not isinstance(key, str):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(number):
            places[key.casefold()] = number
    return places


def _adopt_place_pending(root: Path) -> None:
    """Install a place map only after its window id is already in the archive."""
    path = root / PLACE_PENDING_REL
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
        return
    if not isinstance(payload, dict):
        return
    window = payload.get("window")
    state, writable = _read_windows(root)
    if not writable or not isinstance(window, str) or window not in _closed_ids(state):
        return
    body = _place_payload(payload)
    body_out: dict[str, object] = dict(body)
    body_out["archive_commit_pending"] = True
    body_out["window"] = window
    _write_json(root / PLACE_LOCAL_REL, body_out)
    path.unlink(missing_ok=True)


def _baked_place(root: Path, window_id: str, closed: set[str]) -> dict[str, float] | None:
    """A place file written before the archive is the close result, not a new seed."""
    if window_id in closed:
        return None
    path = root / PLACE_LOCAL_REL
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None
    marked = payload.get("window")
    if not isinstance(marked, str) or marked != window_id:
        return None
    return _place_payload(payload)


def _finish_window(root: Path, state: dict, window_id: str) -> None:
    """Write the closed record first, then the place file computed from the pre-close seeds."""
    if window_id in _closed_ids(state):
        return
    rows = _rows_for_close(load_rank_rows(root / RANK_ROWS_REL), window_id)
    closed = _closed_ids(state)
    slope_seed, trust_seed = _learning_offsets(root, state)
    slopes, _evidence = rebuild_mean(rows, seed=slope_seed, closed_ids=closed)
    trust, _trust_ev = rebuild_trust(rows, seed=trust_seed, closed_ids=closed)
    baked = _baked_place(root, window_id, closed)
    place_map = baked if baked is not None else _current_place_map(root, rows, closed)
    _write_json(root / PLACE_PENDING_REL, {**place_map, "window": window_id})
    record = {
        "id": window_id,
        "cycles": WINDOW_VOTE_LIMIT,
        "slopes": [round(float(value), 6) for value in slopes],
        "trust": round(float(trust), 6),
    }
    closed_list = list(state.get("closed") or [])
    closed_list.append(record)
    _write_windows(
        root,
        {"open": {"id": "w-" + uuid.uuid4().hex[:12], "count": 0}, "closed": closed_list},
    )
    _adopt_place_pending(root)
    result = _commit_slope_archive(root)
    if result.get("ok"):
        _set_place_pending(root, False)


def _close_if_at_limit(root: Path) -> None:
    """Close a full window before another voted row can join it."""
    state, writable = _read_windows(root)
    if not writable:
        return
    window_id = _open_window_id(state)
    if not window_id or window_id in _closed_ids(state):
        return
    if _count_window_rows(root, window_id) < WINDOW_VOTE_LIMIT:
        return
    _finish_window(root, state, window_id)


def _retry_archive_commit(root: Path) -> None:
    if not _place_pending(root):
        return
    result = _commit_slope_archive(root)
    if result.get("ok"):
        _set_place_pending(root, False)


def _sync_window(root: Path) -> None:
    """Recount the open window. At 200, archive the mean, save place, and reset."""
    _adopt_place_pending(root)
    state, writable = _read_windows(root)
    if not writable:
        return
    window_id = _open_window_id(state)
    if not window_id:
        _retry_archive_commit(root)
        return
    count = _count_window_rows(root, window_id)
    if count >= WINDOW_VOTE_LIMIT and window_id not in _closed_ids(state):
        _finish_window(root, state, window_id)
        return
    _retry_archive_commit(root)
    state, writable = _read_windows(root)
    if not writable:
        return
    state["open"] = {"id": window_id, "count": count}
    _write_windows(root, state)


def _full_window_ids(root: Path) -> set[str]:
    """Ids that already have a full voted window. Used when the archive cannot be read."""
    counts: dict[str, int] = {}
    for row in load_rank_rows(root / RANK_ROWS_REL):
        window = row.get("window")
        if not isinstance(window, str) or not window:
            continue
        if not _window_vote(str(row.get("outcome") or "").strip().casefold()):
            continue
        counts[window] = counts.get(window, 0) + 1
    return {window for window, count in counts.items() if count >= WINDOW_VOTE_LIMIT}


def _learning_context(root: Path) -> tuple[set[str], tuple[float, ...], float, dict[str, float]]:
    state, writable = _read_windows(root)
    if not writable:
        closed = _full_window_ids(root)
        closed.add(_UNSTAMPED_CLOSED)
        return closed, INITIAL_SLOPES, TRUST_SEED, _load_place_local(root)
    return _closed_ids(state), *_learning_offsets(root, state), _load_place_local(root)


def _rank_log_root(path: Path) -> Path | None:
    if path.name != RANK_ROWS_REL.name or path.parent.name != "bug-hunt":
        return None
    return path.parent.parent.parent


def _load_pass_draw(root: Path) -> list[float] | None:
    """The six slopes that scored the current queue. Missing or bad draws are ignored."""
    path = root / RANK_PASS_REL
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None
    return _draw_list(payload.get("draw"))


def _append_calibration(
    root: Path,
    rel: str,
    attribution: dict,
    outcome: str,
    findings: object,
) -> None:
    record = {
        "file": rel,
        "attribution_version": ATTRIBUTION_VERSION,
        "exploit_score": _finite_score(attribution.get("exploit_score")),
        "exploration": _finite_score(attribution.get("exploration")),
        "final_score": _finite_score(attribution.get("final_score")),
        "outcome": outcome,
        "findings": _finding_count(findings),
        "mismatch": (
            abs(
                _finite_score(attribution.get("final_score"))
                - _finite_score(attribution.get("exploit_score"))
                - _finite_score(attribution.get("exploration"))
            )
            > 1e-6
        ),
    }
    encoded = json.dumps(record, allow_nan=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > ATTRIBUTION_ROW_LIMIT:
        return
    path = root / CALIBRATION_REL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")
    except (OSError, MemoryError) as exc:
        raise BugHuntError(f"could not append {CALIBRATION_REL.as_posix()}") from exc


def _append_rank_row(
    root: Path,
    rel: str,
    signals: dict[str, float],
    scenario: str,
    outcome: str,
    findings: object = 0,
    score: object = 0.0,
    draw: list[float] | None = None,
    attribution: object = None,
    empty_confidence: object = None,
    recovery_lens: object = None,
) -> None:
    path = root / RANK_ROWS_REL
    parsed = _signal_list(signals)
    if parsed is None:
        stored_signals = {key: 0.0 for key in SIGNAL_KEYS}
    else:
        stored_signals = {key: parsed[index] for index, key in enumerate(SIGNAL_KEYS)}
    row = {
        "file": rel,
        "signals": stored_signals,
        "scenario": scenario,
        "outcome": outcome,
        "findings": _finding_count(findings),
        "score": _finite_score(score),
    }
    stored_draw = _draw_list(draw)
    if stored_draw is not None:
        row["draw"] = stored_draw
    stored_attribution = _queue_row_for_write(
        {"file": rel, "signals": stored_signals, "score": score, "findings": findings, "attribution": attribution}
    ).get("attribution")
    if stored_attribution is not None:
        row["attribution"] = stored_attribution
    if outcome.strip().casefold() == "empty":
        row["empty_confidence"] = _empty_confidence(
            {"outcome": "empty", "empty_confidence": empty_confidence}
        )
        if isinstance(recovery_lens, str) and recovery_lens in RECOVERY_LENSES:
            row["recovery_lens"] = recovery_lens
    outcome_key = outcome.strip().casefold()
    if _window_vote(outcome_key):
        _close_if_at_limit(root)
        window_id = _ensure_open_window(root)
        if window_id:
            row["window"] = window_id
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, allow_nan=False) + "\n")
    except (OSError, MemoryError) as exc:
        raise BugHuntError(f"could not append {RANK_ROWS_REL.as_posix()}") from exc
    if stored_attribution is not None:
        try:
            _append_calibration(root, rel, stored_attribution, outcome, findings)
        except BugHuntError:
            # Calibration is an audit sidecar; its I/O failure must not cause
            # the already-persisted learning row to be replayed on retry.
            pass
    if _window_vote(outcome_key):
        _sync_window(root)


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
    except (MemoryError, OSError):
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


_OTHER_DEFECTS = ("wiring_hop", "dead_setting", "reverted", "split_stores")


def _thin_counted_once(signals: dict[str, float]) -> dict[str, float]:
    """A missing test does not also take the thin bit when another defect signal is on."""
    try:
        stacked = any(float(signals.get(key) or 0.0) > 0.0 for key in _OTHER_DEFECTS)
    except (TypeError, ValueError, OverflowError):
        stacked = False
    if not stacked:
        return signals
    out = dict(signals)
    out["thin_test"] = 0.0
    return out


def _signals_for_file(
    path: Path,
    rel: str,
    *,
    fixes: dict[str, int],
    reverted: set[str],
    stems: set[str],
) -> tuple[dict[str, float], int, int, int, int] | None:
    try:
        if path.stat().st_size > FILE_BYTE_CAP:
            return None
        source = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError, MemoryError):
        return None
    detect = _sandbox_detect()
    try:
        found = detect.findings_for(path, source)
    except (TypeError, ValueError, AttributeError, OSError, RecursionError, MemoryError, OverflowError):
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
            csharp = getattr(detect, "csharp_signals", None)
            packed = csharp(source, thin) if callable(csharp) else detect.Signals(thin_test=thin)
        folded = _opened_key(rel)
        packed.recent_fix_commits = int(fixes.get(folded, 0))
        packed.reverted = 1 if folded in reverted else 0
        signals = {key: float(getattr(packed, key)) for key in SIGNAL_KEYS}
        if any(math.isnan(value) or math.isinf(value) for value in signals.values()):
            raise ValueError("non-finite signal")
        signals = _thin_counted_once(signals)
    except (RecursionError, MemoryError, TypeError, ValueError, AttributeError, OverflowError):
        if finding_count == 0:
            return None
        signals = {key: 0.0 for key in SIGNAL_KEYS}
    branches, calls = _count_surface(source)
    return signals, source.count("\n") + 1, finding_count, branches, calls


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
    evidence_six: float = 20.0,
    evidence_trust: float = 20.0,
    place_evidence: dict[str, float] | None = None,
    rank_rows: list[dict] | None = None,
    override_rel: str = "",
    excluded_locations: set[str] | None = None,
) -> list[dict[str, object]]:
    """Score files this hunt has not opened. The slopes are this pass's draw.

    Pass limit=None to rank every qualifying candidate, then persist the top 50.
    """
    root = Path(root)
    chosen = files if files is not None else _candidate_files(root)
    rels = [_rel_for_path(root, path) for path in chosen]
    stems = _test_stems(rels)
    fixes, reverted = history if history is not None else _git_history(root)
    closed = {_opened_key(item) for item in opened}
    places = place_draws or {}
    evidences = place_evidence or {}
    rows = rank_rows or []
    excluded = {_opened_key(item) for item in (excluded_locations or set())}
    ranked: list[dict[str, object]] = []
    for path, rel in zip(chosen, rels):
        rel = _norm_rel(rel)
        if (
            not rel
            or _opened_key(rel) in closed
            or _opened_key(rel) in excluded
            or _is_test_rel(rel)
        ):
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
            signals, lines, finding_count, branches, calls = measured
            values = _signal_list(signals)
            if values is None:
                continue
            is_override = _opened_key(rel) == _opened_key(override_rel)
            if not any(values) and finding_count == 0 and not is_override:
                continue
            try:
                six_score = score_signals(values, slopes)
            except (TypeError, ValueError, OverflowError):
                continue
            folder = _subsystem(rel)
            place_draw = places.get(folder.casefold(), 0.0)
            try:
                thin_value = float(signals.get("thin_test", 0.0))
            except (TypeError, ValueError):
                thin_value = 0.0
            untested = (
                math.isfinite(thin_value) and thin_value > 0 and not _is_test_rel(rel)
            )
            likelihood = bug_likelihood(
                lines=lines,
                branches=branches,
                calls=calls,
                findings=finding_count,
                untested=untested,
            )
            combined = rank_queue_score(
                six_score, finding_count, trust_draw, place_draw, likelihood
            )
            file_votes, place_votes = _voted_rows_for(rows, rel, folder)
            exploration = exploration_bonus(
                evidence_six,
                evidence_trust,
                evidences.get(folder.casefold(), 20.0),
                file_votes,
                place_votes,
            )
            exploit_score = combined
            ranked.append(
                {
                    "file": rel,
                    "signals": signals,
                    "score": round(exploit_score + exploration, 6),
                    "lines": lines,
                    "findings": finding_count,
                    "likelihood": likelihood,
                    "attribution": _attribution(
                        rel=rel,
                        mode="override" if is_override else "rank",
                        values=values,
                        draw=slopes,
                        findings=finding_count,
                        trust_draw=trust_draw,
                        place_draw=place_draw,
                        likelihood=likelihood,
                        exploit_score=exploit_score,
                        exploration=exploration,
                    ),
                }
            )
        except (MemoryError, OSError, RecursionError, TypeError, ValueError, OverflowError):
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


def _read_recovery_state(root: Path) -> dict:
    """Read bounded recovery metadata; malformed state fails closed to idle."""
    path = Path(root) / RECOVERY_REL
    if not path.is_file():
        return {
            "phase": "idle",
            "attempts": 0,
            "empty_streak": 0,
            "excluded_locations": [],
            "excluded_folders": [],
            "lenses_used": [],
            "coverage_by_folder": {},
            "last_empty_confidence": 1.0,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, MemoryError, RecursionError):
        payload = None
    if not isinstance(payload, dict):
        payload = {}
    phase = payload.get("phase")
    attempts = payload.get("attempts")
    streak = payload.get("empty_streak")
    confidence = payload.get("last_empty_confidence", 1.0)
    locations = payload.get("excluded_locations", [])
    folders = payload.get("excluded_folders", [])
    lenses = payload.get("lenses_used", [])
    coverage = payload.get("coverage_by_folder", {})
    valid = (
        phase in {"idle", "recovery"}
        and isinstance(attempts, int) and not isinstance(attempts, bool) and 0 <= attempts <= 3
        and isinstance(streak, int) and not isinstance(streak, bool) and 0 <= streak <= 3
        and isinstance(locations, list) and len(locations) <= 128
        and isinstance(folders, list) and len(folders) <= 64
        and isinstance(lenses, list) and len(lenses) <= 6
        and isinstance(coverage, dict) and len(coverage) <= 64
    )
    if valid:
        clean_locations = [_norm_rel(item) for item in locations if isinstance(item, str)]
        clean_folders = [str(item) for item in folders if isinstance(item, str)]
        valid = (
            len(clean_locations) == len(locations)
            and len(clean_folders) == len(folders)
            and len(set(map(str.casefold, clean_locations))) == len(clean_locations)
            and len(set(map(str.casefold, clean_folders))) == len(clean_folders)
            and all(item and not item.startswith("/") and ":" not in item and ".." not in item.split("/") for item in clean_locations)
            and all(item in RECOVERY_LENSES for item in lenses)
            and len(set(lenses)) == len(lenses)
            and all(isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool) and value in (0, 1) for key, value in coverage.items())
        )
    try:
        confidence = float(confidence)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        valid = False
    if not valid:
        return {
            "phase": "idle",
            "attempts": 0,
            "empty_streak": 0,
            "excluded_locations": [],
            "excluded_folders": [],
            "lenses_used": [],
            "coverage_by_folder": {},
            "last_empty_confidence": 1.0,
        }
    return {
        "phase": phase,
        "attempts": attempts,
        "empty_streak": streak,
        "excluded_locations": clean_locations,
        "excluded_folders": clean_folders,
        "lenses_used": list(lenses),
        "coverage_by_folder": dict(coverage),
        "last_empty_confidence": confidence,
    }


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
    recovery = _read_recovery_state(root)
    override_rel, override_error = _validated_override(root, state)
    if override_error:
        raise BugHuntError(override_error)
    opened = [] if fresh else _load_opened(root)
    opened, appended = _take_pass_file(
        root, None if fresh else state, opened, history, files=files
    )
    rows = load_rank_rows(root / RANK_ROWS_REL)
    closed_ids, slope_seed, trust_seed, place_seeds = _learning_context(root)
    open_rows = _rows_outside_closed(rows, closed_ids)
    scale = surprise_scale(open_rows)
    mean, evidence = rebuild_mean(rows, seed=slope_seed, closed_ids=closed_ids)
    draw = thompson_draw(mean, evidence, rng, scale)
    trust_mean, trust_evidence = rebuild_trust(rows, seed=trust_seed, closed_ids=closed_ids)
    trust_draw = thompson_scalar(trust_mean, trust_evidence, rng, scale)
    candidate_paths = list(files) if files is not None else _candidate_files(root)
    if override_rel:
        override_path = root / override_rel
        if _opened_key(override_rel) not in {
            _opened_key(_rel_for_path(root, path)) for path in candidate_paths
        }:
            candidate_paths.append(override_path)
    candidate_folders = {
        _subsystem(_norm_rel(_rel_for_path(root, path))).casefold()
        for path in candidate_paths
    }
    place_evidence = {
        folder: rebuild_place(
            rows,
            folder,
            seed=place_seeds.get(folder, PLACE_SEED),
            closed_ids=closed_ids,
        )[1]
        for folder in candidate_folders
    }
    queue = score_unopened(
        root,
        opened,
        draw,
        files=candidate_paths,
        history=history,
        limit=None,
        trust_draw=trust_draw,
        evidence_six=evidence,
        evidence_trust=trust_evidence,
        place_evidence=place_evidence,
        rank_rows=rows,
        override_rel=override_rel,
        excluded_locations=set(recovery.get("excluded_locations", []))
        if recovery.get("phase") == "recovery"
        else None,
    )
    place_draws: dict[str, float] = {}
    for item in queue:
        folder = _subsystem(str(item.get("file") or ""))
        key = folder.casefold()
        if key in place_draws:
            continue
        place_mean, place_mass = rebuild_place(
            rows,
            folder,
            seed=place_seeds.get(folder.casefold(), PLACE_SEED),
            closed_ids=closed_ids,
        )
        drawn_place = thompson_scalar(place_mean, place_mass, rng, scale)
        place_draws[key] = drawn_place if drawn_place > 0.0 else 0.0
    for item in queue:
        folder = _subsystem(str(item.get("file") or ""))
        values = _signal_list(item.get("signals"))
        try:
            six_score = score_signals(values, draw) if values is not None else 0.0
        except (TypeError, ValueError, OverflowError):
            six_score = 0.0
        item["likelihood"] = _likelihood_from_row(root, item)
        place_draw = place_draws.get(folder.casefold(), 0.0)
        exploit_score = rank_queue_score(
            six_score,
            item.get("findings"),
            trust_draw,
            place_draw,
            item["likelihood"],
        )
        file_votes, place_votes = _voted_rows_for(rows, str(item.get("file") or ""), folder)
        exploration = exploration_bonus(
            evidence,
            trust_evidence,
            place_evidence.get(folder.casefold(), 20.0),
            file_votes,
            place_votes,
        )
        item["score"] = round(exploit_score + exploration, 6)
        item["attribution"] = _attribution(
            rel=str(item.get("file") or ""),
            mode="override" if _opened_key(str(item.get("file") or "")) == _opened_key(override_rel) else "rank",
            values=values,
            draw=draw,
            findings=item.get("findings"),
            trust_draw=trust_draw,
            place_draw=place_draw,
            likelihood=item["likelihood"],
            exploit_score=exploit_score,
            exploration=exploration,
        )
    queue.sort(key=queue_sort_key)
    if recovery.get("phase") == "recovery":
        excluded_folders = {
            str(item).casefold() for item in recovery.get("excluded_folders", [])
        }
        if excluded_folders:
            # Folder exclusions are preferences: use another qualifying folder
            # first, but retain same-folder candidates as a bounded fallback.
            queue.sort(
                key=lambda item: (
                    _subsystem(str(item.get("file") or "")).casefold()
                    in excluded_folders,
                    queue_sort_key(item),
                )
            )
        unused = [lens for lens in RECOVERY_LENSES if lens not in recovery.get("lenses_used", [])]
        selected_lens = unused[0] if unused else RECOVERY_LENSES[
            int(recovery.get("attempts", 0)) % len(RECOVERY_LENSES)
        ]
        for item in queue:
            item["recovery_lens"] = selected_lens
    queue = [_queue_row_for_write(item) for item in queue[:QUEUE_LIMIT]]
    _write_json(
        root / RANK_PASS_REL,
        {
            "opened": opened,
            "queue": queue,
            "draw": [round(value, 6) for value in draw],
        },
    )
    top = str(queue[0]["file"]) if queue else ""
    return {
        "top": top,
        "appended": appended,
        "opened": opened,
        "recovery_lens": queue[0].get("recovery_lens", "") if queue else "",
    }


def _last_rank_row(root: Path) -> dict | None:
    rows = load_rank_rows(root / RANK_ROWS_REL)
    if not rows or not isinstance(rows[-1], dict):
        return None
    return rows[-1]


def _append_unlabeled_stop(
    root: Path,
    state: dict | None,
    opened: list[str],
    history: tuple[dict[str, int], set[str]] | None,
    files: list[Path] | None,
) -> tuple[list[str], bool]:
    """Append one stopped row. A blank file stays blank and does not claim the queue head."""
    rel = ""
    scenario = ""
    if isinstance(state, dict):
        rel = _norm_rel(str(state.get("file") or ""))
        scenario = str(state.get("scenario") or "").strip()
    last = _last_rank_row(root)
    if (
        last is not None
        and str(last.get("outcome") or "") == "stopped"
        and _norm_rel(str(last.get("file") or "")) == rel
    ):
        return opened, False
    opened_keys = {_opened_key(item) for item in opened}
    already_logged = False
    if rel:
        wanted = _opened_key(rel)
        for row in load_rank_rows(root / RANK_ROWS_REL):
            if isinstance(row, dict) and _opened_key(str(row.get("file") or "")) == wanted:
                already_logged = True
                break
    if rel and _opened_key(rel) in opened_keys and already_logged:
        return opened, False
    if rel:
        signals = _queue_signals(root, rel)
        if signals is None:
            signals = _fallback_signals(root, rel, history, files=files)
        queued = _queue_item(root, rel) or {}
        findings = queued.get("findings", 0)
        score = queued.get("score", 0.0)
    else:
        signals = {key: 0.0 for key in SIGNAL_KEYS}
        findings = 0
        score = 0.0
    _append_rank_row(
        root,
        rel,
        signals,
        scenario,
        "stopped",
        findings=findings,
        score=score,
    )
    if rel and _opened_key(rel) not in opened_keys:
        opened = [*opened, rel]
        _persist_opened(root, opened)
    return opened, True


def save_stopped_outcome(
    root: Path,
    state: dict | None,
    *,
    history: tuple[dict[str, int], set[str]] | None = None,
    files: list[Path] | None = None,
) -> dict[str, bool]:
    """Write the outcome row when the hunt stops. Does not draw or start another pass.

    Call this before writing continue.json active false, or from a hook that still
    sees a stop token whose active flag is already false. A stop with no valid
    outcome still appends one `stopped` row.
    """
    root = Path(root)
    try:
        prior_opened = _load_opened(root)
    except BugHuntError:
        prior_opened = []
    outcome = ""
    if isinstance(state, dict):
        outcome = str(state.get("outcome") or "").strip().casefold()
    if outcome in _RANK_OUTCOMES:
        opened, appended = _take_pass_file(root, state, prior_opened, history, files=files)
        missing_outcome = False
    else:
        opened, appended = _append_unlabeled_stop(
            root, state, prior_opened, history, files=files
        )
        missing_outcome = False
    path = root / RANK_PASS_REL
    queue: list = []
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError, UnicodeError, MemoryError, RecursionError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("queue"), list):
            closed = {_opened_key(item) for item in opened}
            queue = [
                _queue_row_for_write(item)
                for item in payload["queue"]
                if isinstance(item, dict) and _opened_key(str(item.get("file") or "")) not in closed
            ]
    payload: dict[str, object] = {"opened": opened, "queue": queue}
    if appended or opened != prior_opened:
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
        "A committed, skipped, or review-failed outcome resets consecutive_empty to 0 and clears recovery.json. "
        "For an empty outcome, include finite empty_confidence from 0 to 1 and, during recovery, the selected recovery_lens. "
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
    base = f"""After two consecutive empty searches, enter bounded recovery when a qualifying unopened production location remains; otherwise stop. Recovery uses `.hive/bug-hunt/recovery.json`, lasts at most three recovery-empty passes, and never reopens an excluded location solely to fill a budget. A record-and-skip is not an empty search. A committed, skipped, or review-failed outcome resets the empty-search count and recovery state. {count} committed fixes is the ceiling, not a quota. Until a stop condition is met, deep-dive into code logic and functional issues, apply a fix, self-review, commit locally when that review passes, and repeat across separate inference passes.

{pause_text} This ceiling counts committed fixes, not inference passes.

## Where to look

Rank locations before editing. Open the first file in `.hive/bug-hunt/rank-pass.json` that this run has not already opened. One location per iteration. Qualifying means any of the six signals or a detector finding on production code. A test file is not a hunt location. After a patch, rank tests from past diffs on the same files and run the top of that list. The ranker has no probability floor. The ranker chooses the queue only. It does not write the patch, choose the commit message, or override the stop rule.

The continue hook rebuilds the six weights, detector trust, and per-folder place attention from `.hive/bug-hunt/rank-rows.jsonl` and scores the unopened files before the pass it starts. A bug-hunt request writes that same queue before the first pass. Open the first file in `.hive/bug-hunt/rank-pass.json`. Do not rebuild the weights yourself. The seed, which a later rebuild starts from, is log1p of recent bug-fix commits × {s0}, a failing or thin test counted once × {s1} (not stacked on a wiring hop, unread flag, revert, or split store), a wiring hop with no call site (UI or event → handler → persisted or rendered result) × {s2}, a setting or flag with no reader × {s3}, a reverted commit × {s4}, two stores for one fact × {s5}. Twenty imaginary votes set the draw width and halve for every forty voted rows. They are not in the mean. The seed stays an offset. Real votes add a residual divided by 2 plus their decayed weight. A non-negative seed is not taken below 0. A zero file signal adds no credit, does not change vote weights, and a stored draw does not move it. A skipped row casts no vote. Place attention is not taken below 0. Voted rows decay by 0.9 in row order: the newest voted row is one full vote, and each step older multiplies by 0.9. A committed or review-failed row pulls the weights toward that file's signals. An empty row pulls them away. Each pass draws one six-weight sample, one trust sample, and one place sample per candidate folder from a bell curve around those rebuilt means, mixes them, and does not store the draws. Trust starts at 1.0 and votes on finding files and on rows that omit findings. An explicit findings count of 0 does not vote. Place starts at 0.0 per first-path folder. Residual mismatch on stored row scores widens the next bells. A voted row that omits both findings and score counts as a mismatch. About 400 rows from one process is when a recovery is trustworthy. That count does not install a new fixed set and does not freeze the update. Do not fit a logistic regression. Findings are not a seventh six-signal weight. Finding count then line count break remaining ties. After that mix, the queue squashes activity with tanh into the open range ±4, stepping a saturated endpoint to the next float inside, and adds bug likelihood, which is not a learned weight. Lines, branches, and call sites share one surface squashed into the open range ±4. One or more findings add both activity-cap spans, the surface cap, and the missing-test step once, then log1p of the count, so a smaller file with findings stays ahead of a larger clean file. Add 1 when production code has no matching test. The place rescore keeps likelihood, and rebuilds it from the file when the saved row has no likelihood key. A test file does not take that last step. The queue keeps the top 50 scored files.

After the R9 exploit score, add only the bounded R10 uncertainty/coverage bonus
(maximum 0.25); repeated file and folder votes reduce it. Persist versioned
attribution and a non-learning calibration record with the selected row. A
requested_file override must remain inside the repository, use Python or C#
source, and pass requested_line validation; it is review guidance, not a new
vote or location.

During R11 recovery, use a different qualifying folder when possible and
exclude the just-inspected empty location. Rotate the bounded review lenses in
this order: ui-event, configuration, wiring, persistence, error-reporting,
test-contract. Write the selected lens and finite `empty_confidence` (0..1) in
the pass metadata. Empty learning is multiplied by that confidence; legacy rows
default to 1.0. Recovery metadata is audit state only and is never a posterior
vote.

A logic error still qualifies. The ranker has no probability floor. Count a wrong boolean, an inverted condition, an off-by-one bound, a caught error reported as success, or a count that drops or double-counts an item. That signal is qualifying.

One row per opened location, written once, after the outcome is known: file, signals, scenario, outcome (`committed`, `skipped`, `empty`, or `review-failed`), findings, and score. The hook appends that row to `.hive/bug-hunt/rank-rows.jsonl` from the `file`, `scenario`, and `outcome` keys on `.hive/bug-hunt/continue.json`, copying findings and score from that file's `.hive/bug-hunt/rank-pass.json` row along with the signals it scored. Do not append the row yourself. A blank file key does not claim the queue head. A stop with no valid outcome still appends one stopped row, and that outcome casts no vote. Do not append a second row for the same location in this run. A later hunt may append a new row for that location. Rows in the open window are votes for the next rebuild. Rows stamped with a closed window id are not. An unopened location is not an empty search. The location model treats `committed` and `review-failed` as pulls toward that file's signals. An `empty` row pulls them away. A `skipped` row casts no vote. The classifier treats `committed` and `review-failed` as a real bug.

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

Stop after {count} committed fixes, after bounded R11 recovery is exhausted, or when no unopened location still qualifies. Qualifying means any of the six signals or a detector finding on production code. A test file is not a hunt location. The ranker has no probability floor. Two consecutive empty searches enter recovery when a qualifying unopened production location remains. Recovery chooses an unused lens and a different qualifying folder when possible, persists `recovery.json`, and stops after three recovery-empty passes, the ceiling, no qualifying location, or a state-write failure. A committed, skipped, or review-failed outcome resets that count and recovery. Report the commits, what each one fixed (confirmed or potential, and the scenario), anything you recorded and skipped, and any opened location that had neither a confirmed bug nor a potential bug. Do not invent a scenario the code does not actually produce. Do not push.
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


def _ensure_hunt_gitignore(root: Path) -> bool:
    """Ignore the local place file and donor list. Keep the slope archive trackable."""
    path = root / ".gitignore"
    wanted = (
        ".hive/bug-hunt/place-local.json",
        ".hive/bug-hunt/place-local.pending.json",
        ".hive/bug-hunt/donors.json",
        "!.hive/bug-hunt/slope-windows.json",
    )
    try:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    except (OSError, UnicodeError):
        existing = ""
    present = {line.strip() for line in existing.splitlines()}
    missing = [line for line in wanted if line not in present]
    if not missing:
        return False
    suffix = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(existing + suffix + "\n".join(missing) + "\n", encoding="utf-8", newline="\n")
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
    if _ensure_hunt_gitignore(target):
        written.append(".gitignore")
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
        if relative == SLOPE_WINDOWS_REL.as_posix():
            continue
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
