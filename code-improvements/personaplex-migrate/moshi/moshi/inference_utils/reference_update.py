"""PP-T5 / PP18: encoder /embed into LMGen pending streaming_sum."""

from __future__ import annotations

import logging
import os

import torch

from .reference_hold import hold_reference_frames, reference_hold_factor
from .utils import get_conditioning_remote_async

logger = logging.getLogger(__name__)


async def async_update_reference(lm_gen, reference_text: str, encoder_url: str | None = None) -> None:
    """POST /embed, hold (default 1), update_streaming_sum_tensors. Failures skip; duplex continues."""
    url = (encoder_url if encoder_url is not None else os.environ.get("REFERENCE_ENCODER_URL") or "").strip()
    if not url:
        logger.info("[Reference] REFERENCE_ENCODER_URL unset; skip encoder update")
        return
    try:
        tensor = await get_conditioning_remote_async(text=reference_text or "", encoder_url=url)
    except Exception:
        logger.exception("[Reference] encoder /embed failed; duplex continues")
        return
    try:
        tensor = hold_reference_frames(tensor, reference_hold_factor())
        lm_gen.update_streaming_sum_tensors([tensor])
    except Exception:
        logger.exception("[Reference] streaming_sum update failed; duplex continues")
