"""Download gated Llama tokenizer files for MoshiRAG q8 export (ARC multi_arc_encoder).

ARC4 weights live on Runpod volume; this fetch is only what AutoTokenizer needs from
meta-llama/Llama-3.2-3B-Instruct (not the full ~6GB base weights).

Requires HF access to that repo (license accepted) and either:
  - huggingface-cli login, or
  - HF_TOKEN / HUGGINGFACE_HUB_TOKEN in the environment.

Usage:
  py -3.11 scripts/stage_moshi_rag_llama_tokenizer.py
  py -3.11 scripts/stage_moshi_rag_llama_tokenizer.py --out-dir D:\\MOSHI_RAG_HF\\Llama-3.2-3B-Instruct
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

REPO = "meta-llama/Llama-3.2-3B-Instruct"
ALLOW_PATTERNS = [
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "tokenizer.model",
    "*.jinja",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("D:/DRIVE_DOWNLOADS/MOSHI_RAG_HF/Llama-3.2-3B-Instruct"),
        help="Local folder for tokenizer snapshot",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading tokenizer bundle from {REPO} -> {args.out_dir}")
    path = snapshot_download(
        REPO,
        local_dir=str(args.out_dir),
        allow_patterns=ALLOW_PATTERNS,
    )
    print(f"Done: {path}")
    for name in sorted(args.out_dir.iterdir()):
        if name.is_file():
            print(f"  {name.name}  {name.stat().st_size}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        print(
            "Accept the Llama license at https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct "
            "then run: huggingface-cli login",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc