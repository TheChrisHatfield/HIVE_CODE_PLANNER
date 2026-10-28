from __future__ import annotations

from hive_planner.launcher.home_groups import (
    HOME_ACTIONS,
    default_home_groups,
    move_home_action,
    move_home_group,
    normalize_home_groups,
    rename_home_group,
)


def _action_ids(groups) -> list[str]:
    return [action_id for group in groups for action_id in group["actions"]]


def test_default_groups_cover_every_home_action() -> None:
    groups = default_home_groups()
    assert _action_ids(groups) == list(HOME_ACTIONS)
    assert [group["title"] for group in groups] == ["Project", "Loops", "Sources", "Memory", "Setup"]
    assert "Loop controls" == HOME_ACTIONS["loop_controls"]["label"]
    assert "CodeSpec" == HOME_ACTIONS["codespec"]["label"]


def test_normalize_drops_unknown_and_appends_missing() -> None:
    groups = normalize_home_groups(
        [
            {"id": "project", "title": "  Daily work  ", "actions": ["ci_check", "not-real", "ci_check"]},
        ]
    )
    assert groups[0]["title"] == "Daily work"
    assert groups[0]["actions"][0] == "ci_check"
    assert "not-real" not in _action_ids(groups)
    assert set(_action_ids(groups)) == set(HOME_ACTIONS)
    assert _action_ids(groups).count("ci_check") == 1


def test_rename_and_move_group() -> None:
    groups = default_home_groups()
    groups = rename_home_group(groups, 1, "My loops")
    assert groups[1]["title"] == "My loops"
    groups = move_home_group(groups, 1, -1)
    assert groups[0]["title"] == "My loops"
    assert groups[0]["id"] == "loops"


def test_config_roundtrip_keeps_renamed_home_groups(tmp_path, monkeypatch) -> None:
    from hive_planner.launcher.config import LauncherConfig, load_config, save_config

    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: tmp_path)
    groups = rename_home_group(default_home_groups(), 0, "Daily")
    save_config(
        LauncherConfig(
            hive_planner_root=str(tmp_path),
            home_action_groups=groups,
            home_arrange_enabled=True,
        )
    )
    loaded = load_config()
    assert loaded.home_arrange_enabled is True
    assert loaded.home_action_groups[0]["title"] == "Daily"
    assert _action_ids(loaded.home_action_groups) == list(HOME_ACTIONS)


def test_move_action_crosses_group_boundary() -> None:
    groups = default_home_groups()
    codespec_group = next(i for i, group in enumerate(groups) if "codespec" in group["actions"])
    groups = move_home_action(groups, "codespec", 1)
    next_group = groups[codespec_group + 1]
    assert groups[codespec_group]["actions"] == ["loop_controls"]
    assert next_group["actions"][0] == "codespec"
    assert "load_sources" in next_group["actions"]
    assert "codespec" not in groups[codespec_group]["actions"]


def test_move_action_swaps_inside_group() -> None:
    groups = default_home_groups()
    groups = move_home_action(groups, "codespec", -1)
    loops = next(group for group in groups if group["id"] == "loops")
    assert loops["actions"] == ["codespec", "loop_controls"]
