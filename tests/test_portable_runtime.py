from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.portable_runtime import (
    PORTABLE_RUNTIME_MARKER,
    clear_stale_tk_library_env,
    ensure_portable_runtime,
    verify_bundled_templates,
    verify_portable_deploy,
)


def test_verify_bundled_templates_in_dev_tree() -> None:
    ok, missing = verify_bundled_templates()
    assert ok is True
    assert missing == []


def test_ensure_portable_runtime_deploys_overlays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))

    report = ensure_portable_runtime(tmp_path, force=True)

    assert report.bundled_ok is True
    assert report.deployed_ok is True
    assert report.ok is True
    assert (tmp_path / PORTABLE_RUNTIME_MARKER).is_file()
    assert (tmp_path / ".hive" / "spec-kit" / "WORKFLOW.md").is_file()
    assert (tmp_path / ".cursor" / "plugins" / "hive-continual-learning" / "WORKFLOW.md").is_file()

    ok, missing = verify_portable_deploy(tmp_path)
    assert ok is True
    assert missing == []


def test_ensure_portable_runtime_skips_rerun_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))

    first = ensure_portable_runtime(tmp_path, force=True)
    second = ensure_portable_runtime(tmp_path, force=False)

    assert first.ok is True
    assert second.ok is True
    assert second.files_written == []


def test_ensure_portable_runtime_skips_marker_when_deploy_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.portable_runtime as pr
    from hive_planner import vendor_sync as vendor_sync_mod

    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))

    def _fail_deploy(*_args, **_kwargs) -> None:
        pass

    monkeypatch.setattr(vendor_sync_mod, "deploy_unified_vendor_artifacts", _fail_deploy)
    monkeypatch.setattr(
        pr,
        "verify_portable_artifacts",
        lambda _root: (False, [".hive/spec-kit/WORKFLOW.md"]),
    )

    report = pr.ensure_portable_runtime(tmp_path, force=True)

    assert report.ok is False
    assert not (tmp_path / PORTABLE_RUNTIME_MARKER).is_file()


def test_ensure_portable_runtime_repairs_deleted_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))

    first = ensure_portable_runtime(tmp_path, force=True)
    assert first.ok is True

    workflow = tmp_path / ".hive" / "spec-kit" / "WORKFLOW.md"
    assert workflow.is_file()
    workflow.unlink()

    repaired = ensure_portable_runtime(tmp_path, force=False)
    assert repaired.ok is True
    assert workflow.is_file()


def test_run_portable_bootstrap_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.service import run_portable_bootstrap

    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))

    result = run_portable_bootstrap(force=True)

    assert result["ok"] is True
    assert result["deployed_ok"] is True


def test_clear_stale_tk_library_env_drops_missing_portable_tcl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "HivePlannerPortable" / "_internal" / "_tcl_data"
    broken.mkdir(parents=True)
    monkeypatch.setenv("TCL_LIBRARY", str(broken))
    monkeypatch.setenv("TK_LIBRARY", str(tmp_path / "HivePlannerPortable" / "_tk_data"))
    dropped = clear_stale_tk_library_env()
    assert "TCL_LIBRARY" in dropped
    assert "TK_LIBRARY" in dropped
    assert "TCL_LIBRARY" not in __import__("os").environ
    assert "TK_LIBRARY" not in __import__("os").environ


def test_clear_stale_tk_library_env_keeps_readable_cpython_tcl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tcl = tmp_path / "Python311" / "tcl8.6"
    tk = tmp_path / "Python311" / "tk8.6"
    tcl.mkdir(parents=True)
    tk.mkdir(parents=True)
    (tcl / "init.tcl").write_text("# tcl\n", encoding="utf-8")
    (tk / "tk.tcl").write_text("# tk\n", encoding="utf-8")
    monkeypatch.setenv("TCL_LIBRARY", str(tcl))
    monkeypatch.setenv("TK_LIBRARY", str(tk))
    assert clear_stale_tk_library_env() == []
    assert __import__("os").environ["TCL_LIBRARY"] == str(tcl)
    assert __import__("os").environ["TK_LIBRARY"] == str(tk)


def test_clear_stale_tk_library_env_frozen_retargets_meipass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.portable_runtime as pr

    broken = tmp_path / "HivePlannerPortable" / "_internal" / "_tcl_data"
    broken.mkdir(parents=True)
    bundled = tmp_path / "meipass" / "_tcl_data"
    bundled.mkdir(parents=True)
    (bundled / "init.tcl").write_text("# bundled\n", encoding="utf-8")
    monkeypatch.setenv("TCL_LIBRARY", str(broken))
    monkeypatch.delenv("TK_LIBRARY", raising=False)
    monkeypatch.setattr(pr.sys, "frozen", True, raising=False)
    monkeypatch.setattr(pr.sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)
    dropped = clear_stale_tk_library_env()
    assert "TCL_LIBRARY" in dropped
    assert __import__("os").environ["TCL_LIBRARY"] == str(bundled)


def test_clear_stale_tk_library_env_frozen_drops_usable_path_outside_meipass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.portable_runtime as pr

    outside = tmp_path / "Python311" / "tcl8.6"
    outside.mkdir(parents=True)
    (outside / "init.tcl").write_text("# cpython\n", encoding="utf-8")
    bundled = tmp_path / "meipass" / "_tcl_data"
    bundled.mkdir(parents=True)
    (bundled / "init.tcl").write_text("# bundled\n", encoding="utf-8")
    monkeypatch.setenv("TCL_LIBRARY", str(outside))
    monkeypatch.delenv("TK_LIBRARY", raising=False)
    monkeypatch.setattr(pr.sys, "frozen", True, raising=False)
    monkeypatch.setattr(pr.sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)
    dropped = clear_stale_tk_library_env()
    assert "TCL_LIBRARY" in dropped
    assert __import__("os").environ["TCL_LIBRARY"] == str(bundled)


def test_clear_stale_tk_library_env_drops_unc_and_nul(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TCL_LIBRARY", r"\\server\share\tcl")
    monkeypatch.setenv("TK_LIBRARY", "//server/share/tk")
    dropped = clear_stale_tk_library_env()
    assert "TCL_LIBRARY" in dropped
    assert "TK_LIBRARY" in dropped
    assert "TCL_LIBRARY" not in __import__("os").environ
    assert "TK_LIBRARY" not in __import__("os").environ
