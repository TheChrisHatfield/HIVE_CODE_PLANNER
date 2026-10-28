# Project Map

**Hook:** `change.impact`, `next.files`

Manual v1 map of modules → dependencies. Use `impact-sync-maps` to merge new src modules (Stage 5B).

| Module | Role | Spec / Delta deps |
|--------|------|-------------------|
| `docs/delta/*.md` | Primary planning truth | `context.delta` |
| `docs/planning-rosetta-stone.md` | Hook legend | `planning.rosetta` |
| `src/hive_planner/__main__.py` |   main   | (auto-sync) |
| `src/hive_planner/agent_handoff.py` | Unified Spec Kit + Continual Learning deployment profile (symbiotic pair). | (auto-sync) |
| `src/hive_planner/agents_memory.py` | AGENTS.md lint/propose | `agents-memory-ci-v1` |
| `src/hive_planner/bootstrap.py` | bootstrap | (auto-sync) |
| `src/hive_planner/bug_hunt.py` | Chat-triggered find/fix/commit loop install | `docs/specs/bug-hunt` |
| `src/hive_planner/implementation_loop.py` | Post-spec coding loop install and readiness | `docs/specs/implementation-loop` |
| `src/hive_planner/agnostic_loop.py` | hive-loop-kit install + pause-cycle chooser | `docs/specs/agnostic-loop` |
| `src/hive_planner/call_graph.py` | call graph | (auto-sync) |
| `src/hive_planner/cartridge_adapt.py` | Adapt custom-named cartridge imports into promotable Hive layout. | (auto-sync) |
| `src/hive_planner/cartridge_pack.py` | cartridge pack | (auto-sync) |
| `src/hive_planner/cartridge_promote.py` | Promote draft cartridge files into Delta / Spec Kit and stage CL candidates. | (auto-sync) |
| `src/hive_planner/chunker.py` | Chunking | `compiler.pipeline` |
| `src/hive_planner/ci_handoff.py` | ci handoff | (auto-sync) |
| `src/hive_planner/cl_migration.py` | cl migration | (auto-sync) |
| `src/hive_planner/cl_runtime.py` | Continual Learning runtime profiles — Cursor plugin vs IDE-agnostic headless pat | (auto-sync) |
| `src/hive_planner/cli.py` | CLI entry | `docs/specs/*/tasks.md` |
| `src/hive_planner/config.py` | config | (auto-sync) |
| `src/hive_planner/delta_emit.py` | Delta → cartridge sync | `cartridge-delta-emit-v1` |
| `src/hive_planner/discovery.py` | discovery | (auto-sync) |
| `src/hive_planner/embeddings.py` | Hybrid retrieval index | `embedding-retrieval-v1` |
| `src/hive_planner/emitter.py` | Cartridge emit | `context.cartridge` |
| `src/hive_planner/format_deps.py` | Optional format dependencies (PDF, etc.) for ingest and Load Sources. | (auto-sync) |
| `src/hive_planner/frozen_entry.py` | PyInstaller entrypoint — GUI by default; CLI via subcommand or --hive-cli. | (auto-sync) |
| `src/hive_planner/impact.py` | Impact packets | `change-impact-v1` |
| `src/hive_planner/indexer.py` | JSON indexes | `context.metadata` |
| `src/hive_planner/launcher/__main__.py` |   main   | (auto-sync) |
| `src/hive_planner/launcher/agent_prompt_templates.py` | agent prompt templates | (auto-sync) |
| `src/hive_planner/launcher/app.py` | app | (auto-sync) |
| `src/hive_planner/launcher/bootstrap_state.py` | Bootstrap detection for linked Cursor workspaces. | (auto-sync) |
| `src/hive_planner/launcher/config.py` | config | (auto-sync) |
| `src/hive_planner/launcher/console_win.py` | console win | (auto-sync) |
| `src/hive_planner/launcher/mcp_servers.py` | Cursor `.cursor/mcp.json` hive-planner enable. | `workflow.tools` |
| `src/hive_planner/launcher/popup_placement.py` | Dialog windows reopen at their last screen position. | `workflow.tools` |
| `src/hive_planner/launcher/service.py` | service | (auto-sync) |
| `src/hive_planner/launcher/theme.py` | theme | (auto-sync) |
| `src/hive_planner/launcher/user_guide.py` | user guide | (auto-sync) |
| `src/hive_planner/map_sync.py` | map sync | (auto-sync) |
| `src/hive_planner/mcp_server.py` | Stdio MCP so a Cursor agent can call Hive Planner. | `workflow.tools` |
| `src/hive_planner/memory_routing.py` | Autonomous memory candidate routing — split, route, Thompson-sample arms. | (auto-sync) |
| `src/hive_planner/models.py` | models | (auto-sync) |
| `src/hive_planner/normalizer.py` | Format dispatch | `context.document_sourcing` |
| `src/hive_planner/normalizers/csv.py` | csv | (auto-sync) |
| `src/hive_planner/normalizers/docx.py` | DOCX normalize | `cartridge-compiler-v2` |
| `src/hive_planner/normalizers/html.py` | html | (auto-sync) |
| `src/hive_planner/normalizers/pdf.py` | PDF normalize | `cartridge-compiler-v2` |
| `src/hive_planner/normalizers/pptx.py` | pptx | (auto-sync) |
| `src/hive_planner/normalizers/text.py` | text | (auto-sync) |
| `src/hive_planner/ocr_runtime.py` | Portable Tesseract OCR runtime for image-only PDF sources. | (auto-sync) |
| `src/hive_planner/pipeline.py` | Ingest orchestration | `cartridge-compiler-v2` |
| `src/hive_planner/portable_runtime.py` | Portable / frozen runtime — self-contained Spec Kit + Continual Learning deploy. | (auto-sync) |
| `src/hive_planner/project_profile.py` | project profile | (auto-sync) |
| `src/hive_planner/roadmap_status.py` | roadmap status | (auto-sync) |
| `src/hive_planner/rosetta_eject.py` | Export Rosetta Stone planning session contract for external AI tools (Gemini, Pe | (auto-sync) |
| `src/hive_planner/rosetta_nav.py` | Rosetta Stone navigation blocks for agent handoff artifacts. | (auto-sync) |
| `src/hive_planner/runtime_paths.py` | Frozen / portable path resolution for standalone Hive Planner builds. | (auto-sync) |
| `src/hive_planner/source4s.py` | Source4s — upload txt/pdf reference files for cartridge-linked agent retrieval. | (auto-sync) |
| `src/hive_planner/spec_drift.py` | spec drift | (auto-sync) |
| `src/hive_planner/translator.py` | Rule-based cartridge drafts | `cartridge-translator-v1` |
| `src/hive_planner/vendor_sync.py` | Vendor manifest and unified upstream pin verification (Stage 9). | (auto-sync) |
| `src/hive_planner/wiring_audit.py` | Machine-enforceable Integration wiring audit attestation (CL pre-flight gate). | (auto-sync) |
