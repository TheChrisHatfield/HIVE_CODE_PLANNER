"""PP-T11: cutover default stays moshi_q8 until PP13 gates hold."""

from __future__ import annotations

from hive_planner.voice_bot import VoiceBotConfig
from hive_planner.voice_personaplex_cutover import (
    CUTOVER_GATES,
    NON_BLOCKING,
    cutover_allowed,
    default_speech_child,
    default_speech_child_from_record,
)


def _open(**overrides) -> dict:
    row = {name: True for name in CUTOVER_GATES}
    row["encoder_remains"] = True
    row["moshika_speech_weights_required"] = False
    row.update(overrides)
    return row


def test_pp_t11_voicebot_default_stays_q8_while_gates_fail():
    assert VoiceBotConfig().speech_child == "moshi_q8"
    assert VoiceBotConfig().encoder_autostart is True
    assert default_speech_child_from_record() == VoiceBotConfig().speech_child
    assert cutover_allowed({}) is False


def test_pp_t11_all_gates_true_selects_personaplex():
    assert default_speech_child(_open()) == "personaplex"
    assert cutover_allowed(_open()) is True


def test_pp_t11_any_missing_gate_fail_closed():
    for name in CUTOVER_GATES:
        gates = _open(**{name: False})
        assert cutover_allowed(gates) is False
        assert default_speech_child(gates) == "moshi_q8"


def test_pp_t11_sc_pp9_and_10_do_not_block():
    assert NON_BLOCKING == ("sc_pp9", "sc_pp10")
    assert cutover_allowed(_open(sc_pp9=False, sc_pp10=False)) is True
    assert cutover_allowed(_open(sc_pp9=True, sc_pp10=True)) is True


def test_pp_t11_refuses_moshika_speech_requirement_and_dropped_encoder():
    assert cutover_allowed(_open(moshika_speech_weights_required=True)) is False
    assert cutover_allowed(_open(encoder_remains=False)) is False
