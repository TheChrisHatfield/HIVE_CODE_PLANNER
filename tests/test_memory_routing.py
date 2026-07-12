from __future__ import annotations

import random
from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.memory_routing import (
    ARM_OPERATIONALIZE,
    ARM_REJECT,
    ARM_ROUTE_SPEC,
    ARM_SPLIT,
    RoutingStats,
    load_routing_stats,
    route_ambiguous_candidate,
    route_behavioral_candidate,
    route_oversized_operational,
    save_routing_stats,
    split_long_bullet,
)


def test_split_long_bullet_keeps_short_bullet() -> None:
    bullet = "Keep pytest green. # operational"
    assert split_long_bullet(bullet, max_chars=240) == [bullet]


def test_split_long_bullet_preserves_tag_and_fits_limit() -> None:
    body = (
        "Portable HivePlanner.exe lives under dist/HivePlannerPortable. "
        "Rebuild with scripts/build_portable.ps1 after UI changes. "
        "Smoke-test ocr-status and status before shipping. "
        "Close the running exe first so Windows does not lock the binary."
    )
    bullet = f"{body} # operational"
    assert len(bullet) > 240
    pieces = split_long_bullet(bullet, max_chars=240)
    assert len(pieces) >= 2
    assert all(len(p) <= 240 for p in pieces)
    assert all(p.endswith("# operational") for p in pieces)
    joined = " ".join(p.replace(" # operational", "") for p in pieces)
    assert "HivePlanner.exe" in joined
    assert "build_portable" in joined


def test_route_oversized_operational_splits_without_recording_stats() -> None:
    stats = RoutingStats()
    long = ("A" * 100 + ". " + "B" * 100 + ". " + "C" * 80 + " # operational")
    decision = route_oversized_operational(long, max_chars=240, stats=stats)
    assert decision.arm == ARM_SPLIT
    assert len(decision.remediations) >= 2
    assert stats.arm(ARM_SPLIT).successes == 1.0


def test_route_oversized_unsplittable_rejects(monkeypatch) -> None:
    stats = RoutingStats()
    monkeypatch.setattr(
        "hive_planner.memory_routing.split_long_bullet",
        lambda *_a, **_k: [],
    )
    decision = route_oversized_operational("X" * 300 + " # operational", max_chars=240, stats=stats)
    assert decision.arm == ARM_REJECT
    assert not decision.remediations
    assert stats.arm(ARM_SPLIT).failures > 1.0
    assert "auto-split" in decision.reason.lower()


def test_thompson_pick_is_deterministic_with_seed() -> None:
    stats = RoutingStats()
    stats.arm(ARM_OPERATIONALIZE).successes = 20
    stats.arm(ARM_ROUTE_SPEC).successes = 1
    stats.arm(ARM_REJECT).successes = 1
    picked = {stats.thompson_pick([ARM_OPERATIONALIZE, ARM_ROUTE_SPEC, ARM_REJECT], rng=random.Random(0)) for _ in range(5)}
    assert ARM_OPERATIONALIZE in picked


def test_route_ambiguous_operationalize(tmp_path: Path) -> None:
    stats = RoutingStats()
    stats.arm(ARM_OPERATIONALIZE).successes = 50
    stats.arm(ARM_ROUTE_SPEC).failures = 20
    stats.arm(ARM_REJECT).failures = 20
    decision = route_ambiguous_candidate(
        "Mixed tooling and API wording.",
        feature="feature-x",
        stats=stats,
        rng=random.Random(1),
    )
    assert decision.arm in {ARM_OPERATIONALIZE, ARM_ROUTE_SPEC, ARM_REJECT}
    if decision.arm == ARM_OPERATIONALIZE:
        assert decision.remediations[0].endswith("# operational")


def test_route_behavioral_writes_file(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    decision = route_behavioral_candidate(
        "API must return 404 when disabled.",
        paths=paths,
        feature="feature-x",
    )
    assert decision.arm == ARM_ROUTE_SPEC
    out = tmp_path / "docs" / "proposals" / "cl-candidates.md"
    assert out.is_file()
    assert "API must return 404" in out.read_text(encoding="utf-8")


def test_append_behavioral_dedupes_exact_bullet_line_not_substring(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    out = paths.root / "docs" / "proposals" / "cl-candidates.md"
    out.parent.mkdir(parents=True)
    out.write_text(
        "\n".join(
            [
                "# Continual Learning candidates (auto-routed)",
                "",
                "- See API documentation for details.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    route_behavioral_candidate("API must return 404 when disabled.", paths=paths, feature="feature-x")
    text = out.read_text(encoding="utf-8")
    assert "API must return 404 when disabled." in text
    assert text.count("- See API documentation") == 1


def test_append_behavioral_dedupes_tag_variants(tmp_path: Path) -> None:
    from hive_planner.memory_routing import _append_behavioral_candidate

    paths = RepoPaths(root=tmp_path)
    out = paths.root / "docs" / "proposals" / "cl-candidates.md"
    out.parent.mkdir(parents=True)
    out.write_text(
        "\n".join(
            [
                "# Continual Learning candidates (auto-routed)",
                "",
                "- API must return 404 when disabled. # behavioral",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _, wrote = _append_behavioral_candidate(paths, "feature-x", "API must return 404 when disabled.")
    assert wrote is False
    assert out.read_text(encoding="utf-8").count("API must return 404") == 1


def test_route_behavioral_skips_stats_success_when_duplicate(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    bullet = "API must return 404 when disabled. # behavioral"
    route_behavioral_candidate(bullet, paths=paths, feature="feature-x")
    stats = RoutingStats()
    stats.arm(ARM_ROUTE_SPEC).successes = 5.0
    decision = route_behavioral_candidate(bullet, paths=paths, feature="feature-x", stats=stats)
    assert "already present" in decision.reason
    assert stats.arm(ARM_ROUTE_SPEC).successes == 5.0


def test_routing_stats_roundtrip(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    stats = RoutingStats()
    stats.record(ARM_SPLIT, success=True)
    save_routing_stats(paths, stats)
    loaded = load_routing_stats(paths)
    assert loaded.arm(ARM_SPLIT).successes >= 2.0
