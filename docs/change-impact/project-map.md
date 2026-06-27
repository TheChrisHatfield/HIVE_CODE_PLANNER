# Project Map

**Hook:** `change.impact`, `next.files`

Manual v1 map of modules → dependencies. Use `impact-sync-maps` to merge new src modules (Stage 5B).

| Module | Role | Spec / Delta deps |
|--------|------|-------------------|
| `docs/delta/*.md` | Primary planning truth | `context.delta` |
| `docs/planning-rosetta-stone.md` | Hook legend | `planning.rosetta` |
| `src/hive_planner/__main__.py` |   main   | (auto-sync) |
| `src/hive_planner/agents_memory.py` | AGENTS.md lint/propose | `agents-memory-ci-v1` |
| `src/hive_planner/call_graph.py` | call graph | (auto-sync) |
| `src/hive_planner/cartridge_pack.py` | cartridge pack | (auto-sync) |
| `src/hive_planner/chunker.py` | Chunking | `compiler.pipeline` |
| `src/hive_planner/ci_handoff.py` | ci handoff | (auto-sync) |
| `src/hive_planner/cli.py` | CLI entry | `docs/specs/*/tasks.md` |
| `src/hive_planner/config.py` | config | (auto-sync) |
| `src/hive_planner/delta_emit.py` | Delta → cartridge sync | `cartridge-delta-emit-v1` |
| `src/hive_planner/discovery.py` | discovery | (auto-sync) |
| `src/hive_planner/embeddings.py` | Hybrid retrieval index | `embedding-retrieval-v1` |
| `src/hive_planner/emitter.py` | Cartridge emit | `context.cartridge` |
| `src/hive_planner/impact.py` | Impact packets | `change-impact-v1` |
| `src/hive_planner/indexer.py` | JSON indexes | `context.metadata` |
| `src/hive_planner/map_sync.py` | map sync | (auto-sync) |
| `src/hive_planner/models.py` | models | (auto-sync) |
| `src/hive_planner/normalizer.py` | Format dispatch | `context.document_sourcing` |
| `src/hive_planner/normalizers/csv.py` | csv | (auto-sync) |
| `src/hive_planner/normalizers/docx.py` | DOCX normalize | `cartridge-compiler-v2` |
| `src/hive_planner/normalizers/html.py` | html | (auto-sync) |
| `src/hive_planner/normalizers/pdf.py` | PDF normalize | `cartridge-compiler-v2` |
| `src/hive_planner/normalizers/pptx.py` | pptx | (auto-sync) |
| `src/hive_planner/normalizers/text.py` | text | (auto-sync) |
| `src/hive_planner/pipeline.py` | Ingest orchestration | `cartridge-compiler-v2` |
| `src/hive_planner/roadmap_status.py` | roadmap status | (auto-sync) |
| `src/hive_planner/spec_drift.py` | spec drift | (auto-sync) |
| `src/hive_planner/translator.py` | Rule-based cartridge drafts | `cartridge-translator-v1` |
