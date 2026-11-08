"""Write the original 603-row blend back. No generated rows."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan

rows = gan.load_rows(gan.MIXED)
base = [row for row in rows if not str(row.get("file", "")).startswith("gan/")]
bugs = [row for row in base if row.get("outcome") != "empty"]
empties = [row for row in base if row.get("outcome") == "empty"]
if len(base) != 603 or len(bugs) != 398 or len(empties) != 205:
    raise SystemExit(f"cannot restore: {len(base)} {len(bugs)} {len(empties)}")
recovered = gan.detect.interleave_rows(bugs, empties)
blend = gan.holdout(recovered)
if blend["test_pos"] != 120 or blend["test_neg"] != 61 or round(blend["fit_auc"], 3) != 0.946:
    raise SystemExit(f"holdout mismatch: {blend}")
hard = [row for row in empties if str(row.get("scenario", "")).startswith("hard-negative:")]
blanks = [row for row in empties if row not in hard]
blank_zero = sum(1 for row in blanks if set(row["signals"].values()) == {0})
single = 0
for row in hard:
    lit = sum(1 for value in row["signals"].values() if value)
    if lit == 1:
        single += 1
if len(hard) != 130 or len(blanks) != 75 or blank_zero != 75 or single != 130:
    raise SystemExit(f"composition {len(hard)} {single} {len(blanks)} {blank_zero}")
text = "\n".join(json.dumps(row, separators=(",", ":")) for row in recovered) + "\n"
gan.MIXED.write_text(text, encoding="utf-8")
check = gan.holdout(gan.load_rows(gan.MIXED))
gan_left = sum(1 for row in gan.load_rows(gan.MIXED) if str(row.get("file", "")).startswith("gan/"))
print(json.dumps({
    "rows": check["rows"],
    "bugs": len(bugs),
    "hard_single": single,
    "blanks": len(blanks),
    "gan_left": gan_left,
    "hand_auc": check["hand_auc"],
    "fit_auc": check["fit_auc"],
    "test_pos": check["test_pos"],
    "test_neg": check["test_neg"],
    "slopes": check["slopes"],
}))
