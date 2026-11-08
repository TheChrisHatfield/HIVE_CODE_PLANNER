"""Write a rank log for each git repo that has none.

Uses the detector's six signals and hand-weight sum. Scanner defects are
flagged as scanner-hit. Files with no human label stay unlabeled. Neither
outcome is a hunt outcome (committed, empty, or review-failed).

Does not edit the prompt or any rank log that already exists.

    py -3.11 scripts/sandbox_rank_emit_unlabeled.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _detector():
    path = Path(__file__).with_name("sandbox_rank_detect.py")
    spec = importlib.util.spec_from_file_location("sandbox_rank_detect", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


D = _detector()

# The 24 git repos found on H. The Hive Code Planner copy already has a log.
REPOS = (
    Path(r"H:\D_DRIVE_OVERFLOW\SD_TEST\StableProjectorz\stable-diffusion-webui-forge\webui"),
    Path(r"H:\D_DRIVE_OVERFLOW\SD_TEST\StableProjectorz\stable-diffusion-webui-forge\webui\repositories\BLIP"),
    Path(r"H:\D_DRIVE_OVERFLOW\SD_TEST\StableProjectorz\stable-diffusion-webui-forge\webui\repositories\huggingface_guess"),
    Path(r"H:\D_DRIVE_OVERFLOW\SD_TEST\StableProjectorz\stable-diffusion-webui-forge\webui\repositories\stable-diffusion-webui-assets"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_RANKING_REFERENCES\coleman"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\HIVE_CODE_PLANNER"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\STABLE_FLOW_SPZ_UVSEAM"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\STABLE_FLOW_SPZ_UVSEAM\references\libigl"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\STABLE_FLOW_SPZ_UVSEAM\references\Michelangelo"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\ROBUST_WEIGHT_TRANSFER\robust-weight-transfer"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\LEITNER_LEARNING"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\spec-kit"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\ANDROID_MOVIE_APP"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\UNITY_CHAIN_TOON_SHADER"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\UNITY_CHAIN_TOON_SHADER\vendor\unity-agent-plugin"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\UNITY_CHAIN_TOON_SHADER\vendor\unity-mcp"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\UNITY_CHAIN_TOON_SHADER\vendor\UnityChanToonShaderVer2_Project"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\HIVE_CODE_DEV_1"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\HIVE_CODE_DEV_1\external\continuous-thought-machines"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\HIVE_CODE_DEV_1\external\moshi"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\HIVE_CODE_DEV_1\external\moshi-finetune"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\GEN_PBR"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\zed"),
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\BLUETTOOTH_SURROUND"),
)
KEEP = Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES\HIVE_CODE_PLANNER")
HUMAN = {"committed", "empty", "review-failed", "skipped"}


def _nested_roots(root: Path, others: list[Path]) -> list[Path]:
    resolved = root.resolve()
    nested = []
    for other in others:
        try:
            other.resolve().relative_to(resolved)
        except ValueError:
            continue
        if other.resolve() != resolved:
            nested.append(other.resolve())
    return nested


def iter_source(root: Path, nested: list[Path]) -> list[Path]:
    found: list[Path] = []
    if not root.is_dir():
        return found
    nested_names = {path for path in nested}
    for dirpath, dirnames, filenames in __import__("os").walk(root):
        kept = []
        for name in dirnames:
            if D._skip_dir(name):
                continue
            child = (Path(dirpath) / name).resolve()
            if child in nested_names:
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            lower = name.lower()
            if lower.endswith(".py") or lower.endswith(".cs"):
                found.append(Path(dirpath) / name)
    return found


def rows_for(root: Path, nested: list[Path]) -> list[dict[str, object]]:
    paths = iter_source(root, nested)
    stems = D.test_stems(paths, root)
    fixes, reverted = D.git_history(root)
    fix_lookup: dict[str, int] = {}
    for key, value in fixes.items():
        folded = key.casefold()
        fix_lookup[folded] = fix_lookup.get(folded, 0) + value
    revert_lookup = {key.casefold() for key in reverted}
    rows: list[dict[str, object]] = []
    for path in paths:
        source = D._read(path)
        if source is None:
            continue
        rel = path.relative_to(root).as_posix()
        found = D.findings_for(path, source)
        if found is None:
            continue
        if path.suffix.lower() == ".py":
            signals = D.python_signals(source, 1 if D.is_thin(path, root, stems) else 0)
        else:
            signals = D.Signals(thin_test=1 if D.is_thin(path, root, stems) else 0)
        signals.recent_fix_commits = fix_lookup.get(rel.casefold(), 0)
        if rel.casefold() in revert_lookup:
            signals.reverted = 1
        if found:
            first = found[0]
            scenario = (
                f"scanner-hit ({len(found)}): {first.severity}: {first.text} "
                f"({rel}:{first.line})"
            )
            outcome = "scanner-hit"
            source_name = "scanner"
        else:
            scenario = f"no human label ({rel})"
            outcome = "unlabeled"
            source_name = "none"
        if outcome in HUMAN:
            raise RuntimeError(f"refusing to write a hunt outcome for {rel}")
        rows.append(
            {
                "file": rel,
                "signals": signals.as_dict(),
                "weighted_sum": signals.weighted_sum(),
                "scenario": scenario,
                "outcome": outcome,
                "label_source": source_name,
            }
        )
    return rows


def main() -> int:
    targets = [repo for repo in REPOS if repo.resolve() != KEEP.resolve()]
    print(f"targets={len(targets)} kept_existing={KEEP}")
    wrote = 0
    for root in targets:
        destination = root / ".hive" / "bug-hunt" / "rank-rows.jsonl"
        if destination.is_file():
            print(f"skip existing {destination}")
            continue
        if not root.is_dir():
            print(f"missing {root}")
            continue
        nested = _nested_roots(root, list(REPOS))
        rows = rows_for(root, nested)
        counts: dict[str, int] = {}
        for row in rows:
            counts[str(row["outcome"])] = counts.get(str(row["outcome"]), 0) + 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows)
        destination.write_text(text, encoding="utf-8")
        wrote += 1
        print(
            f"wrote rows={len(rows)} unlabeled={counts.get('unlabeled', 0)} "
            f"scanner_hit={counts.get('scanner-hit', 0)} labeled=0 {destination}"
        )
    print(f"repos_written={wrote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
