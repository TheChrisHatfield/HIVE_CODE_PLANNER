"""Weave round 4 and round 6 thin+wiring near-misses into the mixed file."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan

ROOT = Path(__file__).resolve().parent
base = gan.holdout(gan.load_rows(gan.MIXED))
slopes = base["slopes"]
proposals = []
for name in ("round4-proposals.json", "round6-proposals.json"):
    proposals.extend(json.loads((ROOT / name).read_text(encoding="utf-8")))

picked = []
for item in proposals:
    scored = gan.score_source(item["name"], item["source"], slopes)
    if scored["lit"] == ["thin_test", "wiring_hop"] and scored["fitted"] == 4.168 and not scored["findings"]:
        picked.append(scored)

rows = gan.load_rows(gan.MIXED)
bugs = [row for row in rows if row.get("outcome") != "empty"]
empties = [row for row in rows if row.get("outcome") == "empty"]
if len(rows) != 603 or len(bugs) != 398 or len(empties) != 205:
    raise SystemExit(f"mixed file is not the 0.946 blend: {len(rows)} rows, {len(bugs)} bugs, {len(empties)} empties")
if any(str(row.get("file", "")).startswith("gan/") for row in rows):
    raise SystemExit("mixed file already contains gan rows")
new_rows = gan.accepted_to_rows(picked)
# accepted_to_rows only emits accepted items. Mark these as the GAN fold.
for row, scored in zip(new_rows, picked):
    row["scenario"] = "hard-negative:gan:thin_test,wiring_hop"
    row["file"] = f"gan/{scored['name']}"

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
