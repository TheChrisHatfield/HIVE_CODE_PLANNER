from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hive_planner.agents_memory import AgentsMemoryError, ingest_agents_candidates, lint_agents_md, run_agents_memory
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths, is_repo_root, resolve_root
from hive_planner.roadmap_status import validate_roadmap
from hive_planner.spec_drift import check_memory_spec_drift
from hive_planner.emitter import emit_cartridge
from hive_planner.impact import ImpactError, build_impact_packet, impact_warnings, write_impact_packet
from hive_planner.map_sync import sync_impact_maps
from hive_planner.pipeline import ingest, status_summary
from hive_planner.translator import TranslatorError, translate_document, write_translator_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hive-planner",
        description="Hive Code Planner cartridge compiler (hook: compiler.pipeline)",
    )
    parser.add_argument("--root", type=Path, default=None, help="Repo root (auto-detected if omitted)")

    sub = parser.add_subparsers(dest="command", required=True)

    ingest_parser = sub.add_parser("ingest", help="Discover, normalize, chunk, and index sources")
    ingest_parser.add_argument(
        "--embed",
        action="store_true",
        help="Build/update embedding index for hybrid retrieval on emit",
    )
    emit_parser = sub.add_parser("emit", help="Emit cartridge manifest and source-context.md")
    emit_parser.add_argument("--feature", required=True, help="Active feature name for retrieval")
    emit_parser.add_argument(
        "--force-delta",
        action="store_true",
        help="Overwrite cartridge holistic/macro/micro even when draft or manual banners exist",
    )
    sub.add_parser("status", help="Show ingest/index/cartridge status")

    impact_parser = sub.add_parser("impact", help="Generate change-impact packet (hook: change.impact)")
    impact_parser.add_argument("--feature", required=True, help="Active feature name")
    impact_parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Repo-relative or absolute paths targeted for edit",
    )

    sync_maps = sub.add_parser(
        "impact-sync-maps",
        help="Merge src/test discovery into change-impact maps (hook: change.impact)",
    )
    sync_maps.add_argument(
        "--dry-run",
        action="store_true",
        help="Report map changes without writing files",
    )

    ci_check = sub.add_parser(
        "ci-check",
        help="Run handoff validation suite (hook: workflow.git_handoff)",
    )
    ci_check.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip pytest step (useful when already running under pytest)",
    )
    ci_check.add_argument(
        "--allow-map-drift",
        action="store_true",
        help="Do not fail when impact maps are out of sync",
    )

    sub.add_parser("roadmap-status", help="Validate Stage roadmap artifacts (hook: workflow.tools)")

    translate_parser = sub.add_parser("translate", help="Rule-based cartridge draft translation")
    translate_parser.add_argument("--input", required=True, type=Path, help="Research markdown input file")
    translate_parser.add_argument("--feature", required=True, help="Feature name for micro/spec outputs")

    agents_lint = sub.add_parser("agents-lint", help="Lint AGENTS.md structure and bullets")
    agents_lint.add_argument("--path", type=Path, default=None, help="AGENTS.md path (default: repo root)")

    agents_propose = sub.add_parser("agents-propose", help="Propose AGENTS.md memory updates")
    agents_propose.add_argument("--candidates", required=True, type=Path, help="Candidate bullets file")
    agents_propose.add_argument("--path", type=Path, default=None, help="AGENTS.md path (default: repo root)")
    agents_propose.add_argument(
        "--apply",
        action="store_true",
        help="Guarded v2 apply — merge operational candidates into Durable Workspace Facts only",
    )

    agents_apply = sub.add_parser(
        "agents-apply",
        help="Apply validated operational candidates to AGENTS.md (hook: automation.ci_memory)",
    )
    agents_apply.add_argument("--candidates", required=True, type=Path, help="Candidate bullets file")
    agents_apply.add_argument("--path", type=Path, default=None, help="AGENTS.md path (default: repo root)")

    agents_ingest = sub.add_parser(
        "agents-ingest",
        help="Normalize Continual Learning / transcript export into candidates file",
    )
    agents_ingest.add_argument("--from", dest="source", required=True, type=Path, help="Source export file")
    agents_ingest.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path (default: docs/proposals/candidates-normalized-<timestamp>.md)",
    )

    spec_drift = sub.add_parser(
        "spec-drift-check",
        help="Check Spec Kit handoff and memory/spec alignment (hook: integration.cl_spec)",
    )
    spec_drift.add_argument("--feature", default=None, help="Feature name (default: active from AGENTS.md)")
    spec_drift.add_argument(
        "--candidates",
        type=Path,
        default=None,
        help="Optional candidate bullets file to classify",
    )
    spec_drift.add_argument(
        "--skip-agents-facts",
        action="store_true",
        help="Do not scan existing Durable Workspace Facts in AGENTS.md",
    )

    args = parser.parse_args(argv)
    root, auto_detected = resolve_root(args.root)
    paths = RepoPaths(root=root)

    if args.root is None and not auto_detected and not is_repo_root(root):
        print(
            "Warning: could not auto-detect repo root (missing START_HERE.md). "
            "Use --root or run from the Hive Code Planner directory.",
            file=sys.stderr,
        )

    if args.command == "ingest":
        report = ingest(paths, embed=args.embed)
        print(f"Root: {root}")
        print(f"Processed: {report.processed}, skipped: {report.skipped}, pruned: {report.pruned}")
        for warning in report.warnings:
            print(f"Warning: {warning}")
        for warning in impact_warnings(paths):
            print(f"Warning: {warning}")
        summary = status_summary(paths)
        print(json.dumps(summary, indent=2))
        return 0

    if args.command == "emit":
        outputs, warnings = emit_cartridge(paths, args.feature, force_delta=args.force_delta)
        print(f"Root: {root}")
        for warning in warnings:
            print(f"Warning: {warning}")
        for warning in impact_warnings(paths, args.feature):
            print(f"Warning: {warning}")
        for name, path in outputs.items():
            print(f"Wrote {name}: {path.relative_to(root)}")
        return 0

    if args.command == "status":
        summary = status_summary(paths)
        print(f"Root: {root}")
        print(json.dumps(summary, indent=2))
        return 0

    if args.command == "impact":
        file_paths = [Path(f) for f in args.files]
        try:
            packet = build_impact_packet(paths, args.feature, file_paths)
            out_path = write_impact_packet(paths, packet)
        except ImpactError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(f"Wrote impact packet: {out_path.relative_to(root)}")
        print(f"Risk: {packet.risk_score}")
        print(json.dumps(packet.to_dict(), indent=2))
        return 0

    if args.command == "impact-sync-maps":
        report = sync_impact_maps(paths, dry_run=args.dry_run)
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    if args.command == "ci-check":
        report = run_ci_check(
            paths,
            skip_pytest=args.skip_pytest,
            check_map_drift=not args.allow_map_drift,
        )
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        for step in report.steps:
            status = "ok" if step.ok else "FAIL"
            print(f"{status}: {step.name} — {step.detail}")
        return 0 if report.ok else 1

    if args.command == "roadmap-status":
        report = validate_roadmap(paths)
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        if report.missing:
            print("Missing:", ", ".join(report.missing))
        return 0 if report.ok else 1

    if args.command == "translate":
        try:
            result = translate_document(paths, args.input, args.feature)
            status_path = write_translator_status(paths, result)
        except TranslatorError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        for rel in result.files_written:
            print(f"Wrote draft: cartridge/{rel}")
        print(f"Wrote status: {status_path.relative_to(root)}")
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "agents-lint":
        try:
            report = lint_agents_md(paths, args.path)
        except AgentsMemoryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

    if args.command == "agents-propose":
        try:
            result = run_agents_memory(
                paths,
                args.candidates,
                agents_path=args.path,
                apply=args.apply,
            )
        except AgentsMemoryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(f"Wrote proposal: {result.proposal_path.relative_to(root)}")
        if result.applied:
            print("Applied accepted bullets to AGENTS.md (guarded v2 apply)")
        else:
            print("AGENTS.md unchanged (proposal-only workflow)")
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "agents-apply":
        try:
            result = run_agents_memory(
                paths,
                args.candidates,
                agents_path=args.path,
                apply=True,
            )
        except AgentsMemoryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(f"Wrote proposal: {result.proposal_path.relative_to(root)}")
        print("Applied accepted bullets to AGENTS.md (guarded v2 apply)")
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "agents-ingest":
        try:
            out_path = ingest_agents_candidates(paths, args.source, output_path=args.out)
        except AgentsMemoryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(f"Wrote normalized candidates: {out_path.relative_to(root)}")
        return 0

    if args.command == "spec-drift-check":
        report = check_memory_spec_drift(
            paths,
            feature=args.feature,
            candidates_path=args.candidates,
            include_agents_facts=not args.skip_agents_facts,
        )
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        if report.drift_items:
            print("Drift items:", file=sys.stderr)
            for item in report.drift_items:
                print(f"  - {item}", file=sys.stderr)
        if report.spec_actions:
            print("Spec actions:", file=sys.stderr)
            for action in report.spec_actions:
                print(f"  - {action}", file=sys.stderr)
        return 0 if report.ok else 1

    return 1
