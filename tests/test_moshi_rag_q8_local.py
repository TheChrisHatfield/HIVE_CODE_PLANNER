"""q8 local export: ARC tokenizer patch must not rewrite the HF hub cache."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "moshi_rag_q8_local.py"


def _apply():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "apply_arc_tokenizer"
    )
    ns: dict = {"SystemExit": SystemExit}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SCRIPT), "exec"), ns)
    return ns["apply_arc_tokenizer"]


def test_apply_arc_tokenizer_edits_memory_only() -> None:
    apply = _apply()
    config = {
        "conditioners": {
            "reference_with_time": {"multi_arc_encoder": {"tokenizer_name": "old"}}
        }
    }
    apply(config, "pcuenq/local-tok")
    assert (
        config["conditioners"]["reference_with_time"]["multi_arc_encoder"]["tokenizer_name"]
        == "pcuenq/local-tok"
    )


def test_apply_arc_tokenizer_rejects_a_config_without_arc() -> None:
    apply = _apply()
    with pytest.raises(SystemExit, match="multi_arc_encoder"):
        apply({"conditioners": {}}, "tok")


def test_export_script_does_not_patch_the_hf_cache_file() -> None:
    src = SCRIPT.read_text(encoding="utf-8")
    assert "_patch_arc_tokenizer_in_hf_cache" not in src
    assert "from_hf_repo(args.hf_repo, config_path=config_path)" in src
    assert "--config-path" not in src
    assert "with --config " in src
