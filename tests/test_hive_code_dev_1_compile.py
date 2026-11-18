from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


SRC = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "HIVE_CODE_DEV_1"
    / "src"
    / "hive_code_dev_1"
    / "dataset"
    / "compile.py"
)


def _mod():
    pkg = types.ModuleType("hive_code_dev_1")
    contracts = types.ModuleType("hive_code_dev_1.contracts")
    dataset = types.ModuleType("hive_code_dev_1.dataset")
    matrix = types.ModuleType("hive_code_dev_1.dataset.matrix")
    features = types.ModuleType("hive_code_dev_1.dataset.structured_features")
    contracts.SandboxTraceRecord = object
    contracts.from_dict = lambda *a, **k: None
    contracts.scheduler_intent_for_arm = lambda arm: arm
    contracts.scheduler_intent_value = lambda intent: intent
    contracts.y_route_labels = lambda record: {}
    matrix.TRAIN_PROFILES = set()
    matrix.VAL_PROFILES = set()
    features.build_structured_features = lambda *a, **k: []
    sys.modules.setdefault("hive_code_dev_1", pkg)
    sys.modules["hive_code_dev_1.contracts"] = contracts
    sys.modules.setdefault("hive_code_dev_1.dataset", dataset)
    sys.modules["hive_code_dev_1.dataset.matrix"] = matrix
    sys.modules["hive_code_dev_1.dataset.structured_features"] = features
    spec = importlib.util.spec_from_file_location("hive_code_dev_1_dataset_compile", SRC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_empty_compile_replaces_stale_jsonl(tmp_path: Path) -> None:
    traces = tmp_path / "traces"
    output = tmp_path / "out"
    traces.mkdir()
    output.mkdir()
    stale = '{"hardware_profile_id": "old"}\n'
    (output / "train.jsonl").write_text(stale, encoding="utf-8")
    (output / "val.jsonl").write_text(stale, encoding="utf-8")
    (output / "augmented.jsonl").write_text(stale, encoding="utf-8")

    compiled = _mod().DatasetCompiler(traces, output).compile()
    assert compiled.train_rows == []
    assert compiled.val_rows == []
    assert compiled.augmented_rows == []
    assert (output / "train.jsonl").read_text(encoding="utf-8") == ""
    assert (output / "val.jsonl").read_text(encoding="utf-8") == ""
    assert (output / "augmented.jsonl").read_text(encoding="utf-8") == ""


def test_feature_row_accepts_missing_routing_hints() -> None:
    ns = types.SimpleNamespace
    record = ns(
        scheduler_signal=ns(
            resource_signals=None,
            routing_hints=None,
            latency_budget=10.0,
            selected_arm=2,
            encoded_scheduler_state=None,
            power_constraint=1.0,
            worker_pool_size=4,
            compute_budget_units=1.0,
            signals_stable=True,
        ),
        outcome=ns(
            stage_confidence=None,
            actual_latency=1.0,
            actual_accuracy=1.0,
            bandit_success=True,
        ),
        context=ns(
            hardware_profile_id="p",
            core_count=4,
            constraint_tier="t",
            scenario_template_id=None,
        ),
        shared_latent_vector=[0.0],
    )
    row = _mod()._feature_row(record)
    assert row["scheduler_intent"] == 2
    assert row["e_core_active"] == 0.0
