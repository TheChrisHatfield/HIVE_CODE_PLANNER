"""PP-T16 / PP17: Hive hold-drop maps to NVIDIA ``is_alive`` (websocket closed)."""

from __future__ import annotations


def websocket_prefill_alive(close_flag: bool, ws_closed: bool) -> bool:
    """False when the Hive client closed or the aiohttp socket is closed.

    ``ServerState.handle_chat`` holds slot 1 (``self.lock``) through prefill.
    ``step_system_prompts_async(..., is_alive=...)`` yields when this is False,
    so a second handshake can take the lock.
    """
    return not (bool(close_flag) or bool(ws_closed))
