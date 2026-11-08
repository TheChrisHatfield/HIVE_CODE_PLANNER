"""Add thin+wiring near-misses one at a time onto the restored 603-row blend."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan

ROOT = Path(__file__).resolve().parent
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

proposals = json.loads((ROOT / "round4-proposals.json").read_text(encoding="utf-8"))
picked = []
for item in proposals:
    scored = gan.score_source(item["name"], item["source"], blend["slopes"])
    if scored["lit"] == ["thin_test", "wiring_hop"] and scored["fitted"] == 4.168 and not scored["findings"]:
        picked.append(scored)
if len(picked) < 8:
    raise SystemExit(f"need 8 thin+wiring files, found {len(picked)}")
picked = picked[:8]
new_rows = gan.accepted_to_rows(picked)
for raw, scored in zip(new_rows, picked):
    raw["file"] = f"gan/{scored['name']}"
    raw["scenario"] = "hard-negative:gan:thin_test,wiring_hop"

print(json.dumps({"step": 0, "added": None, "rows": 603, **{k: blend[k] for k in ("hand_auc", "fit_auc", "test_pos", "test_neg")}}), flush=True)
for count in range(1, 9):
    blended = gan.detect.interleave_rows(bugs, empties + new_rows[:count])
    text = "\n".join(json.dumps(row, separators=(",", ":")) for row in blended) + "\n"
    gan.MIXED.write_text(text, encoding="utf-8")
    after = gan.holdout(gan.load_rows(gan.MIXED))
    tail = "".join("P" if row.get("outcome") != "empty" else "N" for row in blended[-12:])
    print(json.dumps({
        "step": count,
        "added": picked[count - 1]["name"],
        "rows": after["rows"],
        "hand_auc": after["hand_auc"],
        "fit_auc": after["fit_auc"],
        "test_pos": after["test_pos"],
        "test_neg": after["test_neg"],
        "tail": tail,
    }), flush=True)
