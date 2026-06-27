from __future__ import annotations

"""VoiceFlow-inspired palette (borrowed from KOKORO tts_overlay_unified.py)."""

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


def card_title(parent, text: str) -> None:
    tk.Label(
        parent,
        text=text,
        font=FONT_BOLD,
        bg=COLORS["card"],
        fg=COLORS["fg"],
        anchor="w",
    ).pack(fill="x", padx=12, pady=(12, 6))


def primary_button(parent, text: str, command) -> None:
    tk.Button(
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
    ).pack(side="left", padx=(0, 8), pady=4)


def secondary_button(parent, text: str, command) -> None:
    tk.Button(
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
    ).pack(side="left", padx=(0, 8), pady=4)
