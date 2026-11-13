"""Score a proposal batch with the untouched 0.946-blend slopes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_rank_gan as gan


def load_proposals(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise SystemExit(f"proposals must be a JSON list: {path}")
    items: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or "name" not in item or "source" not in item:
            raise SystemExit(f"proposal missing name/source: {item!r}")
        items.append(item)
    return items


def score_proposals(items: list[dict], slopes: list[float], pos_median: float) -> list[dict]:
    rows = []
    for item in items:
        scored = gan.score_source(item["name"], item["source"], slopes)
        scored["fools"] = bool(scored["accepted"] and scored["fitted"] >= pos_median)
        rows.append(scored)
    return rows


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv if argv is None else argv
    if len(argv) < 2:
        raise SystemExit("usage: _score_frozen.py <proposals.json>")
    base = gan.holdout(gan.load_rows(gan.MIXED))
    slopes = base["slopes"]
    items = load_proposals(Path(argv[1]))
    rows = score_proposals(items, slopes, base["pos_median"])
    print(json.dumps({"blend_slopes": slopes, "pos_median": base["pos_median"], "scored": rows}))


if __name__ == "__main__":
    main()
