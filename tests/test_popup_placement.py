from __future__ import annotations

import json
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")

from hive_planner.launcher.popup_placement import (
    PlacementStore,
    format_geometry,
    format_position,
    install_popup_memory,
    parse_window_size,
    remember_popup,
    titlebar_on_a_monitor,
)


PRIMARY = [(0, 0, 1920, 1080)]
LEFT_AND_PRIMARY = [(-1920, 0, 0, 1080), (0, 0, 1920, 1080)]


def test_format_geometry_allows_negative_coordinates() -> None:
    # Tk reads a bare minus as "from the opposite screen edge".
    assert format_position(-1500, 80) == "+-1500+80"
    assert format_position(40, -20) == "+40+-20"
    assert format_geometry(600, 440, -1500, 80) == "600x440+-1500+80"
    assert format_geometry(600, 440, 40, -20) == "600x440+40+-20"
    assert parse_window_size("600x440+-1500+80") == (600, 440)
    assert parse_window_size("+50+50") is None


def test_titlebar_must_sit_on_a_monitor() -> None:
    assert titlebar_on_a_monitor(2000, 40, 600, LEFT_AND_PRIMARY) is False
    assert titlebar_on_a_monitor(-1500, 40, 600, LEFT_AND_PRIMARY) is True
    assert titlebar_on_a_monitor(100, 40, 600, PRIMARY) is True
    assert titlebar_on_a_monitor(100, 40, 1, PRIMARY) is True
    assert titlebar_on_a_monitor(100, 40, 600, []) is True


def test_placement_store_roundtrip_skips_corrupt_entries(tmp_path: Path) -> None:
    path = tmp_path / "popup-placements.json"
    path.write_text(
        json.dumps(
            {
                "Add workspace link": {"x": -1600, "y": 120},
                "bad": {"x": "nope"},
                "far": {"x": 999999, "y": 1},
                "": {"x": 1, "y": 1},
            }
        ),
        encoding="utf-8",
    )
    store = PlacementStore(path)
    assert store.get("Add workspace link") == (-1600, 120)
    assert store.get("bad") is None
    assert store.get("far") is None
    store.set("Load Sources", 30, 44)
    reloaded = PlacementStore(path)
    assert reloaded.get("Add workspace link") == (-1600, 120)
    assert reloaded.get("Load Sources") == (30, 44)


def test_two_store_objects_keep_each_others_titles(tmp_path: Path) -> None:
    path = tmp_path / "popup-placements.json"
    first = PlacementStore(path)
    second = PlacementStore(path)
    first.set("Add workspace link", 10, 20)
    second.set("Load Sources", 30, 40)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["Add workspace link"] == {"x": 10, "y": 20}
    assert saved["Load Sources"] == {"x": 30, "y": 40}


def test_corrupt_file_does_not_raise(tmp_path: Path) -> None:
    path = tmp_path / "popup-placements.json"
    path.write_text("{", encoding="utf-8")
    store = PlacementStore(path)
    assert store.get("Add workspace link") is None
    store.set("Add workspace link", 8, 9)
    assert json.loads(path.read_text(encoding="utf-8"))["Add workspace link"] == {"x": 8, "y": 9}


def _pump(root, ms: int) -> None:
    root.after(ms, root.quit)
    root.mainloop()


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_dialog_reopens_at_saved_position_and_remembers_a_move(tmp_path: Path, tk_root) -> None:
    root = tk_root
    store = PlacementStore(tmp_path / "popup-placements.json")
    store.set("Add workspace link", 320, 140)
    dialog = tk.Toplevel(root)
    remember_popup(
        dialog,
        store=store,
        monitors=lambda: PRIMARY,
        save_delay_ms=0,
    )
    dialog.title("Add workspace link")
    dialog.grab_set()
    dialog.geometry("600x440")
    root.update()
    assert dialog.winfo_x() == 320
    assert dialog.winfo_y() == 140
    assert dialog.winfo_width() == 600
    assert dialog.winfo_height() == 440

    dialog.geometry("600x440+410+180")
    root.update()
    assert store.get("Add workspace link") == (410, 180)

    dialog.grab_release()
    dialog.destroy()
    root.update()

    again = tk.Toplevel(root)
    remember_popup(again, store=store, monitors=lambda: PRIMARY, save_delay_ms=0)
    again.title("Add workspace link")
    again.geometry("600x440")
    root.update()
    assert again.winfo_x() == 410
    assert again.winfo_y() == 180
    assert again.winfo_width() == 600
    assert again.winfo_height() == 440
    again.destroy()
    root.update()


def test_new_dialog_opens_on_the_parent_monitor(tmp_path: Path, tk_root) -> None:
    root = tk_root
    root.attributes("-alpha", 0.0)
    root.deiconify()
    root.geometry("920x680+400+200")
    root.update()
    store = PlacementStore(tmp_path / "popup-placements.json")
    dialog = tk.Toplevel(root)
    remember_popup(dialog, store=store, monitors=lambda: PRIMARY)
    dialog.title("Add workspace link")
    dialog.transient(root)
    dialog.geometry("600x440")
    root.update()
    expected_x = root.winfo_rootx() + max(0, (root.winfo_width() - 600) // 2)
    expected_y = root.winfo_rooty() + max(0, (root.winfo_height() - 440) // 2)
    assert dialog.winfo_x() == expected_x
    assert dialog.winfo_y() == expected_y
    assert dialog.winfo_x() != 0
    assert dialog.winfo_width() == 600
    assert dialog.winfo_height() == 440
    assert store.get("Add workspace link") is None
    dialog.destroy()
    root.withdraw()
    root.attributes("-alpha", 1.0)
    root.update()


def test_offscreen_position_is_kept_until_the_dialog_is_moved(tmp_path: Path, tk_root) -> None:
    root = tk_root
    store = PlacementStore(tmp_path / "popup-placements.json")
    store.set("Add workspace link", 9000, 40)
    dialog = tk.Toplevel(root)
    remember_popup(
        dialog,
        store=store,
        monitors=lambda: PRIMARY,
        save_delay_ms=0,
    )
    dialog.title("Add workspace link")
    dialog.geometry("300x200+80+60")
    root.update()
    _pump(root, 50)
    assert dialog.winfo_x() != 9000
    assert dialog.winfo_width() == 300
    assert dialog.winfo_height() == 200
    assert store.get("Add workspace link") == (9000, 40)
    dialog.destroy()
    root.update()


def test_other_titled_popups_share_memory_tooltips_do_not(tmp_path: Path, tk_root) -> None:
    root = tk_root
    store = PlacementStore(tmp_path / "popup-placements.json")
    store.set("Implementation loop feature", 240, 90)
    install_popup_memory(root, store=store, monitors=lambda: PRIMARY, save_delay_ms=0)
    prompt = tk.Toplevel(root)
    prompt.withdraw()
    prompt.title("Implementation loop feature")
    prompt.geometry("280x120+20+20")
    prompt.deiconify()
    root.update()
    assert prompt.winfo_x() == 240
    assert prompt.winfo_y() == 90
    assert prompt.winfo_width() == 280
    assert prompt.winfo_height() == 120

    tip = tk.Toplevel(root)
    tip.overrideredirect(True)
    tip.title("Implementation loop feature")
    tip.geometry("40x20+12+12")
    root.update()
    assert tip.winfo_x() == 12
    assert tip.winfo_y() == 12
    assert store.get("Implementation loop feature") == (240, 90)
    prompt.destroy()
    tip.destroy()
    root.update()


def test_dialog_helper_uses_shared_popup_memory() -> None:
    source = (Path(__file__).resolve().parents[1] / "src/hive_planner/launcher/app.py").read_text(
        encoding="utf-8"
    )
    assert "remember_popup(dialog)" in source
    assert "install_popup_memory(root)" in source
