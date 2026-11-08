"""Replace the identical GAN rows with four balanced near-miss families."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan

ROOT = Path(__file__).resolve().parent
HANDFUL = 2
MIX_CAP = 2
FAMILIES = {
    "thin": ["thin_test"],
    "dead": ["dead_setting"],
    "wiring": ["wiring_hop"],
    "mix-thin-dead": ["thin_test", "dead_setting"],
    "mix-thin-split": ["thin_test", "split_stores"],
    "mix-wiring-dead": ["wiring_hop", "dead_setting"],
    "mix-wiring-split": ["wiring_hop", "split_stores"],
}

rows = gan.load_rows(gan.MIXED)
base_rows = [row for row in rows if not str(row.get("file", "")).startswith("gan/")]
bugs = [row for row in base_rows if row.get("outcome") != "empty"]
empties = [row for row in base_rows if row.get("outcome") == "empty"]
if len(base_rows) != 603 or len(bugs) != 398 or len(empties) != 205:
    raise SystemExit(
        f"restored blend is not 603/398/205: {len(base_rows)} {len(bugs)} {len(empties)}"
    )

recovered = gan.detect.interleave_rows(bugs, empties)
blend = gan.holdout(recovered)
if blend["test_pos"] != 120 or blend["test_neg"] != 61:
    raise SystemExit(f"recovered holdout is not the 0.946 cut: {blend}")
slopes = blend["slopes"]
proposals = json.loads((ROOT / "round7-proposals.json").read_text(encoding="utf-8"))
scored = []
for item in proposals:
    row = gan.score_source(item["name"], item["source"], slopes)
    row["fools"] = bool(row["accepted"] and row["fitted"] >= blend["pos_median"])
    scored.append(row)

buckets = {name: [] for name in FAMILIES}
rejected = []
for row in scored:
    matched = None
    for name, lit in FAMILIES.items():
        if row["lit"] == lit and not row["findings"]:
            matched = name
            break
    if matched is None:
        rejected.append({"name": row["name"], "lit": row["lit"], "findings": row["findings"]})
        continue
    cap = MIX_CAP if matched.startswith("mix-") else HANDFUL
    if matched.startswith("mix-"):
        mix_count = sum(len(buckets[name]) for name in buckets if name.startswith("mix-"))
        if mix_count >= MIX_CAP:
            continue
    if len(buckets[matched]) < cap:
        buckets[matched].append(row)

picked = [row for group in buckets.values() for row in group]
if sum(1 for row in picked if row["lit"] == ["thin_test"]) != HANDFUL:
    raise SystemExit("thin family is not two files")
if sum(1 for row in picked if row["lit"] == ["dead_setting"]) != HANDFUL:
    raise SystemExit("dead family is not two files")
if sum(1 for row in picked if row["lit"] == ["wiring_hop"]) != HANDFUL:
    raise SystemExit("wiring family is not two files")
if sum(1 for row in picked if len(row["lit"]) == 2) != MIX_CAP:
    raise SystemExit("mix family is not two files")
new_rows = gan.accepted_to_rows(picked)
for raw, row in zip(new_rows, picked):
    family = next(name for name, lit in FAMILIES.items() if row["lit"] == lit)
    raw["file"] = f"gan/{row['name']}"
    raw["scenario"] = "hard-negative:gan-family:" + family

blended = gan.detect.interleave_rows(bugs, empties + new_rows)
text = "\n".join(json.dumps(row, separators=(",", ":")) for row in blended) + "\n"
gan.MIXED.write_text(text, encoding="utf-8")
after = gan.holdout(gan.load_rows(gan.MIXED))
tail = "".join("P" if row.get("outcome") != "empty" else "N" for row in blended[-24:])
counts = {name: len(group) for name, group in buckets.items()}
print(json.dumps({
    "blend_slopes": slopes,
    "pos_median": blend["pos_median"],
    "family_counts": counts,
    "rejected": rejected,
    "scored": [{k: row[k] for k in ("name", "lit", "hand", "fitted", "findings", "fools")} for row in scored],
    "added": len(new_rows),
    "rows": len(blended),
    "tail": tail,
    "restored": {k: blend[k] for k in ("hand_auc", "fit_auc", "test_pos", "test_neg", "rows")},
    "after": after,
}))
