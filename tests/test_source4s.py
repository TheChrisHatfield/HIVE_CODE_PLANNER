from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.source4s import (
    SOURCE4S_DIR_NAME,
    list_source4s_files,
    run_source4s,
    stage_source4s_files,
)


def test_stage_source4s_accepts_txt_and_pdf(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    txt = tmp_path / "notes.txt"
    txt.write_text("Mission: build source4s upload path.\n", encoding="utf-8")
    pdf = tmp_path / "brief.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    copied, warnings = stage_source4s_files(paths, [txt, pdf, tmp_path / "skip.md"])
    assert len(copied) == 2
    assert any("source4s/notes.txt" in rel for rel in copied)
    assert any("source4s/brief.pdf" in rel for rel in copied)
    assert any("skip.md" in w for w in warnings)


def test_stage_source4s_deduplicates_filename(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    dest = paths.sources / SOURCE4S_DIR_NAME / "dup.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("existing", encoding="utf-8")

    incoming = tmp_path / "dup.txt"
    incoming.write_text("new content", encoding="utf-8")
    copied, _ = stage_source4s_files(paths, [incoming])
    assert copied == ["context-library/sources/source4s/dup-2.txt"]


def test_run_source4s_ingest_only(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    doc = tmp_path / "ref.txt"
    doc.write_text(
        "# Reference\n\nAcceptance criteria for source4s feature scope.\n",
        encoding="utf-8",
    )

    result = run_source4s(paths, [doc], feature=None, update_cartridge=False)
    assert result.ok
    assert result.copied
    assert result.processed >= 1
    assert result.source_context_path is None
    assert list_source4s_files(paths)


def test_run_source4s_links_cartridge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "source4s-v1"
    doc = tmp_path / "plan.txt"
    doc.write_text(
        "# Plan\n\nMission: cartridge-linked reference uploads for planning agents.\n",
        encoding="utf-8",
    )

    emitted: list[str] = []

    def fake_emit(repo_paths: RepoPaths, feat: str, **kwargs: object) -> tuple[dict, list[str]]:
        assert feat == feature
        source_path = repo_paths.cartridge / "source-context.md"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("# Source Context\n\nlinked\n", encoding="utf-8")
        emitted.append(feat)
        return {"source_context": source_path}, []

    monkeypatch.setattr("hive_planner.source4s.emit_source_context", fake_emit)

    result = run_source4s(paths, [doc], feature=feature, update_cartridge=True)
    assert result.ok
    assert result.source_context_path == "cartridge/source-context.md"
    assert emitted == [feature]


def test_run_source4s_requires_files(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    result = run_source4s(paths, [], feature="x-v1")
    assert not result.ok
    assert result.error


def test_load_sources_skips_delta_and_pack_sync(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "load-sources-v1"
    holistic = paths.cartridge / "holistic.md"
    holistic.parent.mkdir(parents=True, exist_ok=True)
    holistic.write_text("<!-- MANUAL: keep me -->\n\n# Holistic\n", encoding="utf-8")

    doc = tmp_path / "ref.txt"
    doc.write_text("# Reference\n\nMission for load-sources feature.\n", encoding="utf-8")

    result = run_source4s(paths, [doc], feature=feature, update_cartridge=True)
    assert result.ok
    assert holistic.read_text(encoding="utf-8").startswith("<!-- MANUAL:")
    assert (paths.cartridge / "source-context.md").is_file()
    assert "pack_sync" not in json.loads((paths.cartridge / "manifest.json").read_text(encoding="utf-8")).get(
        "stats", {}
    )
