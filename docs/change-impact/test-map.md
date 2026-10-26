# Test Map

**Hook:** `change.impact`, `next.files`

Maps source modules to tests (v1 manual + Stage 5B import merge via `impact-sync-maps`).

| Source module | Tests |
|---------------|-------|
| `src/hive_planner/agent_handoff.py` | `tests/test_agent_handoff.py`, `tests/test_agents_memory.py`, `tests/test_bootstrap.py`, `tests/test_cl_migration.py`, `tests/test_cl_runtime.py`, `tests/test_spec_drift.py`, `tests/test_unified_handoff.py`, `tests/test_wiring_audit.py` |
| `src/hive_planner/agents_memory.py` | `tests/test_agents_memory.py`, `tests/test_cl_migration.py`, `tests/test_security_validation.py`, `tests/test_spec_drift.py`, `tests/test_wiring_audit.py` |
| `src/hive_planner/bootstrap.py` | `tests/test_agent_handoff.py`, `tests/test_bootstrap.py`, `tests/test_cl_runtime.py`, `tests/test_security_validation.py`, `tests/test_unified_handoff.py` |
| `src/hive_planner/bug_hunt.py` | `tests/test_bug_hunt.py`, `tests/test_bootstrap.py` |
| `src/hive_planner/implementation_loop.py` | `tests/test_implementation_loop.py`, `tests/test_implementation_loop_coordinator.py` |
| `src/hive_planner/call_graph.py` | `tests/test_impact.py`, `tests/test_security_validation.py` |
| `src/hive_planner/cartridge_adapt.py` | `tests/test_cartridge_adapt.py` |
| `src/hive_planner/cartridge_pack.py` | `tests/test_cartridge_pack.py` |
| `src/hive_planner/cartridge_promote.py` | `tests/test_cartridge_promote.py`, `tests/test_cli_handoff.py` |
| `src/hive_planner/chunker.py` | `tests/test_compiler.py`, `tests/test_formats.py`, `tests/test_formats_v3.py` |
| `src/hive_planner/ci_handoff.py` | `tests/test_ci_handoff.py`, `tests/test_security_validation.py`, `tests/test_spec_drift.py`, `tests/test_unified_handoff.py`, `tests/test_wiring_audit.py` |
| `src/hive_planner/cl_migration.py` | `tests/test_cl_migration.py`, `tests/test_cl_runtime.py` |
| `src/hive_planner/cl_runtime.py` | `tests/test_agent_handoff.py`, `tests/test_cl_migration.py`, `tests/test_cl_runtime.py`, `tests/test_unified_handoff.py` |
| `src/hive_planner/cli.py` | `tests/test_agents_memory.py`, `tests/test_bootstrap.py`, `tests/test_cartridge_promote.py`, `tests/test_cli_handoff.py`, `tests/test_delta_emit.py`, `tests/test_embeddings.py`, `tests/test_format_deps.py`, `tests/test_impact.py`, `tests/test_ocr_runtime.py`, `tests/test_rosetta_eject.py`, `tests/test_source4s.py`, `tests/test_translator.py` |
| `src/hive_planner/config.py` | `tests/test_agent_handoff.py`, `tests/test_agents_memory.py`, `tests/test_bootstrap.py`, `tests/test_cartridge_adapt.py`, `tests/test_cartridge_pack.py`, `tests/test_cartridge_promote.py`, `tests/test_ci_handoff.py`, `tests/test_cl_migration.py`, `tests/test_cl_runtime.py`, `tests/test_cli_handoff.py`, `tests/test_compiler.py`, `tests/test_delta_emit.py`, `tests/test_embeddings.py`, `tests/test_format_deps.py`, `tests/test_formats.py`, `tests/test_formats_v3.py`, `tests/test_impact.py`, `tests/test_map_sync.py`, `tests/test_memory_routing.py`, `tests/test_ocr_runtime.py`, `tests/test_roadmap_status.py`, `tests/test_rosetta_nav.py`, `tests/test_security_validation.py`, `tests/test_source4s.py`, `tests/test_spec_drift.py`, `tests/test_translator.py`, `tests/test_unified_handoff.py`, `tests/test_wiring_audit.py` |
| `src/hive_planner/delta_emit.py` | `tests/test_cartridge_pack.py`, `tests/test_cartridge_promote.py`, `tests/test_delta_emit.py` |
| `src/hive_planner/discovery.py` | `tests/test_compiler.py`, `tests/test_embeddings.py`, `tests/test_formats.py`, `tests/test_source4s.py` |
| `src/hive_planner/embeddings.py` | `tests/test_delta_emit.py`, `tests/test_embeddings.py` |
| `src/hive_planner/emitter.py` | `tests/test_cartridge_pack.py`, `tests/test_compiler.py`, `tests/test_delta_emit.py`, `tests/test_embeddings.py`, `tests/test_formats.py` |
| `src/hive_planner/format_deps.py` | `tests/test_format_deps.py` |
| `src/hive_planner/frozen_entry.py` | `tests/test_runtime_paths.py` |
| `src/hive_planner/impact.py` | `tests/test_impact.py`, `tests/test_security_validation.py` |
| `src/hive_planner/indexer.py` | `tests/test_compiler.py`, `tests/test_embeddings.py`, `tests/test_formats.py`, `tests/test_formats_v3.py` |
| `src/hive_planner/launcher/app.py` | `tests/test_runtime_paths.py` |
| `src/hive_planner/launcher/config.py` | `tests/test_runtime_paths.py` |
| `src/hive_planner/launcher/service.py` | `tests/test_cartridge_adapt.py`, `tests/test_cl_migration.py`, `tests/test_portable_runtime.py`, `tests/test_runtime_paths.py` |
| `src/hive_planner/map_sync.py` | `tests/test_ci_handoff.py`, `tests/test_map_sync.py`, `tests/test_security_validation.py` |
| `src/hive_planner/memory_routing.py` | `tests/test_agents_memory.py`, `tests/test_memory_routing.py` |
| `src/hive_planner/models.py` | `tests/test_compiler.py`, `tests/test_delta_emit.py`, `tests/test_embeddings.py`, `tests/test_format_deps.py`, `tests/test_formats.py` |
| `src/hive_planner/normalizer.py` | `tests/test_compiler.py`, `tests/test_formats.py`, `tests/test_formats_v3.py` |
| `src/hive_planner/normalizers/csv.py` | `tests/test_formats_v3.py` |
| `src/hive_planner/normalizers/docx.py` | `tests/test_formats.py` |
| `src/hive_planner/normalizers/html.py` | `tests/test_formats_v3.py` |
| `src/hive_planner/normalizers/pdf.py` | `tests/test_formats.py`, `tests/test_ocr_runtime.py` |
| `src/hive_planner/normalizers/pptx.py` | `tests/test_formats_v3.py` |
| `src/hive_planner/normalizers/text.py` | `tests/test_compiler.py` |
| `src/hive_planner/ocr_runtime.py` | `tests/test_ocr_runtime.py` |
| `src/hive_planner/pipeline.py` | `tests/test_compiler.py`, `tests/test_embeddings.py`, `tests/test_format_deps.py`, `tests/test_formats.py`, `tests/test_formats_v3.py`, `tests/test_impact.py`, `tests/test_ocr_runtime.py`, `tests/test_source4s.py` |
| `src/hive_planner/portable_runtime.py` | `tests/test_portable_runtime.py`, `tests/test_runtime_paths.py` |
| `src/hive_planner/project_profile.py` | `tests/test_agent_handoff.py`, `tests/test_agents_memory.py`, `tests/test_ci_handoff.py`, `tests/test_cl_migration.py`, `tests/test_cl_runtime.py`, `tests/test_project_profile.py`, `tests/test_spec_drift.py`, `tests/test_unified_handoff.py`, `tests/test_wiring_audit.py` |
| `src/hive_planner/roadmap_status.py` | `tests/test_roadmap_status.py` |
| `src/hive_planner/rosetta_eject.py` | `tests/test_rosetta_eject.py` |
| `src/hive_planner/rosetta_nav.py` | `tests/test_ci_handoff.py`, `tests/test_rosetta_nav.py`, `tests/test_spec_drift.py`, `tests/test_wiring_audit.py` |
| `src/hive_planner/runtime_paths.py` | `tests/test_runtime_paths.py` |
| `src/hive_planner/source4s.py` | `tests/test_format_deps.py`, `tests/test_source4s.py` |
| `src/hive_planner/spec_drift.py` | `tests/test_agents_memory.py`, `tests/test_ci_handoff.py`, `tests/test_rosetta_nav.py`, `tests/test_security_validation.py`, `tests/test_spec_drift.py` |
| `src/hive_planner/translator.py` | `tests/test_cartridge_promote.py`, `tests/test_translator.py` |
| `src/hive_planner/vendor_sync.py` | `tests/test_agent_handoff.py`, `tests/test_cl_migration.py`, `tests/test_cl_runtime.py`, `tests/test_portable_runtime.py`, `tests/test_unified_handoff.py` |
| `src/hive_planner/wiring_audit.py` | `tests/test_wiring_audit.py` |
| `.cursor/hooks/*.py` + hive-continual-learning stop hook | `tests/test_cursor_hooks_compat.py` |
