"""PP-T6: Rule B trigger on text-token user→model change. No rag_token_id 4."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .rag_manager import RAGManager
from .reference_trigger_policy import user_turn_ended


async def maybe_trigger_rule_b(
    handed: bool,
    *,
    rag: RAGManager | None,
    task_group: asyncio.TaskGroup | None,
    context_provider: Callable[[], str] | None,
    handle_reference_fn: Callable[..., Awaitable[None]] | None,
    last_user_line: str,
    prev_speaker: str = "user",
    new_speaker: str = "model",
) -> bool:
    """Start one background generate on user→model. wait_steps=0. Returns True if trigger ran."""
    if not handed or rag is None or task_group is None:
        return False
    if not user_turn_ended(prev_speaker, new_speaker):
        return False
    if not (last_user_line or "").strip():
        return False
    await rag.trigger(
        task_group,
        wait_steps=0,
        handle_reference_fn=handle_reference_fn,
        context_provider=context_provider,
    )
    return True
