from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hive_planner.agents_memory import AgentsMemoryError, ingest_agents_candidates, lint_agents_md, run_agents_memory
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths, resolve_repo_file_path, is_repo_root, resolve_root
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
    emit_parser.add_argument(
        "--emit-rules-seeds",
        action="store_true",
        help="Write cartridge/rules/<feature>.mdc.seed from Delta macro/micro (never writes .cursor/rules/)",
    )
    emit_parser.add_argument(
        "--promote",
        action="store_true",
        help="After emit, run cartridge promote + spec-drift (spec-drift/handoff when no drafts to merge)",
    )
    emit_parser.add_argument(
        "--mark-draft",
        action="store_true",
        help="Prepend draft banners on emitted cartridge layers (use before --promote for Sources emit)",
    )
    emit_parser.add_argument(
        "--force-promote",
        action="store_true",
        help="With --promote, overwrite existing non-bootstrap Delta/spec targets",
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
    impact_parser.add_argument(
        "--mode",
        choices=["default", "bugfix"],
        default="default",
        help="Impact analysis mode (bugfix widens call-graph targets and sets medium risk)",
    )
    impact_parser.add_argument(
        "--deep",
        action="store_true",
        help="Include import/call-graph secondary targets (also enabled by --mode bugfix)",
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

    vendor_sync = sub.add_parser(
        "vendor-sync",
        help="Check or apply unified upstream vendor pins (Stage 9)",
    )
    vendor_sync.add_argument(
        "--check",
        action="store_true",
        help="Validate vendor/manifest.json schema and report pin status (default)",
    )
    vendor_sync.add_argument(
        "--apply",
        action="store_true",
        help="Import pinned upstream trees from vendor/manifest.json",
    )

    sub.add_parser(
        "unified-verify",
        help="Verify vendor manifest and project .hive/upstream-pins.json (Stage 9)",
    )

    sub.add_parser("roadmap-status", help="Validate Stage roadmap artifacts (hook: workflow.tools)")

    init_parser = sub.add_parser(
        "init",
        help="Bootstrap a new Hive project profile (hook: workflow.project_bootstrap)",
    )
    init_parser.add_argument("--target", required=True, type=Path, help="Directory for the new project root")
    init_parser.add_argument("--name", default=None, help="Project display name (default: target folder name)")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Scaffold into a non-empty or partially initialized directory",
    )
    init_parser.add_argument(
        "--profile",
        default="minimal",
        choices=("minimal", "full"),
        help="Bootstrap profile: minimal (v1) or full starter-kit v2 (pyproject, CI stub, src/tests)",
    )
    init_parser.add_argument(
        "--git-init",
        action="store_true",
        help="Run git init in the target after scaffolding (optional; requires git on PATH)",
    )
    init_parser.add_argument(
        "--agent-handoff",
        default="unified",
        choices=("off", "unified"),
        help="Agent handoff profile: unified deploys Spec Kit + Continual Learning together; off = planning only",
    )
    init_parser.add_argument(
        "--spec-kit",
        action="store_true",
        help="Deprecated alias for --agent-handoff unified",
    )
    init_parser.add_argument(
        "--continual-learning",
        action="store_true",
        help="Deprecated; unified mode always enables both Spec Kit and Continual Learning",
    )
    init_parser.add_argument(
        "--cl-runtime",
        default="cursor",
        choices=("cursor", "headless", "external"),
        help="Continual Learning runtime: cursor (plugin) or headless/external (CLI-only memory loop)",
    )

    cl_runtime_parser = sub.add_parser(
        "cl-runtime",
        help="Show or set Continual Learning runtime (Cursor plugin vs IDE-agnostic headless)",
    )
    cl_runtime_sub = cl_runtime_parser.add_subparsers(dest="cl_runtime_command", required=True)
    cl_runtime_show = cl_runtime_sub.add_parser("show", help="Show resolved CL runtime for this project")
    cl_runtime_set = cl_runtime_sub.add_parser("set", help="Set CL runtime in .hive/project.json")
    cl_runtime_set.add_argument(
        "runtime",
        choices=("cursor", "headless", "external"),
        help="cursor = Hive vendored Cursor plugin; headless/external = CLI agents-propose path",
    )

    translate_parser = sub.add_parser("translate", help="Rule-based cartridge draft translation")
    translate_parser.add_argument("--input", required=True, type=Path, help="Research markdown input file")
    translate_parser.add_argument("--feature", required=True, help="Feature name for micro/spec outputs")
    translate_parser.add_argument(
        "--no-promote",
        action="store_true",
        help="Skip promoting drafts to Delta/Spec Kit and spec-drift check",
    )
    translate_parser.add_argument(
        "--force-promote",
        action="store_true",
        help="Overwrite existing Delta/spec targets when promoting cartridge drafts",
    )

    promote_parser = sub.add_parser(
        "cartridge-promote",
        help="Promote draft cartridge files to Delta/Spec Kit and run spec-drift (hook: integration.cl_spec)",
    )
    promote_parser.add_argument("--feature", required=True, help="Feature name")
    promote_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing non-bootstrap Delta/spec targets",
    )
    promote_parser.add_argument(
        "--skip-spec-drift",
        action="store_true",
        help="Promote only — do not run spec-drift-check",
    )

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
    agents_propose.add_argument(
        "--skip-wiring-audit",
        action="store_true",
        help="Skip Integration wiring audit gate (unified handoff only)",
    )

    agents_apply = sub.add_parser(
        "agents-apply",
        help="Apply validated operational candidates to AGENTS.md (hook: automation.ci_memory)",
    )
    agents_apply.add_argument("--candidates", required=True, type=Path, help="Candidate bullets file")
    agents_apply.add_argument("--path", type=Path, default=None, help="AGENTS.md path (default: repo root)")
    agents_apply.add_argument(
        "--skip-wiring-audit",
        action="store_true",
        help="Skip Integration wiring audit gate (unified handoff only)",
    )

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

    wiring_audit = sub.add_parser(
        "wiring-audit",
        help="Record or verify Integration wiring audit attestation (hook: integration.wiring_audit)",
    )
    wiring_audit_sub = wiring_audit.add_subparsers(dest="wiring_audit_command", required=True)
    wiring_record = wiring_audit_sub.add_parser("record", help="Record wiring audit attestation after validation")
    wiring_record.add_argument("--feature", default=None, help="Feature id (default: active from AGENTS.md)")
    wiring_record.add_argument(
        "--evidence",
        required=True,
        help="Integration-level validation command or result (required)",
    )
    wiring_record.add_argument("--summary", default="", help="Optional short audit summary")
    wiring_check = wiring_audit_sub.add_parser("check", help="Verify wiring audit attestation is current")
    wiring_check.add_argument("--feature", default=None, help="Feature id (default: active from AGENTS.md)")

    cl_migrate = sub.add_parser(
        "cl-migrate",
        help="Migrate marketplace Continual Learning data to Hive vendored CL",
    )
    cl_migrate.add_argument(
        "--remove-marketplace-plugin",
        action="store_true",
        help="Remove .cursor/plugins/continual-learning/ from the project after migration",
    )
    cl_migrate.add_argument("--dry-run", action="store_true", help="Report actions without writing files")

    args = parser.parse_args(argv)
    root, auto_detected = resolve_root(args.root)
    paths = RepoPaths(root=root)

    if args.root is None and not auto_detected and not is_repo_root(root):
        print(
            "Warning: could not auto-detect repo root (missing START_HERE.md). "
            "Use --root or run from the Hive Code Planner directory.",
            file=sys.stderr,
        )

    if args.command == "init":
        from hive_planner.bootstrap import BootstrapError, init_project

        try:
            agent_handoff = args.agent_handoff
            if args.spec_kit and agent_handoff == "off":
                agent_handoff = "unified"
            result = init_project(
                paths,
                args.target,
                name=args.name,
                force=args.force,
                profile=args.profile,
                git_init=args.git_init,
                agent_handoff=agent_handoff,
                cl_runtime=args.cl_runtime,
            )
        except BootstrapError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Hive source: {root}")
        print(f"Bootstrapped: {result.target}")
        print(f"Project: {result.project_name}")
        for warning in result.warnings:
            print(f"Warning: {warning}")
        from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, resolve_agent_handoff_mode, validate_unified_handoff

        payload = result.to_dict()
        mode = resolve_agent_handoff_mode(result.target)
        handoff_ok = True
        if mode == AGENT_HANDOFF_UNIFIED:
            handoff = validate_unified_handoff(result.target)
            handoff_ok = handoff.complete
            payload["handoff_ok"] = handoff_ok
            if not handoff_ok:
                payload["handoff_missing"] = handoff.missing
                print(
                    f"Error: Unified handoff incomplete — missing: {', '.join(handoff.missing)}",
                    file=sys.stderr,
                )
        print(json.dumps(payload, indent=2))
        return 0 if handoff_ok else 1

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
        try:
            outputs, warnings = emit_cartridge(
                paths,
                args.feature,
                force_delta=args.force_delta,
                emit_rules_seeds=args.emit_rules_seeds,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        for warning in warnings:
            print(f"Warning: {warning}")
        for warning in impact_warnings(paths, args.feature):
            print(f"Warning: {warning}")
        for name, path in outputs.items():
            print(f"Wrote {name}: {path.relative_to(root)}")
        payload = {"outputs": {name: str(path.relative_to(root)) for name, path in outputs.items()}}
        if args.mark_draft:
            from hive_planner.cartridge_promote import mark_cartridge_layers_draft

            payload["mark_draft"] = mark_cartridge_layers_draft(
                paths,
                args.feature,
                only_paths=outputs.values(),
            )
            for layer, status in sorted(payload["mark_draft"].items()):
                print(f"Mark draft {layer}: {status}")
        if args.promote:
            from hive_planner.cartridge_promote import promote_cartridge_drafts

            promote = promote_cartridge_drafts(
                paths,
                args.feature,
                force=args.force_promote,
            )
            payload["promote"] = promote.to_dict()
            if promote.candidates_path:
                print(f"Wrote CL candidates: {promote.candidates_path}")
            print(f"Promotion spec-drift ok: {promote.ok}")
            if not promote.ok:
                from hive_planner.cartridge_promote import HANDOFF_INCOMPLETE_MSG

                print(HANDOFF_INCOMPLETE_MSG, file=sys.stderr)
            print(json.dumps(payload, indent=2))
            from hive_planner.cartridge_promote import promote_cli_exit_code

            return promote_cli_exit_code(promote)
        if args.mark_draft:
            print(json.dumps(payload, indent=2))
        return 0

    if args.command == "status":
        summary = status_summary(paths)
        print(f"Root: {root}")
        print(json.dumps(summary, indent=2))
        return 0

    if args.command == "impact":
        try:
            file_paths = [resolve_repo_file_path(paths, Path(f)) for f in args.files]
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        try:
            packet = build_impact_packet(
                paths,
                args.feature,
                file_paths,
                mode=args.mode,
                deep=args.deep,
            )
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
            check_roadmap=None,
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
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except TranslatorError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        for rel in result.files_written:
            print(f"Wrote draft: cartridge/{rel}")
        print(f"Wrote status: {status_path.relative_to(root)}")
        payload = result.to_dict()
        if not getattr(args, "no_promote", False):
            from hive_planner.cartridge_promote import promote_cartridge_drafts

            promote = promote_cartridge_drafts(
                paths,
                args.feature,
                force=args.force_promote,
            )
            payload["promote"] = promote.to_dict()
            if promote.candidates_path:
                print(f"Wrote CL candidates: {promote.candidates_path}")
            print(f"Promotion spec-drift ok: {promote.ok}")
            if not promote.ok:
                from hive_planner.cartridge_promote import HANDOFF_INCOMPLETE_MSG

                print(HANDOFF_INCOMPLETE_MSG, file=sys.stderr)
        print(json.dumps(payload, indent=2))
        from hive_planner.cartridge_promote import promote_cli_exit_code

        return promote_cli_exit_code(payload.get("promote"))

    if args.command == "cartridge-promote":
        from hive_planner.cartridge_promote import promote_cartridge_drafts

        try:
            result = promote_cartridge_drafts(
                paths,
                args.feature,
                force=args.force,
                run_spec_drift=not args.skip_spec_drift,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        if result.candidates_path:
            print(f"Wrote CL candidates: {result.candidates_path}")
        for warning in result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        if not result.ok:
            from hive_planner.cartridge_promote import HANDOFF_INCOMPLETE_MSG

            print(HANDOFF_INCOMPLETE_MSG, file=sys.stderr)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.ok else 1

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
                skip_wiring_audit=args.skip_wiring_audit,
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
                skip_wiring_audit=args.skip_wiring_audit,
            )
        except AgentsMemoryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(f"Wrote proposal: {result.proposal_path.relative_to(root)}")
        print("Applied accepted bullets to AGENTS.md (guarded v2 apply)")
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "cl-runtime":
        from hive_planner.cl_runtime import resolve_cl_runtime, set_project_cl_runtime

        if args.cl_runtime_command == "show":
            runtime = resolve_cl_runtime(root)
            print(f"Root: {root}")
            print(f"cl_runtime: {runtime}")
            return 0
        try:
            set_project_cl_runtime(root, args.runtime)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(f"Set cl_runtime={args.runtime}")
        print("Re-run Deploy agent handoff (launcher or bootstrap) to refresh CL artifacts.")
        return 0

    if args.command == "cl-migrate":
        from hive_planner.cl_migration import ClMigrationError, migrate_marketplace_cl

        try:
            report = migrate_marketplace_cl(
                paths,
                remove_marketplace_plugin=args.remove_marketplace_plugin,
                dry_run=args.dry_run,
            )
        except ClMigrationError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

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

    if args.command == "wiring-audit":
        from hive_planner.wiring_audit import WiringAuditError, check_wiring_audit, record_wiring_audit

        if args.wiring_audit_command == "record":
            try:
                out_path = record_wiring_audit(
                    paths,
                    feature=args.feature,
                    evidence=args.evidence,
                    summary=args.summary,
                )
            except WiringAuditError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            print(f"Root: {root}")
            print(f"Recorded wiring audit: {out_path.relative_to(root)}")
            return 0

        report = check_wiring_audit(paths, feature=args.feature)
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

    if args.command == "vendor-sync":
        from hive_planner.vendor_sync import VendorSyncError, vendor_sync_apply, vendor_sync_check

        try:
            if args.apply:
                report = vendor_sync_apply(root)
            else:
                report = vendor_sync_check(root)
        except VendorSyncError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

    if args.command == "unified-verify":
        from hive_planner.vendor_sync import VendorSyncError, unified_verify

        try:
            report = unified_verify(paths)
        except VendorSyncError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Root: {root}")
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

    return 1
