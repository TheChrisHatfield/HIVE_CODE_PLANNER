"""Validate low-band near-misses, then add them one at a time."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan

ROOT = Path(__file__).resolve().parent
EXPECT = {
    "sauna_timer.py": ["thin_test", "dead_setting"],
    "film_roll.py": ["thin_test", "dead_setting"],
    "kiln_hold.py": ["thin_test", "dead_setting"],
    "harbor_slip.py": ["thin_test", "split_stores"],
    "orchard_row.py": ["thin_test", "split_stores"],
    "booth_sign.py": ["thin_test", "split_stores"],
    "test_radio_probe.py": ["wiring_hop"],
    "test_loom_probe.py": ["wiring_hop"],
}
WEAK_FITTED_CAP = 3.42
WEAK_FITTED_FLOOR = 1.0


def weak_ok(scored: dict, expect: list[str] | None) -> bool:
    """True when a scored proposal is an accepted low-band match for EXPECT."""
    if expect is None or not scored.get("accepted"):
        return False
    if scored["lit"] != expect or scored["findings"]:
        return False
    fitted = scored["fitted"]
    if expect == ["wiring_hop"]:
        return fitted < WEAK_FITTED_CAP
    return WEAK_FITTED_FLOOR <= fitted < WEAK_FITTED_CAP


def label_weak_rows(picked: list[dict]) -> list[dict]:
    new_rows = gan.accepted_to_rows(picked)
    if len(new_rows) != len(picked):
        raise SystemExit(
            f"accepted_to_rows dropped {len(picked) - len(new_rows)} weak picks"
        )
    for raw, scored in zip(new_rows, picked, strict=True):
        raw["file"] = f"gan/{scored['name']}"
        raw["scenario"] = "hard-negative:gan-weak:" + ",".join(scored["lit"])
    return new_rows


def main() -> None:
    rows = gan.load_rows(gan.MIXED)
    base_rows = [row for row in rows if not str(row.get("file", "")).startswith("gan/")]
    bugs = [row for row in base_rows if row.get("outcome") != "empty"]
    empties = [row for row in base_rows if row.get("outcome") == "empty"]
    if len(base_rows) != 603 or len(bugs) != 398 or len(empties) != 205:
        raise SystemExit(f"base is not 603/398/205: {len(base_rows)} {len(bugs)} {len(empties)}")
    recovered = gan.detect.interleave_rows(bugs, empties)
    blend = gan.holdout(recovered)
    if blend["test_pos"] != 120 or blend["test_neg"] != 61 or round(blend["fit_auc"], 3) != 0.946:
        raise SystemExit(f"recovered blend is not the 0.946 cut: {blend}")

    proposals = json.loads((ROOT / "round8-proposals.json").read_text(encoding="utf-8"))
    picked = []
    for item in proposals:
        scored = gan.score_source(item["name"], item["source"], blend["slopes"])
        scored["fools"] = bool(scored["accepted"] and scored["fitted"] >= blend["pos_median"])
        if not weak_ok(scored, EXPECT.get(item["name"])):
            raise SystemExit(f"rejected {item['name']}: {scored}")
        picked.append(scored)

    new_rows = label_weak_rows(picked)

    print(json.dumps({
        "step": 0,
        "added": None,
        "rows": 603,
        "hand_auc": blend["hand_auc"],
        "fit_auc": blend["fit_auc"],
        "test_pos": blend["test_pos"],
        "test_neg": blend["test_neg"],
        "checked": [{"name": row["name"], "lit": row["lit"], "fitted": row["fitted"], "hand": row["hand"]} for row in picked],
    }), flush=True)
    for count in range(1, 9):
        blended = gan.detect.interleave_rows(bugs, empties + new_rows[:count])
        text = "\n".join(json.dumps(row, separators=(",", ":")) for row in blended) + "\n"
        gan.MIXED.write_text(text, encoding="utf-8")
        after = gan.holdout(gan.load_rows(gan.MIXED))
        print(json.dumps({
            "step": count,
            "added": picked[count - 1]["name"],
            "file_fitted": picked[count - 1]["fitted"],
            "rows": after["rows"],
            "hand_auc": after["hand_auc"],
            "fit_auc": after["fit_auc"],
            "test_pos": after["test_pos"],
            "test_neg": after["test_neg"],
        }), flush=True)


if __name__ == "__main__":
    main()
