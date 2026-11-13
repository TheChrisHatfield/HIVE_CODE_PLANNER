"""Dataset compilation + distribution-faithful augmentation (Task 8)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from hive_code_dev_1.contracts import (
    SandboxTraceRecord,
    from_dict,
    scheduler_intent_for_arm,
    scheduler_intent_value,
    y_route_labels,
)
from hive_code_dev_1.dataset.matrix import TRAIN_PROFILES, VAL_PROFILES
from hive_code_dev_1.dataset.structured_features import build_structured_features


@dataclass
class CompiledDataset:
    train_rows: list[dict] = field(default_factory=list)
    val_rows: list[dict] = field(default_factory=list)
    augmented_rows: list[dict] = field(default_factory=list)


def _feature_row(record: SandboxTraceRecord) -> dict:
    sig = record.scheduler_signal
    uncertainty = float(record.outcome.stage_confidence or 0.5)
    task_value = 0.5
    structured = build_structured_features(
        sig,
        context=record.context,
        uncertainty_score=uncertainty,
        task_value_score=task_value,
    )
    resources = sig.resource_signals or {}
    hints = sig.routing_hints or {}
    return {
        "hardware_profile_id": record.context.hardware_profile_id,
        "core_count": record.context.core_count or sig.worker_pool_size,
        "constraint_tier": record.context.constraint_tier,
        "latency_budget": sig.latency_budget,
        "selected_arm": int(sig.selected_arm),
        "scheduler_intent": sig.routing_hints.get(
            "scheduler_intent",
            scheduler_intent_value(scheduler_intent_for_arm(sig.selected_arm)),
        ),
        "shared_latent_vector": list(record.shared_latent_vector),
        "scheduler_latent": list(sig.encoded_scheduler_state or record.shared_latent_vector),
        "structured_tensor": structured,
        "uncertainty_score": uncertainty,
        "task_value_score": task_value,
        "power_constraint": float(sig.power_constraint),
        "worker_pool_size": int(sig.worker_pool_size),
        "compute_budget_units": float(sig.compute_budget_units),
        "signals_stable": bool(sig.signals_stable),
        "free_cores": float(resources.get("free_cores", 0.0)),
        "queued_tasks": float(resources.get("queued_tasks", 0.0)),
        "mean_slice_ns": float(resources.get("mean_slice_ns", 1_000_000.0)),
        "e_core_active": float(hints.get("e_core_active", 0.0)),
        "integration_level": float(hints.get("integration_level", 0.0)),
        "scenario_template_id": record.context.scenario_template_id or record.context.constraint_tier,
        "labels": y_route_labels(record),
        "outcome": {
            "actual_latency": record.outcome.actual_latency,
            "actual_accuracy": record.outcome.actual_accuracy,
            "bandit_success": record.outcome.bandit_success,
            "stage_confidence": record.outcome.stage_confidence,
            "accuracy_is_proxy": True,
        },
    }


def augment_from_nearest(real_rows: list[dict], *, target_budget: float) -> dict | None:
    """Distribution-faithful: interpolate budget only; outcomes copied from nearest real row."""
    if not real_rows:
        return None
    nearest = min(real_rows, key=lambda r: abs(r["latency_budget"] - target_budget))
    aug = json.loads(json.dumps(nearest))
    aug["latency_budget"] = target_budget
    aug["augmented"] = True
    aug["augmentation_source"] = nearest["hardware_profile_id"]
    st = list(aug.get("structured_tensor") or [])
    if len(st) >= 1:
        st[0] = float(target_budget) / 100.0
        aug["structured_tensor"] = (st + [0.0] * 16)[:16]
    if target_budget < 10.0:
        aug["labels"]["activation_sparsity_budget"] = max(
            aug["labels"]["activation_sparsity_budget"], 0.5
        )
        aug["labels"]["max_nodes"] = max(1, int(aug["labels"]["max_nodes"]) // 2)
        aug["labels"]["early_exit_confidence_threshold"] = min(
            float(aug["labels"]["early_exit_confidence_threshold"]), 0.85
        )
    return aug


class DatasetCompiler:
    def __init__(self, traces_dir: Path, output_dir: Path) -> None:
        self.traces_dir = traces_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_traces(self) -> list[SandboxTraceRecord]:
        records: list[SandboxTraceRecord] = []
        for path in sorted(self.traces_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            records.append(from_dict(SandboxTraceRecord, data))
        return records

    def compile(self) -> CompiledDataset:
        records = self.load_traces()
        compiled = CompiledDataset()

        for record in records:
            row = _feature_row(record)
            profile = record.context.hardware_profile_id
            if profile in VAL_PROFILES:
                compiled.val_rows.append(row)
            else:
                compiled.train_rows.append(row)

        for budget in (7.0, 12.0, 15.0, 20.0):
            aug = augment_from_nearest(compiled.train_rows, target_budget=budget)
            if aug:
                compiled.augmented_rows.append(aug)

        train_path = self.output_dir / "train.jsonl"
        val_path = self.output_dir / "val.jsonl"
        aug_path = self.output_dir / "augmented.jsonl"

        def _write_jsonl(path: Path, rows: list[dict]) -> None:
            text = "".join(json.dumps(r) + "\n" for r in rows)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)

        _write_jsonl(train_path, compiled.train_rows + compiled.augmented_rows)
        _write_jsonl(val_path, compiled.val_rows)
        _write_jsonl(aug_path, compiled.augmented_rows)

        return compiled
