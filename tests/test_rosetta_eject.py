from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.rosetta_eject import (
    CONTRACT_FILENAME,
    EJECT_DIRNAME,
    PROMPT_FILENAME,
    README_FILENAME,
    RosettaEjectError,
    build_session_start_prompt,
    eject_rosetta_cartridge,
    infer_project_name,
    load_session_contract_text,
    resolve_session_contract_path,
)


def test_resolve_session_contract_prefers_repo_docs(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    docs = root / "docs"
    docs.mkdir(parents=True)
    repo_contract = docs / CONTRACT_FILENAME
    repo_contract.write_text("# repo contract\n", encoding="utf-8")

    resolved = resolve_session_contract_path(root)
    assert resolved == repo_contract


def test_resolve_session_contract_skips_empty_repo_docs(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    docs = root / "docs"
    docs.mkdir(parents=True)
    (docs / CONTRACT_FILENAME).write_text("", encoding="utf-8")

    resolved = resolve_session_contract_path(root)
    assert resolved is not None
    assert resolved.name == CONTRACT_FILENAME
    assert "bootstrap_templates" in resolved.as_posix()
    assert resolved.read_text(encoding="utf-8").strip()


def test_resolve_session_contract_falls_back_to_packaged() -> None:
    resolved = resolve_session_contract_path(None)
    assert resolved is not None
    assert resolved.name == CONTRACT_FILENAME
    assert "bootstrap_templates" in resolved.as_posix()


def test_load_session_contract_text(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / CONTRACT_FILENAME).write_text("# contract\n", encoding="utf-8")
    assert load_session_contract_text(repo_root=root).startswith("# contract")


def test_build_session_start_prompt_includes_project_name() -> None:
    text = build_session_start_prompt(project_name="TaskApp")
    assert "TaskApp" in text
    assert "Planning Rosetta Stone" in text
    assert "[CTX:" in text


def test_infer_project_name_from_repo_root(tmp_path: Path) -> None:
    root = tmp_path / "my-cool-app"
    root.mkdir()
    assert infer_project_name(root) == "my-cool-app"
    assert infer_project_name(None) == "My Project"


def test_eject_rosetta_cartridge_writes_bundle(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / CONTRACT_FILENAME).write_text("# eject me\n", encoding="utf-8")

    result = eject_rosetta_cartridge(tmp_path / "exports", repo_root=root, project_name="Demo")
    bundle = tmp_path / "exports" / EJECT_DIRNAME
    assert result.output_dir == bundle
    assert result.contract_path.read_text(encoding="utf-8").startswith("# eject me")
    assert "Demo" in result.prompt_path.read_text(encoding="utf-8")
    assert result.readme_path.is_file()
    assert len(result.files_written) == 3
    assert (bundle / PROMPT_FILENAME).is_file()
    assert (bundle / README_FILENAME).is_file()


def test_eject_missing_contract_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hive_planner.rosetta_eject.resolve_session_contract_path",
        lambda _repo_root=None: None,
    )
    with pytest.raises(RosettaEjectError):
        eject_rosetta_cartridge(tmp_path, repo_root=tmp_path)


def test_rosetta_eject_cli_writes_files(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / CONTRACT_FILENAME).write_text("# cli contract\n", encoding="utf-8")

    from hive_planner.cli import main

    code = main(["--root", str(root), "rosetta-eject", "--project-name", "CLI Demo"])
    assert code == 0
    bundle = root / EJECT_DIRNAME
    assert (bundle / CONTRACT_FILENAME).is_file()
    assert "CLI Demo" in (bundle / PROMPT_FILENAME).read_text(encoding="utf-8")


def test_rosetta_eject_cli_prompt_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / CONTRACT_FILENAME).write_text("# contract\n", encoding="utf-8")

    from hive_planner.cli import main

    code = main(["--root", str(root), "rosetta-eject", "--prompt-only", "--project-name", "Only"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Only" in out
    assert "Planning Rosetta Stone" in out
