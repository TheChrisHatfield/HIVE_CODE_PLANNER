"""Right-hand "HIVE Voice bot" panel for the launcher (visual shell).

Layout follows the reference mock: a header (back arrow, title, menu), a soft
green/grey orb with an assistant label and greeting, and a footer with a small
side button, a large green mic toggle, and an end-call button.

This module is presentation only. The mic and end-call buttons flip the visible
state and fire optional callbacks. Decisions (what a refusal says, which bridge
route ends a call) live in `voice_panel_controller.py`. This module starts no
audio and calls no bridge itself.
"""

from __future__ import annotations

import math
import tkinter as tk

from hive_planner.launcher.theme import COLORS, FONT_BOLD, FONT_SUBTITLE

PANEL_WIDTH = 230
PANEL_HEIGHT = 380
ORB_SIZE = 150
FRAME_MS = 40

GREETING = "Hey, What can I do for you today?"
LISTENING_GREETING = "Listening..."


def _blob_points(cx: float, cy: float, radius: float, phase: float, amp: float) -> list[float]:
    """Return a closed, wobbly ring of points for a smooth polygon."""
    points: list[float] = []
    steps = 16
    for i in range(steps):
        theta = 2 * math.pi * i / steps
        wobble = 1 + amp * math.sin(3 * theta + phase) + 0.5 * amp * math.sin(5 * theta - phase * 1.3)
        r = radius * wobble
        points.extend((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return points


class VoicePanel(tk.Frame):
    def __init__(
        self, master: tk.Misc, *, on_back=None, on_menu=None, on_end=None, on_mic=None, on_side=None,
        task_text=None,
    ) -> None:
        super().__init__(master, bg=COLORS["card"], width=PANEL_WIDTH, highlightbackground=COLORS["border"], highlightthickness=1)
        self._on_back = on_back
        self._on_menu = on_menu
        self._on_end = on_end
        # on_side() -> None. Opens the typed-instruction flow (slice 5b); the panel holds no logic.
        self._on_side = on_side
        # on_mic(start: bool) -> str | None. None = accepted; a string = refused and shown.
        self._on_mic = on_mic
        # task_text() -> str | None (slice 5e): label for the greeting slot while a typed task runs.
        self._task_text = task_text
        self._shown_task: str | None = None
        self._listening = False
        self._ending = False
        self._phase = 0.0
        self._after_id: str | None = None

        self._build_header()
        self._build_footer()
        self._build_body()
        self._lock_size()
        self._swallow_wheel()
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._animate()

    # --- construction -------------------------------------------------

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=COLORS["card"])
        header.pack(fill="x", padx=10, pady=(10, 4))
        back = tk.Label(header, text="\u2190", font=("Segoe UI", 12), bg=COLORS["card"], fg=COLORS["fg"])
        back.pack(side="left")
        self._bind_optional(back, self._on_back)
        menu = tk.Label(header, text="\u22ef", font=("Segoe UI", 12), bg=COLORS["card"], fg=COLORS["fg"])
        menu.pack(side="right")
        self._bind_optional(menu, self._on_menu)
        title = tk.Label(header, text="HIVE Voice bot", font=FONT_BOLD, bg=COLORS["card"], fg=COLORS["fg"])
        title.pack(side="left", padx=(8, 0))

    def _build_body(self) -> None:
        """Orb and copy sit in the cavity between header and footer (fill=y stretches this)."""
        body = tk.Frame(self, bg=COLORS["card"])
        body.pack(fill="both", expand=True)
        tk.Frame(body, bg=COLORS["card"]).pack(expand=True)
        self._orb = tk.Canvas(body, width=ORB_SIZE, height=ORB_SIZE, bg=COLORS["card"], highlightthickness=0)
        self._orb.pack(pady=(14, 0))
        self._sub = tk.Label(body, text="Your Assistant", font=FONT_SUBTITLE, bg=COLORS["card"], fg=COLORS["muted"])
        self._sub.pack(pady=(10, 2))
        self._greeting = tk.Label(
            body,
            text=GREETING,
            font=("Segoe UI", 12),
            bg=COLORS["card"],
            fg=COLORS["fg"],
            wraplength=PANEL_WIDTH - 40,
            justify="center",
        )
        self._greeting.pack(pady=(0, 10))
        tk.Frame(body, bg=COLORS["card"]).pack(expand=True)

    def _build_footer(self) -> None:
        footer = tk.Frame(self, bg=COLORS["card"])
        footer.pack(side="bottom", fill="x", pady=(0, 16))

        side = tk.Canvas(footer, width=34, height=34, bg=COLORS["card"], highlightthickness=0)
        side.pack(side="left", padx=(14, 0))
        side.create_rectangle(9, 9, 25, 25, outline=COLORS["muted"], width=2)
        side.create_line(13, 15, 21, 15, fill=COLORS["muted"], width=2)
        side.create_line(13, 19, 19, 19, fill=COLORS["muted"], width=2)
        self._side = side
        self._bind_optional(side, self._on_side)

        end = tk.Canvas(footer, width=34, height=34, bg=COLORS["card"], highlightthickness=0, cursor="hand2")
        end.pack(side="right", padx=(0, 14))
        end.create_oval(2, 2, 32, 32, fill=COLORS["error"], outline="", tags="bg")
        end.create_line(12, 12, 22, 22, fill="white", width=2, tags="glyph")
        end.create_line(22, 12, 12, 22, fill="white", width=2, tags="glyph")
        end.bind("<Button-1>", lambda _e: self._end_call())
        self._hangup = end

        # Pack hang-up before the expanding mic so Tk does not give the mic the
        # whole leftover cavity and clip the right-hand control.
        self._mic = tk.Canvas(footer, width=56, height=56, bg=COLORS["card"], highlightthickness=0, cursor="hand2")
        self._mic.pack(side="left", expand=True)
        self._mic.bind("<Button-1>", lambda _e: self._toggle_listening())
        self._draw_mic()

    def _swallow_wheel(self) -> None:
        """Stop the launcher's bind-all wheel from scrolling the dashboard through this column."""

        def stop(_event=None) -> str:
            return "break"

        def bind_tree(widget: tk.Misc) -> None:
            widget.bind("<MouseWheel>", stop, add="+")
            widget.bind("<Button-4>", stop, add="+")
            widget.bind("<Button-5>", stop, add="+")
            for child in widget.winfo_children():
                bind_tree(child)

        bind_tree(self)

    def _lock_size(self) -> None:
        """Keep a fixed width and a content-sized height; fill=y may still stretch."""
        try:
            self.update_idletasks()
            height = max(int(self.winfo_reqheight()), PANEL_HEIGHT)
        except tk.TclError:
            height = PANEL_HEIGHT
        try:
            self.configure(width=PANEL_WIDTH, height=height)
            self.pack_propagate(False)
        except tk.TclError:
            pass

    # --- state ---------------------------------------------------------

    def _alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _toggle_listening(self) -> None:
        if self._ending or not self._alive():
            return
        previous = self._listening
        self._listening = not previous
        if callable(self._on_mic):
            refusal = self._on_mic(self._listening)
            if refusal:
                # Refused start: keep the previous (off) state. A refused stop still means the
                # recorder is off, so it must not flip back to "listening". Show why either way.
                if self._listening:
                    self._listening = previous
                self._refresh_visible_state()
                self.show_message(str(refusal))
                return
        if not self._refresh_visible_state():
            self._listening = previous
            self._refresh_visible_state()

    def show_message(self, text: str) -> None:
        """Show a one-line status in the greeting slot. The next state change restores the greeting."""
        try:
            if self._alive():
                self._greeting.configure(text=text)
        except tk.TclError:
            pass

    def _end_call(self) -> None:
        if self._ending:
            return
        self._ending = True
        try:
            self._listening = False
            if not self._alive():
                return
            self._refresh_visible_state()
            try:
                self._fire(self._on_end)
            except tk.TclError:
                pass
            self._listening = False
            if self._alive():
                self._refresh_visible_state()
        finally:
            self._ending = False

    def _refresh_visible_state(self) -> bool:
        try:
            if not self._alive():
                return False
            self._greeting.configure(text=LISTENING_GREETING if self._listening else (self._shown_task or GREETING))
            self._draw_mic()
            return True
        except tk.TclError:
            return False

    def _sync_task_text(self) -> None:
        """Slice 5e: follow the task label. It changes only on a real change, so a refusal message stays up."""
        if self._listening or not callable(self._task_text):
            return
        text = self._task_text()
        if text == self._shown_task:
            return
        self._shown_task = text
        try:
            self._greeting.configure(text=text or GREETING)
        except tk.TclError:
            pass

    @property
    def listening(self) -> bool:
        return self._listening

    def _draw_mic(self) -> None:
        c = self._mic
        c.delete("all")
        fill = COLORS["primary_light"] if self._listening else COLORS["primary"]
        c.create_oval(2, 2, 54, 54, fill=fill, outline="", tags="bg")
        if self._listening:
            c.create_oval(5, 5, 51, 51, outline="white", width=2, tags="listen-ring")
        # Narrow capsule + U cradle + stem (a block+shallow-arc reads as a chair).
        c.create_oval(24, 11, 32, 19, fill="white", outline="white", tags="capsule")
        c.create_rectangle(24, 15, 32, 27, fill="white", outline="white", tags="capsule")
        c.create_oval(24, 23, 32, 31, fill="white", outline="white", tags="capsule")
        c.create_arc(18, 16, 38, 38, start=180, extent=180, style="arc", outline="white", width=2, tags="cradle")
        c.create_line(28, 38, 28, 43, fill="white", width=2, tags="stem")
        c.create_line(22, 43, 34, 43, fill="white", width=2, tags="stem")

    @staticmethod
    def _fire(callback) -> None:
        if callable(callback):
            callback()

    @staticmethod
    def _bind_optional(widget: tk.Misc, callback) -> None:
        if not callable(callback):
            return
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda _e: callback())

    # --- animation -----------------------------------------------------

    def _cancel_animation(self) -> None:
        if self._after_id is None:
            return
        try:
            self.after_cancel(self._after_id)
        except tk.TclError:
            pass
        self._after_id = None

    def _schedule_frame(self) -> None:
        self._cancel_animation()
        try:
            self._after_id = self.after(FRAME_MS, self._animate)
        except tk.TclError:
            self._after_id = None

    def _animate(self) -> None:
        if not self._alive():
            self._cancel_animation()
            return
        self._phase += 0.22 if self._listening else 0.08
        try:
            self._sync_task_text()
        except tk.TclError:
            pass
        try:
            if self.winfo_viewable():
                self._draw_orb()
        except tk.TclError:
            pass
        self._schedule_frame()

    def _draw_orb(self) -> None:
        c = self._orb
        c.delete("all")
        cx = cy = ORB_SIZE / 2
        amp = 0.09 if self._listening else 0.05
        breathe = 1 + 0.04 * math.sin(self._phase)

        base = ORB_SIZE * 0.40 * breathe
        c.create_polygon(
            _blob_points(cx, cy, base, self._phase, amp),
            smooth=True, fill="#c9ccd2", outline="",
        )
        c.create_polygon(
            _blob_points(cx - 10, cy - 8, base * 0.78, self._phase * 1.3 + 1.0, amp),
            smooth=True, fill=COLORS["primary_light"], outline="",
        )
        c.create_polygon(
            _blob_points(cx + 8, cy + 6, base * 0.52, self._phase * 0.9 + 2.0, amp),
            smooth=True, fill="#9ca3af", outline="",
        )
        c.create_polygon(
            _blob_points(cx - 14, cy - 14, base * 0.26, self._phase * 1.1, amp),
            smooth=True, fill="#eef2f0", outline="",
        )

    def _on_destroy(self, event=None) -> None:
        if event is not None:
            try:
                widget = event.widget
                if widget is not None and str(widget) != str(self):
                    return
            except tk.TclError:
                pass
        self._listening = False
        self._cancel_animation()
