"""Remember where Hive Planner popup windows were last placed.

Each dialog title keeps its own screen position, including monitors to the
left of the primary display (negative coordinates). Hover tooltips and other
override-redirect windows are left alone. A saved spot that is no longer on
any monitor is ignored until that dialog is moved again.
"""

from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path

_COORD_LIMIT = 32000
_SAVE_DELAY_MS = 250


def format_position(x: int, y: int) -> str:
    """Tk position suffix.

    A bare minus means "from the right/bottom edge", so a negative coordinate
    has to keep the leading plus: ``+-1500+-20``.
    """
    return f"+{int(x)}+{int(y)}"


def format_geometry(width: int, height: int, x: int, y: int) -> str:
    """Size plus position. Position-only moves should use format_position."""
    return f"{int(width)}x{int(height)}{format_position(x, y)}"


def parse_window_size(geometry: str) -> tuple[int, int] | None:
    head = geometry.split("+", 1)[0].split("-", 1)[0]
    if "x" not in head:
        return None
    width_text, height_text = head.split("x", 1)
    try:
        width = int(width_text)
        height = int(height_text)
    except ValueError:
        return None
    if width <= 1 or height <= 1:
        return None
    return width, height


def titlebar_on_a_monitor(
    x: int,
    y: int,
    width: int,
    monitors: list[tuple[int, int, int, int]],
) -> bool:
    """True when a usable slice of the title bar sits on a monitor.

    An empty monitor list means the screens could not be listed, so the saved
    position is kept rather than discarded.
    """
    if not monitors:
        return True
    # An unrealized window reports a 1px size. Don't treat that as off-screen.
    bar_width = int(width) if int(width) >= 48 else 240
    bar_right = x + bar_width
    bar_bottom = y + 32
    for left, top, right, bottom in monitors:
        overlap_w = min(bar_right, right) - max(x, left)
        overlap_h = min(bar_bottom, bottom) - max(y, top)
        if overlap_w >= 48 and overlap_h >= 16:
            return True
    return False


def list_monitors() -> list[tuple[int, int, int, int]]:
    """Physical monitor rectangles as (left, top, right, bottom)."""
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )
        found: list[tuple[int, int, int, int]] = []

        def _collect(_monitor, _hdc, rect_ptr, _data) -> int:
            rect = rect_ptr.contents
            found.append((int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)))
            return 1

        callback = callback_type(_collect)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)
        return found
    except (OSError, AttributeError, ValueError):
        return []


class PlacementStore:
    """JSON map of dialog title to last top-left position."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, tuple[int, int]] | None = None

    def get(self, title: str) -> tuple[int, int] | None:
        key = title.strip()
        if not key:
            return None
        return self._load().get(key)

    def set(self, title: str, x: int, y: int) -> None:
        key = title.strip()
        if not key:
            return
        if not (-_COORD_LIMIT <= int(x) <= _COORD_LIMIT and -_COORD_LIMIT <= int(y) <= _COORD_LIMIT):
            return
        # Re-read so another dialog's store object does not drop titles it has not seen.
        data = _read_points(self.path)
        data[key] = (int(x), int(y))
        self._data = data
        self._write(data)

    def _load(self) -> dict[str, tuple[int, int]]:
        if self._data is None:
            self._data = _read_points(self.path)
        return self._data

    def _write(self, data: dict[str, tuple[int, int]]) -> None:
        payload = {key: {"x": x, "y": y} for key, (x, y) in sorted(data.items())}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)


_default_store: PlacementStore | None = None


def default_store() -> PlacementStore:
    global _default_store
    if _default_store is None:
        from hive_planner.launcher.config import default_config_dir

        _default_store = PlacementStore(default_config_dir() / "popup-placements.json")
    return _default_store


def remember_popup(
    window: tk.Toplevel,
    *,
    store: PlacementStore | None = None,
    monitors=None,
    save_delay_ms: int = _SAVE_DELAY_MS,
) -> None:
    """Keep the window transparent until its saved position is applied, then track drags.

    It stays mapped so callers can still grab it. The window is shown after placement.
    """
    placement = store if store is not None else default_store()
    screens = monitors if monitors is not None else list_monitors
    window._hive_popup_tracked = True  # type: ignore[attr-defined]
    try:
        window.attributes("-alpha", 0.0)
    except tk.TclError:
        pass

    def place() -> None:
        title = "popup"
        applied = False
        try:
            if not window.winfo_exists():
                return
            title = window.title().strip() or "popup"
            saved = placement.get(title)
            # Position only. Putting a size in this geometry call runs before the
            # caller's "600x440" is applied and would shrink the dialog to 200x200.
            if saved is not None and titlebar_on_a_monitor(saved[0], saved[1], _window_width(window), screens()):
                _move_window(window, saved[0], saved[1])
                applied = True
        except tk.TclError:
            _reveal(window)
            return

        def finish() -> None:
            try:
                if not window.winfo_exists():
                    return
            except tk.TclError:
                return
            # transient() parks a new dialog at 0,0, which is the corner of the
            # primary monitor. Center it on Hive Planner until the user moves it.
            if not applied and _is_at_screen_origin(window):
                _center_on_parent(window)
            _reveal(window)
            _track_moves(window, title, placement, save_delay_ms=save_delay_ms)

        try:
            window.after(0, finish)
        except tk.TclError:
            _reveal(window)

    window.after_idle(place)


def install_popup_memory(
    root: tk.Misc,
    *,
    store: PlacementStore | None = None,
    monitors=None,
    save_delay_ms: int = _SAVE_DELAY_MS,
) -> None:
    """Apply the same memory to every later titled popup, including askstring."""
    if getattr(root, "_hive_popup_memory", False):
        return
    root._hive_popup_memory = True  # type: ignore[attr-defined]
    placement = store if store is not None else default_store()
    screens = monitors if monitors is not None else list_monitors

    def on_map(event) -> None:
        try:
            if not root.winfo_exists():
                return
        except tk.TclError:
            return
        window = event.widget
        if not isinstance(window, tk.Toplevel):
            return
        if getattr(window, "_hive_popup_tracked", False):
            return
        try:
            if not window.winfo_exists() or window.overrideredirect():
                return
            title = window.title().strip()
        except tk.TclError:
            return
        if not title:
            return
        window._hive_popup_tracked = True  # type: ignore[attr-defined]
        saved = placement.get(title)
        if saved is not None and titlebar_on_a_monitor(saved[0], saved[1], _window_width(window), screens()):
            _move_window(window, saved[0], saved[1])
        _track_moves(window, title, placement, save_delay_ms=save_delay_ms)

    root.bind_class("Toplevel", "<Map>", on_map, add="+")


def _read_points(path: Path) -> dict[str, tuple[int, int]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    points: dict[str, tuple[int, int]] = {}
    for key, value in raw.items():
        point = _point_from_json(key, value)
        if point is not None:
            points[key.strip()] = point
    return points


def _point_from_json(key: object, value: object) -> tuple[int, int] | None:
    if not isinstance(key, str) or not key.strip() or not isinstance(value, dict):
        return None
    try:
        x = int(value["x"])
        y = int(value["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-_COORD_LIMIT <= x <= _COORD_LIMIT and -_COORD_LIMIT <= y <= _COORD_LIMIT):
        return None
    return x, y


def _window_width(window: tk.Toplevel) -> int:
    try:
        window.update_idletasks()
        size = parse_window_size(window.geometry())
        if size is not None:
            return size[0]
        return max(window.winfo_width(), window.winfo_reqwidth(), 1)
    except tk.TclError:
        return 1


def _move_window(window: tk.Toplevel, x: int, y: int) -> None:
    """Move without setting a size, so a pending caller geometry is preserved."""
    try:
        window.geometry(format_position(x, y))
    except tk.TclError:
        return


def _is_at_screen_origin(window: tk.Toplevel) -> bool:
    try:
        return int(window.winfo_x()) == 0 and int(window.winfo_y()) == 0
    except tk.TclError:
        return False


def _center_on_parent(window: tk.Toplevel) -> None:
    parent = window.master
    try:
        if parent is None or not parent.winfo_viewable():
            return
        window.update_idletasks()
        width = int(window.winfo_width())
        height = int(window.winfo_height())
        if width <= 1 or height <= 1:
            width = int(window.winfo_reqwidth())
            height = int(window.winfo_reqheight())
        if width <= 1 or height <= 1:
            return
        x = int(parent.winfo_rootx()) + max(0, (int(parent.winfo_width()) - width) // 2)
        y = int(parent.winfo_rooty()) + max(0, (int(parent.winfo_height()) - height) // 2)
    except tk.TclError:
        return
    _move_window(window, x, y)


def _reveal(window: tk.Toplevel) -> None:
    try:
        if not window.winfo_exists():
            return
        window.deiconify()
        window.attributes("-alpha", 1.0)
        window.lift()
    except tk.TclError:
        return


def _track_moves(
    window: tk.Toplevel,
    title: str,
    store: PlacementStore,
    *,
    save_delay_ms: int,
) -> None:
    try:
        window.update_idletasks()
        origin = (int(window.winfo_x()), int(window.winfo_y()))
    except tk.TclError:
        return
    state: dict[str, object] = {"origin": origin, "job": None}

    def save_now() -> None:
        state["job"] = None
        point = state.get("origin")
        if not isinstance(point, tuple):
            return
        # Keep the last Configure position. winfo during Destroy is often 0, 0.
        store.set(title, int(point[0]), int(point[1]))

    def on_configure(event) -> None:
        if event.widget is not window:
            return
        try:
            point = (int(window.winfo_x()), int(window.winfo_y()))
        except tk.TclError:
            return
        if point == state.get("origin"):
            return
        state["origin"] = point
        job = state.get("job")
        if isinstance(job, str):
            try:
                window.after_cancel(job)
            except tk.TclError:
                pass
        try:
            state["job"] = window.after(save_delay_ms, save_now)
        except tk.TclError:
            save_now()

    def on_destroy(event) -> None:
        if event.widget is not window:
            return
        job = state.get("job")
        if not isinstance(job, str):
            return
        try:
            window.after_cancel(job)
        except tk.TclError:
            pass
        save_now()

    window.bind("<Configure>", on_configure, add="+")
    window.bind("<Destroy>", on_destroy, add="+")
