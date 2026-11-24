"""PP-T11 / PP13: default `speech_child` flips only when live gates hold (SC-PP8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

CUTOVER_GATES = (
    "sc_pp2",
    "sc_pp3",
    "sc_pp6",
    "sc_pp7",
    "sc_pp11",
    "pp_t9",
)
# SC-PP9 / SC-PP10 are P2 and do not block this default (G204).
NON_BLOCKING = ("sc_pp9", "sc_pp10")

GATES_RECORD = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "specs"
    / "PersonaPlex_migrate"
    / "pp-t11-cutover-gates.json"
)


def cutover_allowed(gates: Mapping[str, Any] | None) -> bool:
    """True only when every PP13 gate is explicitly true. Missing keys fail closed."""
    data = dict(gates or {})
    if bool(data.get("moshika_speech_weights_required")):
        return False
    if data.get("encoder_remains") is False:
        return False
    return all(bool(data.get(name)) for name in CUTOVER_GATES)


def default_speech_child(gates: Mapping[str, Any] | None) -> str:
    return "personaplex" if cutover_allowed(gates) else "moshi_q8"


def load_cutover_gates(path: Path | None = None) -> dict[str, Any]:
    target = path or GATES_RECORD
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def default_speech_child_from_record(path: Path | None = None) -> str:
    """Voice_Bot dataclass default stays moshi_q8 until this returns personaplex."""
    return default_speech_child(load_cutover_gates(path))
