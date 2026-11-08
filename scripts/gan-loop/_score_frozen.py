"""Score a proposal batch with the untouched 0.946-blend slopes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan

base = gan.holdout(gan.load_rows(gan.MIXED))
slopes = base["slopes"]
proposals = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rows = []
for item in proposals:
    scored = gan.score_source(item["name"], item["source"], slopes)
    scored["fools"] = bool(scored["accepted"] and scored["fitted"] >= base["pos_median"])
    rows.append(scored)
print(json.dumps({"blend_slopes": slopes, "pos_median": base["pos_median"], "scored": rows}))
