"""PP-T9: skip live other_mimi codec; SC-PP11 / PP-E1 fail closed without live Hz."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

_MOSHI_SERVER = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "personaplex-migrate"
    / "moshi"
    / "moshi"
    / "server.py"
)
_JUDGE = Path(__file__).resolve().parents[1] / "scripts" / "personaplex_sc_pp11_judge.py"


def _opus_loop_fn(tree: ast.AST) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "opus_loop":
            return node
    raise AssertionError("opus_loop missing")


def _warmup_fn(tree: ast.AST) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "warmup":
            return node
    raise AssertionError("warmup missing")


def _calls_other_mimi(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and node.attr in {"encode", "decode"}:
            val = node.value
            if isinstance(val, ast.Attribute) and val.attr == "other_mimi":
                return True
    return False


def test_pp_t9_opus_loop_skips_other_mimi_and_stt():
    src = _MOSHI_SERVER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    loop = _opus_loop_fn(tree)
    assert _calls_other_mimi(loop) is False
    assert _calls_other_mimi(_warmup_fn(tree)) is True
    assert "from moshi.stt" not in src
    assert "install_stt" not in src
    assert "run_one_step" not in src
    text = ast.get_source_segment(src, loop) or ast.unparse(loop)
    assert "tokens[:, 1:9]" in text or "tokens[:,1:9]" in text.replace(" ", "")
    assert "asyncio.sleep(0)" in text


def test_pp_t9_sc_pp11_and_pp_e1_fail_closed_without_live_hz():
    spec = importlib.util.spec_from_file_location("personaplex_sc_pp11_judge", _JUDGE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.sc_pp11_holds(after_handshake=True, step_hz=12.5) is True
    assert mod.sc_pp11_holds(after_handshake=True, step_hz=6.4) is False
    assert mod.sc_pp11_holds(after_handshake=True, step_hz=None) is False
    assert mod.sc_pp11_holds(after_handshake=True, step_hz=12.5, is_prefill=True) is False
    assert mod.sc_pp11_holds(after_handshake=True, step_hz=12.5, stt_in_loop=True) is False
    assert mod.sc_pp11_holds(after_handshake=True, step_hz=12.5, labeled_g7=True) is False
    assert (
        mod.pp_e1_holds(
            live_mic=True,
            retrieve=True,
            encoder=True,
            streaming_sum=True,
            consume_steps=2,
            step_hz=12.5,
        )
        is True
    )
    assert (
        mod.pp_e1_holds(
            live_mic=False,
            retrieve=True,
            encoder=True,
            streaming_sum=True,
            consume_steps=2,
            step_hz=12.5,
        )
        is False
    )
    assert (
        mod.pp_e1_holds(
            live_mic=True,
            retrieve=True,
            encoder=True,
            streaming_sum=True,
            consume_steps=2,
            step_hz=12.5,
            labeled_g7=True,
        )
        is False
    )


def test_pp_t9_record_is_fail_closed():
    spec = importlib.util.spec_from_file_location("personaplex_sc_pp11_judge", _JUDGE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    record = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "specs"
        / "PersonaPlex_migrate"
        / "pp-t9-sc-pp11-record.json"
    )
    row = mod.verdict_from_record(record)
    assert row["holds"] is False
    assert row["sc_pp11"] is False
    assert row["pp_e1"] is False
