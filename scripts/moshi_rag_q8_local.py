"""Local int8 (q8) export for a Moshi PyTorch repo. CPU by default, no Hugging Face upload.

Adapted from kyutai-labs/moshi-rag scripts/export_quantized.py (upstream loads on cuda and
uploads). Here the model loads on CPU, the q8 safetensors and a rewritten config.json are
written to a local folder, and the mimi/tokenizer paths point back at the source repo.

Requires bitsandbytes with a working int8 quantize path. QLinear in moshi/utils/quantize.py
calls bitsandbytes int8_vectorwise_quant, so this fails at that step if the install has no CPU
kernel. Set HF_HOME to a drive with free space before running.

Usage:
  py -3.11 scripts/moshi_rag_q8_local.py kyutai/moshika-rag-pytorch-bf16 <out_dir>
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download
from safetensors.torch import save_file

from moshi.models import loaders
from moshi.utils.quantize import replace_linear_with_qlinear


def main() -> None:
    parser = argparse.ArgumentParser("moshi_rag_q8_local")
    parser.add_argument("hf_repo", help="Source repo, e.g. kyutai/moshika-rag-pytorch-bf16")
    parser.add_argument("out_dir", type=Path, help="Local folder to write q8 weights and config.json")
    parser.add_argument("--device", default="cpu", help="Device for the load and quantize step (default cpu)")
    parser.add_argument(
        "--arc-tokenizer",
        default=None,
        help="Override multi_arc_encoder tokenizer_name (local path or HF repo, e.g. pcuenq/Llama-3.2-1B-Instruct-tokenizer)",
    )
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading base checkpoint (from HF cache when already downloaded).")
    hf_config_path = Path(hf_hub_download(args.hf_repo, "config.json"))
    config = json.loads(hf_config_path.read_text(encoding="utf-8"))
    config_path = None
    if args.arc_tokenizer:
        apply_arc_tokenizer(config, args.arc_tokenizer)
        config_path = out_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print(f"ARC tokenizer_name -> {args.arc_tokenizer} in {config_path} (HF cache unchanged)")
    info = loaders.CheckpointInfo.from_hf_repo(args.hf_repo, config_path=config_path)
    print(f"Building model on {args.device}.")
    model = info.get_moshi(fuse_lora=True, device=args.device)
    print("Quantizing linear layers to int8 (bitsandbytes).")
    replace_linear_with_qlinear(model)

    old_name, old_ext = info.moshi_weights.name.rsplit(".", 1)
    new_name = f"{old_name}.q8.{old_ext}"
    weights_path = out_dir / new_name
    print(f"Writing {weights_path}")
    save_file(model.state_dict(), str(weights_path))
    print(f"Checkpoint size: {weights_path.stat().st_size / 1e9:.2f} GB")

    readme = hf_hub_download(args.hf_repo, "README.md") if _exists(args.hf_repo, "README.md") else None
    if readme:
        shutil.copy(readme, out_dir / "README.md")

    config["moshi_name"] = new_name
    config["quantize"] = True
    for key in ("mimi_name", "tokenizer_name"):
        value = config.get(key)
        if value is None:
            continue
        if not value.startswith("hf://"):
            config[key] = f"hf://{args.hf_repo}/{value}"
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Done. Point moshi.server at this folder with --config {out_dir / 'config.json'}")


def apply_arc_tokenizer(config: dict, tokenizer: str) -> dict:
    """Set ARC tokenizer_name on an in-memory config. Does not write the HF cache."""
    try:
        arc = config["conditioners"]["reference_with_time"]["multi_arc_encoder"]
    except (KeyError, TypeError) as exc:
        raise SystemExit(
            "config.json has no conditioners.reference_with_time.multi_arc_encoder"
        ) from exc
    if not isinstance(arc, dict):
        raise SystemExit("multi_arc_encoder is not a mapping")
    arc["tokenizer_name"] = tokenizer
    return config


def _exists(repo: str, filename: str) -> bool:
    from huggingface_hub import HfApi

    return HfApi().file_exists(repo, filename)


if __name__ == "__main__":
    main()
