"""Weave round 4 and round 6 thin+wiring near-misses into the mixed file."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan

ROOT = Path(__file__).resolve().parent
BEST_LIT = ["thin_test", "wiring_hop"]
BEST_FITTED = 4.168


def is_best_pick(scored: dict) -> bool:
    """Accepted thin+wiring near-miss at the frozen 4.168 fitted score."""
    return bool(
        scored.get("accepted")
        and scored["lit"] == BEST_LIT
        and scored["fitted"] == BEST_FITTED
        and not scored["findings"]
    )


def label_best_rows(picked: list[dict]) -> list[dict]:
    new_rows = gan.accepted_to_rows(picked)
    if len(new_rows) != len(picked):
        raise SystemExit(
            f"accepted_to_rows dropped {len(picked) - len(new_rows)} best picks"
        )
    for row, scored in zip(new_rows, picked, strict=True):
        row["scenario"] = "hard-negative:gan:thin_test,wiring_hop"
        row["file"] = f"gan/{scored['name']}"
    return new_rows


def main() -> None:
    base = gan.holdout(gan.load_rows(gan.MIXED))
    slopes = base["slopes"]
    proposals = []
    for name in ("round4-proposals.json", "round6-proposals.json"):
        proposals.extend(json.loads((ROOT / name).read_text(encoding="utf-8")))

    picked = []
    for item in proposals:
        scored = gan.score_source(item["name"], item["source"], slopes)
        if is_best_pick(scored):
            picked.append(scored)

    rows = gan.load_rows(gan.MIXED)
    bugs = [row for row in rows if row.get("outcome") != "empty"]
    empties = [row for row in rows if row.get("outcome") == "empty"]
    if len(rows) != 603 or len(bugs) != 398 or len(empties) != 205:
        raise SystemExit(f"mixed file is not the 0.946 blend: {len(rows)} rows, {len(bugs)} bugs, {len(empties)} empties")
    if any(str(row.get("file", "")).startswith("gan/") for row in rows):
        raise SystemExit("mixed file already contains gan rows")
    new_rows = label_best_rows(picked)

    blended = gan.detect.interleave_rows(bugs, empties + new_rows)
    text = "\n".join(json.dumps(row, separators=(",", ":")) for row in blended) + "\n"
    gan.MIXED.write_text(text, encoding="utf-8")
    after = gan.holdout(blended)
    tail = "".join("P" if row.get("outcome") != "empty" else "N" for row in blended[-24:])
    print(json.dumps({
        "before_rows": len(rows),
        "bugs": len(bugs),
        "empties_before": len(empties),
        "added": len(new_rows),
        "after_rows": len(blended),
        "tail": tail,
        "before": {k: base[k] for k in ("hand_auc", "fit_auc", "test_pos", "test_neg", "rows")},
        "after": after,
    }))


if __name__ == "__main__":
    main()
