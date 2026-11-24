"""Export a local wav persona to a .pt embedding file (PP-T15 / PP16).

No Hugging Face download. Requires local --moshi-weight, --mimi-weight, --tokenizer, and --wav.
Live model load is operator-run; this module's path helper is what tests pin.
"""

from __future__ import annotations

import argparse
from os.path import splitext
from pathlib import Path


def pt_out_path(wav: str) -> str:
    return splitext(wav)[0] + ".pt"


def require_local_files(moshi_weight: str, mimi_weight: str, tokenizer: str, wav: str) -> None:
    missing = [
        label
        for label, path in (
            ("moshi-weight", moshi_weight),
            ("mimi-weight", mimi_weight),
            ("tokenizer", tokenizer),
            ("wav", wav),
        )
        if not path or not Path(path).is_file()
    ]
    if missing:
        raise SystemExit("export_voice_pt: missing local files (no HF): " + ", ".join(missing))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="export_voice_pt")
    p.add_argument("--wav", required=True)
    p.add_argument("--moshi-weight", required=True)
    p.add_argument("--mimi-weight", required=True)
    p.add_argument("--tokenizer", required=True)
    p.add_argument("--device", default="cuda")
    args = p.parse_args(argv)
    require_local_files(args.moshi_weight, args.mimi_weight, args.tokenizer, args.wav)
    # Operator-run: load LMGen with save_voice_prompt_embeddings=True and write pt_out_path(wav).
    print(pt_out_path(args.wav))


if __name__ == "__main__":
    main()
