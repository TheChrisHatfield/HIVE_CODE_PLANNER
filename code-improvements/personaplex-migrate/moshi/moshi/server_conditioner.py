# Copyright (c) Kyutai, all rights reserved.
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""FastAPI HTTP service around `ConditionProvider` + `ConditionFuser`.

Loads conditioner weights from a Moshi safetensors checkpoint and runs
`prepare` / forward for whatever text conditioners the LM JSON config defines.
Tensor conditioner inputs are not accepted.

Example usage:
    python -m moshi.moshi.server_conditioner \
        --config  hf://kyutai/moshika-rag-pytorch-bf16/config.json \
        --moshi-weight hf://kyutai/moshika-rag-pytorch-bf16/model.safetensors \
        --cuda-device 0 \
        --conditioner reference_with_time
"""

import argparse
import json
from typing import Any

import torch
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
import uvicorn

from .models import loaders
from .conditioners import ConditionAttributes
from safetensors.torch import load_file, save
import logging

logger = logging.getLogger(__name__)


class ConditionEncodeRequest(BaseModel):
    """A text string is passed as the text input to every text conditioner (see GET /spec)."""

    text: str = ""


def subset_lm_config_conditioners(lm_config: dict[str, Any], name: str) -> None:
    """Keep only ``name`` in ``lm_config['conditioners']`` and trim fuser lists accordingly."""
    all_cfg = lm_config.get("conditioners")
    if not isinstance(all_cfg, dict) or not all_cfg:
        raise RuntimeError("LM config has no non-empty 'conditioners' object")

    if name not in all_cfg:
        raise ValueError(f"--conditioner {name!r} not in config. Available: {sorted(all_cfg)}")

    lm_config["conditioners"] = {name: all_cfg[name]}
    keep = {name}

    fuser = dict(lm_config.get("fuser") or {})
    for m in ("sum", "streaming_sum", "prepend", "cross"):
        lst = fuser.get(m)
        if isinstance(lst, list):
            fuser[m] = [x for x in lst if x in keep]
    lm_config["fuser"] = fuser


class EncoderService:
    """Runs the configured `ConditionProvider` and fuser."""

    def __init__(
        self,
        config: str,
        moshi_weight: str,
        conditioner: str,
        device: str = "cuda",
    ):
        """
        Args:
            config: Path to the lm config JSON file (e.g. config.json).
            moshi_weight: Safetensors path or ``hf://...`` URI for conditioner weights.
            device: Device string (e.g. ``cuda:0``, ``cpu``).
            conditioner: If set, only this conditioner is loaded from the config (and checkpoint);
                fuser ``sum`` / ``streaming_sum`` / ``prepend`` / ``cross`` entries are trimmed
                to that name.
        """
        self.device = device

        config_path = loaders.hf_get(config)
        raw_config = json.loads(config_path.read_text())
        lm_config = dict(raw_config)
        for key in [
            "moshi_name",
            "mimi_name",
            "mimi_config_name",
            "tokenizer_name",
            "lora_name",
            "model_type",
            "lm_gen_config",
            "tts_config",
            "stt_config",
            "model_id",
        ]:
            lm_config.pop(key, None)

        subset_lm_config_conditioners(lm_config, conditioner)
        logger.info(f"Using conditioner: {conditioner}")

        logger.info(f"Loading conditioners on {device}")
        self.condition_provider = loaders.get_conditioner_provider(lm_config["dim"], device, lm_config)
        self.fuser = loaders.get_condition_fuser(lm_config)
        self.conditioner_name = conditioner
        logger.info("Conditioners loaded successfully")

        if not self.condition_provider.conditioners:
            raise RuntimeError("Model does not have a condition provider")

        self._load_conditioner_weights_from_moshi_checkpoint(moshi_weight)
        for _name, cond in self.condition_provider.conditioners.items():
            load_weights = getattr(cond, "load_weights", None)
            if callable(load_weights):
                logger.info("Loading weights for %s", _name)
                load_weights()

    def _load_conditioner_weights_from_moshi_checkpoint(self, moshi_weight: str) -> None:
        if not moshi_weight:
            raise RuntimeError("Missing --moshi-weight argument required for conditioner weights")

        model_weight_path = loaders.hf_get(moshi_weight)
        if not str(moshi_weight).endswith(".safetensors"):
            raise RuntimeError("moshi-weight must point to a safetensors file.")
        if not model_weight_path.exists():
            raise RuntimeError(f"Could not resolve moshi-weight path: {moshi_weight}")

        # Session 27: read only this conditioner's keys. load_file() maps the full
        # 15 GB checkpoint and access-violates on Windows (torch storage __getitem__).
        # Session 27: the safetensors torch/mmap path still access-violates on this host
        # (torch storage __getitem__). Read only this conditioner's byte ranges with plain
        # file I/O and build tensors with torch.frombuffer.
        import json as _json
        import struct as _struct

        _prefix = f"condition_provider.conditioners.{self.conditioner_name}."
        _dtype_map = {
            "BF16": torch.bfloat16,
            "F16": torch.float16,
            "F32": torch.float32,
            "I64": torch.int64,
            "I32": torch.int32,
            "U8": torch.uint8,
        }
        checkpoint = {}
        with open(str(model_weight_path), "rb") as _fh:
            (_hlen,) = _struct.unpack("<Q", _fh.read(8))
            _header = _json.loads(_fh.read(_hlen))
            _base = 8 + _hlen
            for _k, _meta in _header.items():
                if _k == "__metadata__" or not _k.startswith(_prefix):
                    continue
                _start, _end = _meta["data_offsets"]
                _fh.seek(_base + _start)
                _buf = bytearray(_fh.read(_end - _start))
                _t = torch.frombuffer(_buf, dtype=_dtype_map[_meta["dtype"]])
                checkpoint[_k] = _t.reshape(_meta["shape"]).clone()
        if self.conditioner_name not in self.condition_provider.conditioners:
            raise RuntimeError(f"Conditioner {self.conditioner_name} not found in config")
        self._load_from_checkpoint(checkpoint, self.conditioner_name, strict=False)

    def _load_from_checkpoint(
        self,
        checkpoint: dict[str, Any],
        conditioner_name: str,
        strict: bool,
    ) -> None:
        prefix = f"condition_provider.conditioners.{conditioner_name}."
        state = {
            key.removeprefix(prefix): value.to(torch.device(self.device))
            for key, value in checkpoint.items()
            if key.startswith(prefix)
        }
        if not state:
            raise RuntimeError(
                f"No weights found in checkpoint for conditioner "
                f"'{conditioner_name}'. Expected keys starting with '{prefix}'"
            )

        logger.info(
            "Checkpoint keys for conditioner '%s': %s",
            conditioner_name,
            list(state.keys()),
        )
        module = self.condition_provider.conditioners[conditioner_name]
        module.load_state_dict(state, strict=strict)
        logger.info(
            "Loaded conditioner '%s'",
            conditioner_name,
        )

    def spec(self) -> dict[str, Any]:
        return {
            "conditioner_name": self.conditioner_name,
            "text_conditioners": list(self.condition_provider.text_conditions),
            "tensor_conditioners": list(self.condition_provider.tensor_conditions),
            "fuser": {k: list(v) for k, v in self.fuser.fuse2cond.items()},
        }

    def encode(self, text: str) -> torch.Tensor:
        conditions = [
            ConditionAttributes(
                text={self.conditioner_name: text},
                tensor={},
            )
        ]

        prepared = self.condition_provider.prepare(conditions)
        condition_tensors = self.condition_provider(prepared)
        fuse_method = self.fuser.cond2fuse[self.conditioner_name]
        if fuse_method == "streaming_sum":
            output_tensor = self.fuser.get_streaming_sum(condition_tensors)
        elif fuse_method == "sum":
            output_tensor = self.fuser.get_sum(condition_tensors)
        elif fuse_method == "prepend":
            output_tensor = self.fuser.get_prepend(condition_tensors)
        elif fuse_method == "cross":
            output_tensor = self.fuser.get_cross(condition_tensors)
        else:
            raise ValueError(f"Invalid fuse method: {fuse_method}")
        return output_tensor


# Global service instance
_service: EncoderService | None = None


def get_service() -> EncoderService:
    """Get the global Arc Encoder service instance."""
    if _service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Arc Encoder service not initialized"
        )
    return _service


# FastAPI app
app = FastAPI(title="Condition encoder service", version="0.1.0")


@app.on_event("startup")
def startup_event():
    """Log startup information."""
    logger.info("Condition encoder service (app) process started")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "condition_encoder"}


@app.get("/spec")
def conditioner_spec():
    """JSON describing conditioners (same string is sent to each text conditioner on /embed)."""
    return Response(json.dumps(get_service().spec()), media_type="application/json")


@app.post("/embed")
def embed_text(request: ConditionEncodeRequest) -> Response:
    """
    Encode using the LM config's text conditioners.

    Request body (JSON): ``{"text": "<string>"}`` — the same value is supplied to every
    text conditioner listed in GET /spec ``text_conditioners``.

    Response (JSON object): keys are fuse methods ``sum``, ``prepend``, ``cross``,
    ``streaming_sum``. Each value is either ``null`` or an object
    ``{"format": "safetensors", "encoding": "base64", "payload": "<one tensor saved as safetensors key tensor>"}``.
    """
    service = get_service()

    try:
        condition_tensor = service.encode(request.text)
        return serialize_embeddings(condition_tensor)
    except Exception as e:
        logger.error(f"Error encoding text: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error encoding text: {str(e)}")


def serialize_embeddings(
    condition_tensor: torch.Tensor,
) -> Response:
    try:
        tensor_bytes = save({"tensor": condition_tensor.cpu()})
    except Exception as e:
        raise RuntimeError(f"Error serializing embeddings: {e}")

    logger.info(f"Serialized condition tensor, size: {len(tensor_bytes)} bytes")

    return Response(
        content=bytes(tensor_bytes),
        media_type="application/octet-stream",
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="HTTP service: run ConditionProvider + fuser for an LM conditioner JSON config.",
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the lm config JSON file (e.g. hf://kyutai/moshika-rag-pytorch-bf16/config.json).",
    )
    parser.add_argument(
        "--moshi-weight",
        type=str,
        required=True,
        help="Path to Moshi safetensors checkpoint (conditioner weights) (e.g. hf://kyutai/moshika-rag-pytorch-bf16/model.safetensors).",
    )
    parser.add_argument(
        "--conditioner",
        type=str,
        required=True,
        metavar="NAME",
        help="Single conditioner name from the LM config (weights loaded for this module only).",
    )
    parser.add_argument(
        "--cuda-device",
        type=str,
        default="0",
        help="CUDA device to use (e.g., '0' for cuda:0, 'cpu' for CPU, default: '0')",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to bind to (default: 8001)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    # Determine device
    if args.cuda_device.lower() == "cpu":
        device = "cpu"
    else:
        device = f"cuda:{args.cuda_device}"

    # Initialize service
    global _service
    _service = EncoderService(
        config=args.config,
        moshi_weight=args.moshi_weight,
        device=device,
        conditioner=args.conditioner,
    )

    # Run server
    logger.info(f"Starting Arc Encoder Service on {args.host}:{args.port}")
    logger.info(f"Using device: {device}")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level="info",
    )


if __name__ == "__main__":
    main()
