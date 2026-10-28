from __future__ import annotations

"""VoiceFlow-inspired palette (borrowed from KOKORO tts_overlay_unified.py)."""

import sys
import tkinter as tk
from tkinter import ttk

COLORS = {
    "bg": "#faf8f5",
    "fg": "#050a0f",
    "card": "#ffffff",
    "primary": "#10b981",
    "primary_light": "#34d399",
    "secondary": "#f0ebe5",
    "muted": "#6b7280",
    "border": "#e5e0da",
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
}

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUBTITLE = ("Segoe UI", 9)

_wheel_bindings: dict[int, tk.Misc] = {}
_wheel_stack: list[int] = []
_wheel_handlers_installed = False


def _resolve_wheel_target() -> tk.Misc | None:
    while _wheel_stack:
        widget_id = _wheel_stack[-1]
        target = _wheel_bindings.get(widget_id)
        if target is None:
            _wheel_stack.pop()
            continue
        try:
            if target.winfo_exists():
                return target
        except tk.TclError:
            pass
        _wheel_bindings.pop(widget_id, None)
        _wheel_stack.pop()
    return None


def _dispatch_wheel(event) -> str | None:
    target = _resolve_wheel_target()
    if target is not None and hasattr(target, "yview_scroll"):
        target.yview_scroll(int(-1 * (event.delta / 120)), "units")
    return None


def _dispatch_wheel_up(_event) -> str | None:
    target = _resolve_wheel_target()
    if target is not None and hasattr(target, "yview_scroll"):
        target.yview_scroll(-1, "units")
    return None


def _dispatch_wheel_down(_event) -> str | None:
    target = _resolve_wheel_target()
    if target is not None and hasattr(target, "yview_scroll"):
        target.yview_scroll(1, "units")
    return None


def _ensure_wheel_handlers(root: tk.Misc) -> None:
    global _wheel_handlers_installed
    if _wheel_handlers_installed:
        return
    _wheel_handlers_installed = True
    if sys.platform == "win32":
        root.bind_all("<MouseWheel>", _dispatch_wheel, add="+")
    else:
        root.bind_all("<Button-4>", _dispatch_wheel_up, add="+")
        root.bind_all("<Button-5>", _dispatch_wheel_down, add="+")


def reset_mousewheel_state_for_tests() -> None:
    global _wheel_handlers_installed
    _wheel_bindings.clear()
    _wheel_stack.clear()
    _wheel_handlers_installed = False


def bind_mousewheel(widget: tk.Misc, *, target: tk.Misc | None = None) -> None:
    """Scroll *target* while the pointer is over *widget* (nested binds use the latest enter)."""
    scroll_target = target or widget

    def on_enter(_event=None) -> None:
        widget_id = widget.winfo_id()
        _wheel_bindings[widget_id] = scroll_target
        if widget_id in _wheel_stack:
            _wheel_stack.remove(widget_id)
        _wheel_stack.append(widget_id)
        _ensure_wheel_handlers(widget.winfo_toplevel())

    def on_leave(_event=None) -> None:
        widget_id = widget.winfo_id()
        if _wheel_stack and _wheel_stack[-1] == widget_id:
            _wheel_stack.pop()
        elif widget_id in _wheel_stack:
            _wheel_stack.remove(widget_id)

    def on_destroy(_event=None) -> None:
        widget_id = widget.winfo_id()
        _wheel_bindings.pop(widget_id, None)
        if _wheel_stack and _wheel_stack[-1] == widget_id:
            _wheel_stack.pop()
        elif widget_id in _wheel_stack:
            _wheel_stack.remove(widget_id)

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")
    widget.bind("<Destroy>", on_destroy, add="+")


class HoverTooltip:
    """Small delayed popup shown while the pointer rests over a widget."""

    def __init__(self, widget: tk.Misc, text: str, *, delay_ms: int = 450) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tipwindow: tk.Toplevel | None = None
        self.after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._destroy, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel_schedule()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_schedule(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self) -> None:
        self.after_id = None
        if self.tipwindow or not self.text.strip():
            return
        try:
            if not self.widget.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            tip = tk.Toplevel(self.widget)
        except tk.TclError:
            return
        tip.wm_overrideredirect(True)
        tip.wm_attributes("-topmost", True)
        frame = tk.Frame(
            tip,
            bg=COLORS["fg"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        frame.pack()
        tk.Label(
            frame,
            text=self.text,
            justify="left",
            bg=COLORS["fg"],
            fg=COLORS["card"],
            font=FONT_SUBTITLE,
            wraplength=320,
            padx=8,
            pady=6,
        ).pack()
        tip.update_idletasks()
        screen_w = tip.winfo_screenwidth()
        if x + tip.winfo_width() > screen_w - 8:
            x = max(8, screen_w - tip.winfo_width() - 8)
        tip.wm_geometry(f"+{x}+{y}")
        self.tipwindow = tip

    def _hide(self, _event=None) -> None:
        self._cancel_schedule()
        if self.tipwindow is not None:
            self.tipwindow.destroy()
            self.tipwindow = None

    def _destroy(self, _event=None) -> None:
        self._cancel_schedule()
        self._hide()


def attach_hover_tooltip(widget: tk.Misc, text: str, *, delay_ms: int = 450) -> HoverTooltip:
    return HoverTooltip(widget, text, delay_ms=delay_ms)


def attach_combobox_tooltip(combobox: ttk.Combobox, text: str, *, delay_ms: int = 450) -> None:
    """Bind tooltip text to a combobox and its inner entry (Windows/clam often misses the outer widget)."""
    attach_hover_tooltip(combobox, text, delay_ms=delay_ms)
    combobox.update_idletasks()
    for child in combobox.winfo_children():
        attach_hover_tooltip(child, text, delay_ms=delay_ms)


def apply_ttk_style(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=[14, 8], font=FONT)
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["card"]), ("!selected", COLORS["secondary"])],
        foreground=[("selected", COLORS["primary"]), ("!selected", COLORS["muted"])],
    )
    style.configure("TCombobox", fieldbackground=COLORS["card"])


def card(parent, *, padx=16, pady=8):
    frame = tk.Frame(parent, bg=COLORS["card"], highlightbackground=COLORS["border"], highlightthickness=1)
    frame.pack(fill="x", padx=padx, pady=pady)
    return frame


def apply_app_icon(window: tk.Misc) -> None:
    """Set the Hive hex icon on this window and as the default for child dialogs."""
    from hive_planner.runtime_paths import app_icon_path

    icon = app_icon_path()
    if icon is None:
        return
    setter = getattr(window, "iconbitmap", None)
    if setter is None:
        return
    path = str(icon)
    try:
        setter(path)
    except tk.TclError:
        pass
    try:
        setter(default=path)
    except (tk.TclError, TypeError):
        pass


def card_title(parent, text: str) -> None:
    tk.Label(
        parent,
        text=text,
        font=FONT_BOLD,
        bg=COLORS["card"],
        fg=COLORS["fg"],
        anchor="w",
    ).pack(fill="x", padx=12, pady=(12, 6))


def primary_button(parent, text: str, command, *, tooltip: str | None = None) -> tk.Button:
    button = tk.Button(
        parent,
        text=text,
        command=command,
        font=FONT_BOLD,
        bg=COLORS["primary"],
        fg="white",
        activebackground=COLORS["primary_light"],
        activeforeground="white",
        relief="flat",
        padx=14,
        pady=8,
        cursor="hand2",
    )
    button.pack(side="left", padx=(0, 8), pady=4)
    if tooltip:
        attach_hover_tooltip(button, tooltip)
    return button


def secondary_button(parent, text: str, command, *, tooltip: str | None = None) -> tk.Button:
    button = tk.Button(
        parent,
        text=text,
        command=command,
        font=FONT,
        bg=COLORS["secondary"],
        fg=COLORS["fg"],
        activebackground=COLORS["border"],
        relief="flat",
        padx=12,
        pady=8,
        cursor="hand2",
    )
    button.pack(side="left", padx=(0, 8), pady=4)
    if tooltip:
        attach_hover_tooltip(button, tooltip)
    return button
