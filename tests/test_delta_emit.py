from __future__ import annotations

import json
from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.delta_emit import AUTO_SYNC_PREFIX, sync_delta_cartridge, sync_delta_file
from hive_planner.emitter import emit_cartridge
from hive_planner.embeddings import BUILTIN_MODEL_ID, embed_texts
from hive_planner.emitter import select_chunks
from hive_planner.models import ChunkRecord


def _write_delta_tree(paths: RepoPaths, feature: str) -> None:
    delta = paths.root / "docs" / "delta"
    delta.mkdir(parents=True, exist_ok=True)
    (delta / "00_holistic.md").write_text("# Holistic\n\nMission alpha\n", encoding="utf-8")
    (delta / "10_macro.md").write_text("# Macro\n\nSubsystem beta\n", encoding="utf-8")
    micro_dir = delta / "20_micro"
    micro_dir.mkdir(parents=True, exist_ok=True)
    (micro_dir / f"{feature}.md").write_text(f"# Micro\n\nFeature {feature}\n", encoding="utf-8")


def test_sync_writes_holistic_macro_micro(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-delta-emit-v1"
    _write_delta_tree(paths, feature)

    results, written, warnings = sync_delta_cartridge(paths, feature)
    assert results["holistic"] == "written"
    assert results["macro"] == "written"
    assert results["micro"] == "written"
    assert len(written) == 3
    assert AUTO_SYNC_PREFIX in (paths.cartridge / "holistic.md").read_text(encoding="utf-8")
    assert "Mission alpha" in (paths.cartridge / "holistic.md").read_text(encoding="utf-8")
    assert not warnings


def test_sync_skips_draft_banner(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-delta-emit-v1"
    _write_delta_tree(paths, feature)
    draft = paths.cartridge / "holistic.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("\n<!-- DRAFT: review before promoting -->\n\nOld draft\n", encoding="utf-8")

    results, _, warnings = sync_delta_cartridge(paths, feature)
    assert results["holistic"].startswith("skipped")
    assert "Old draft" in draft.read_text(encoding="utf-8")
    assert any("Skipped cartridge/holistic.md" in w for w in warnings)


def test_force_delta_overwrites_draft(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-delta-emit-v1"
    _write_delta_tree(paths, feature)
    draft = paths.cartridge / "macro.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("<!-- DRAFT: review before promoting -->\n\nStale\n", encoding="utf-8")

    results, _, _ = sync_delta_cartridge(paths, feature, force=True)
    assert results["macro"] in {"written", "updated"}
    assert "Subsystem beta" in draft.read_text(encoding="utf-8")


def test_auto_sync_updates_on_reemit(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-delta-emit-v1"
    _write_delta_tree(paths, feature)
    sync_delta_cartridge(paths, feature)

    holistic = paths.root / "docs" / "delta" / "00_holistic.md"
    holistic.write_text("# Holistic\n\nMission gamma\n", encoding="utf-8")

    results, _, _ = sync_delta_cartridge(paths, feature)
    assert results["holistic"] == "updated"
    assert "Mission gamma" in (paths.cartridge / "holistic.md").read_text(encoding="utf-8")


def test_emit_manifest_records_delta_sync(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-delta-emit-v1"
    _write_delta_tree(paths, feature)

    outputs, _ = emit_cartridge(paths, feature, force_delta=True)
    assert "holistic" in outputs
    manifest = json.loads((paths.cartridge / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stats"]["delta_sync"]["holistic"] in {"written", "updated"}


def test_select_chunks_respects_embedding_model_id() -> None:
    query = "embedding retrieval semantic ranking"
    chunks = [
        ChunkRecord("a-c0", "a", "h", "unrelated kitchen recipes", chunk_index=0),
        ChunkRecord("b-c0", "b", "h", "vector semantic ranking improves retrieval", chunk_index=0),
    ]
    vectors = {}
    for chunk in chunks:
        vecs, _ = embed_texts([chunk.text], model_id=BUILTIN_MODEL_ID)
        vectors[chunk.chunk_id] = vecs[0]

    selected = select_chunks(
        chunks,
        query,
        embedding_vectors=vectors,
        embedding_model_id=BUILTIN_MODEL_ID,
    )
    assert selected[0].doc_id == "b"


def test_sync_delta_file_missing_source(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    source = paths.root / "docs" / "delta" / "00_holistic.md"
    target = paths.cartridge / "holistic.md"
    status, out = sync_delta_file(paths, source, target)
    assert status == "missing"
    assert out is None
