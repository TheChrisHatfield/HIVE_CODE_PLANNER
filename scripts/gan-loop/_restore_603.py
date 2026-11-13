"""Write the original 603-row blend back. No generated rows."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan


def locked_parts(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    base = [row for row in rows if not str(row.get("file", "")).startswith("gan/")]
    bugs = [row for row in base if row.get("outcome") != "empty"]
    empties = [row for row in base if row.get("outcome") == "empty"]
    return base, bugs, empties


def composition(empties: list[dict]) -> tuple[int, int, int, int]:
    hard = [
        row
        for row in empties
        if str(row.get("scenario", "")).startswith("hard-negative:")
    ]
    blanks = [
        row
        for row in empties
        if not str(row.get("scenario", "")).startswith("hard-negative:")
    ]
    blank_zero = 0
    for row in blanks:
        signals = row.get("signals")
        values = signals.values() if isinstance(signals, dict) else ()
        if set(values) == {0}:
            blank_zero += 1
    single = 0
    for row in hard:
        signals = row.get("signals")
        values = signals.values() if isinstance(signals, dict) else ()
        lit = sum(1 for value in values if value)
        if lit == 1:
            single += 1
    return len(hard), single, len(blanks), blank_zero


def main() -> None:
    rows = gan.load_rows(gan.MIXED)
    base, bugs, empties = locked_parts(rows)
    if len(base) != 603 or len(bugs) != 398 or len(empties) != 205:
        raise SystemExit(f"cannot restore: {len(base)} {len(bugs)} {len(empties)}")
    recovered = gan.detect.interleave_rows(bugs, empties)
    blend = gan.holdout(recovered)
    if blend["test_pos"] != 120 or blend["test_neg"] != 61 or round(blend["fit_auc"], 3) != 0.946:
        raise SystemExit(f"holdout mismatch: {blend}")
    hard_n, single, blanks_n, blank_zero = composition(empties)
    if hard_n != 130 or blanks_n != 75 or blank_zero != 75 or single != 130:
        raise SystemExit(f"composition {hard_n} {single} {blanks_n} {blank_zero}")
    text = "\n".join(json.dumps(row, separators=(",", ":")) for row in recovered) + "\n"
    gan.MIXED.write_text(text, encoding="utf-8")
    written = gan.load_rows(gan.MIXED)
    check = gan.holdout(written)
    gan_left = sum(1 for row in written if str(row.get("file", "")).startswith("gan/"))
    print(json.dumps({
        "rows": check["rows"],
        "bugs": len(bugs),
        "hard_single": single,
        "blanks": blanks_n,
        "gan_left": gan_left,
        "hand_auc": check["hand_auc"],
        "fit_auc": check["fit_auc"],
        "test_pos": check["test_pos"],
        "test_neg": check["test_neg"],
        "slopes": check["slopes"],
    }))


if __name__ == "__main__":
    main()
