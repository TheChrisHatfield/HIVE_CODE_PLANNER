from pathlib import Path

from hive_planner.launcher.service import (
    CursorWorkspace,
    detect_active_cursor_project,
    match_cursor_workspace_from_title,
)


def _ws(path: Path, name: str | None = None) -> CursorWorkspace:
    return CursorWorkspace(
        path=str(path.resolve()),
        name=name or path.name,
        location=str(path.parent),
        exists=True,
        hive_ready=False,
        has_cursor_dir=False,
        has_git=False,
        entry_kind="folder",
    )


def test_match_title_does_not_treat_a_short_name_as_a_substring(tmp_path: Path) -> None:
    other = tmp_path / "other-app"
    other.mkdir()
    (other / "README.md").write_text("x\n", encoding="utf-8")
    target = tmp_path / "app"
    target.mkdir()
    (target / "README.md").write_text("y\n", encoding="utf-8")
    workspaces = [_ws(other), _ws(target)]

    matched = match_cursor_workspace_from_title("README.md - app - Cursor", workspaces)
    assert matched is not None
    assert matched.path == str(target.resolve())


def test_match_title_does_not_pick_the_first_folder_that_has_that_file(tmp_path: Path) -> None:
    first = tmp_path / "recent"
    first.mkdir()
    (first / "app.py").write_text("print(1)\n", encoding="utf-8")
    second = tmp_path / "active-tab"
    second.mkdir()
    (second / "app.py").write_text("print(2)\n", encoding="utf-8")
    workspaces = [_ws(first), _ws(second)]

    matched = match_cursor_workspace_from_title("app.py - missing-name - Cursor", workspaces)
    assert matched is None
    fallback = detect_active_cursor_project(
        hive_active=str(second),
        window_titles=["app.py - missing-name - Cursor"],
        workspaces=workspaces,
    )
    assert fallback is not None
    assert fallback.path == str(first.resolve())
