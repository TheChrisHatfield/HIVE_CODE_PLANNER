from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from hive_planner.launcher.config import LauncherConfig, linked_project_exists, load_config, normalize_project_path, save_config
from hive_planner.launcher.service import (
    CursorWorkspace,
    classify_workspace,
    discover_cursor_workspaces,
    discover_python_installations,
    format_python_scan_report,
    get_setup_status,
    is_code_workspace_file,
    open_in_cursor,
    open_path_in_explorer,
    pick_hive_bootstrap_target,
    prepare_linked_project_root,
    resolve_linked_project_root,
    run_deploy_agent_handoff,
    run_install,
    run_project_ci_check,
    run_project_init,
    run_project_map_sync,
    summarize_linked_project,
    summarize_project,
    workspace_primary_folder,
)
from hive_planner.launcher.theme import (
    COLORS,
    FONT,
    FONT_BOLD,
    FONT_SUBTITLE,
    FONT_TITLE,
    apply_ttk_style,
    card,
    card_title,
    primary_button,
    secondary_button,
    bind_mousewheel,
)
from hive_planner.launcher import console_win
from hive_planner.launcher.user_guide import load_user_guide, user_guide_path
from hive_planner.project_profile import read_project_profile


def format_recent_project_label(path: str, profile: str | None = None, *, active: bool = False) -> str:
    entry = Path(path)
    if is_code_workspace_file(entry):
        folder = f"{entry.stem} (Workspace)"
    else:
        folder = entry.name or path
    if profile:
        label = f"{folder}  [{profile}]"
    else:
        label = folder
    if active:
        return f"{label}  ← active"
    return label


def format_workspace_picker_label(workspace: CursorWorkspace) -> str:
    location = workspace.location
    if not workspace.exists:
        return f"{workspace.name}  ·  {location}  ·  missing"
    return f"{workspace.name}  ·  {location}"


def format_linked_workspace_label(path: str, profile: str | None = None, *, active: bool = False) -> str:
    ws = classify_workspace(Path(path))
    if ws.exists:
        base = f"{ws.name}  ·  {ws.location}"
    else:
        base = f"{_linked_display_name(path)}  ·  missing"
    if profile and ws.exists:
        base = f"{ws.name}  [{profile}]  ·  {ws.location}"
    if active:
        return f"{base}  ← active"
    return base


def _linked_path_exists(path: str) -> bool:
    return linked_project_exists(path)


def _linked_display_name(path: str) -> str:
    entry = Path(path)
    if is_code_workspace_file(entry):
        return f"{entry.stem} (Workspace)"
    return entry.name or path


class HivePlannerApp:
    RECENT_LIST_MIN_ROWS = 2
    RECENT_LIST_MAX_ROWS = 4

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = load_config()
        self.setup = get_setup_status(self.config)
        self._wizard_step = 0
        self._bg_generation = 0
        self._python_scan_active = False

        root.title("Hive Planner")
        root.geometry("920x680")
        root.minsize(780, 580)
        root.configure(bg=COLORS["bg"])
        apply_ttk_style(root)

        self.container = tk.Frame(root, bg=COLORS["bg"])
        self.container.pack(fill="both", expand=True)

        if not self.config.onboarding_complete:
            self._show_onboarding()
        else:
            self._show_dashboard()

    def _clear_container(self) -> None:
        self._invalidate_bg_callbacks()
        for child in self.container.winfo_children():
            child.destroy()

    def _run_bg(self, work, on_done) -> None:
        generation = self._bg_generation

        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001 — surface in UI log
                result = {"ok": False, "error": str(exc)}

            def finish() -> None:
                if generation != self._bg_generation:
                    if self._python_scan_active:
                        self._python_scan_active = False
                        try:
                            self._hide_python_scan_progress()
                        except tk.TclError:
                            pass
                    return
                try:
                    on_done(result)
                except tk.TclError:
                    return

            self.root.after(0, finish)

        threading.Thread(target=runner, daemon=True).start()

    def _invalidate_bg_callbacks(self) -> None:
        self._bg_generation += 1
        self._python_scan_active = False
        self._hide_python_scan_progress()

    def _show_onboarding(self) -> None:
        self._clear_container()
        wrapper = tk.Frame(self.container, bg=COLORS["bg"])
        wrapper.pack(fill="both", expand=True, padx=32, pady=24)

        tk.Label(
            wrapper,
            text="Hive Planner",
            font=FONT_TITLE,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        ).pack(anchor="w")
        tk.Label(
            wrapper,
            text="Local planning control for Cursor — no browser required.",
            font=FONT_SUBTITLE,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(anchor="w", pady=(0, 16))

        steps = tk.Frame(wrapper, bg=COLORS["bg"])
        steps.pack(fill="x", pady=(0, 12))
        for i, label in enumerate(["Welcome", "Setup", "Paths", "Ready"], start=1):
            color = COLORS["primary"] if i - 1 <= self._wizard_step else COLORS["muted"]
            tk.Label(steps, text=f" {i} {label} ", font=FONT_BOLD, bg=color, fg="white" if i - 1 <= self._wizard_step else COLORS["fg"]).pack(
                side="left", padx=4
            )

        body = tk.Frame(wrapper, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)
        actions = tk.Frame(wrapper, bg=COLORS["bg"])
        actions.pack(fill="x", pady=(12, 0))

        if self._wizard_step == 0:
            intro = card(body)
            card_title(intro, "What you get")
            tk.Label(
                intro,
                text="• Bootstrap Hive projects with Delta planning layout\n"
                "• Unified agent handoff: Spec Kit + Continual Learning (symbiotic)\n"
                "• Run ci-check health gates before handoff\n"
                "• Sync impact maps and open projects in Cursor",
                justify="left",
                font=FONT,
                bg=COLORS["card"],
                fg=COLORS["muted"],
            ).pack(anchor="w", padx=12, pady=(0, 12))
            if self.setup.python_ok and self.setup.hive_installed and self.setup.hive_root_ok:
                primary_button(actions, "Open dashboard →", self._finish_onboarding)
            else:
                primary_button(actions, "Get started →", lambda: self._advance_wizard(1))
        elif self._wizard_step == 1:
            self.setup = get_setup_status(self.config)
            status_card = card(body)
            card_title(status_card, "Environment")
            for label, ok, detail in [
                ("Python", self.setup.python_ok, self.setup.python_version),
                ("Hive installed", self.setup.hive_installed, self.setup.hive_version or "missing"),
                ("Git", self.setup.git_available, "available" if self.setup.git_available else "optional"),
            ]:
                row = tk.Frame(status_card, bg=COLORS["card"])
                row.pack(fill="x", padx=12, pady=4)
                tk.Label(row, text=label, width=16, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
                badge = COLORS["success"] if ok else COLORS["warning"]
                tk.Label(row, text=detail, bg=COLORS["card"], fg=badge, font=FONT_BOLD).pack(side="left")
            secondary_button(actions, "← Back", lambda: self._advance_wizard(0))
            secondary_button(actions, "Scan for Python", self._on_scan_python)
            secondary_button(actions, "Install / update", self._on_install)
            if self.setup.python_ok and self.setup.hive_installed and self.setup.hive_root_ok:
                primary_button(actions, "Open dashboard →", self._finish_onboarding)
            else:
                primary_button(actions, "Continue →", lambda: self._advance_wizard(2))
        elif self._wizard_step == 2:
            paths_card = card(body)
            card_title(paths_card, "Paths")
            self._hive_root_var = tk.StringVar(value=str(self.config.normalized_hive_root()))
            self._python_var = tk.StringVar(value=self.config.python_executable)
            self._field(paths_card, "Hive planner root", self._hive_root_var, browse=True)
            self._field(paths_card, "Python command", self._python_var, scan_python=True)
            secondary_button(actions, "← Back", lambda: self._advance_wizard(1))
            primary_button(actions, "Continue →", self._save_wizard_paths)
        else:
            done = card(body)
            card_title(done, "Ready")
            tk.Label(
                done,
                text="Open the dashboard to create projects, run health checks, and manage settings.",
                wraplength=640,
                justify="left",
                bg=COLORS["card"],
                fg=COLORS["muted"],
                font=FONT,
            ).pack(anchor="w", padx=12, pady=(0, 12))
            primary_button(actions, "Open dashboard", self._finish_onboarding)

    def _advance_wizard(self, step: int) -> None:
        self._wizard_step = step
        self._show_onboarding()

    def _save_wizard_paths(self) -> None:
        self.config.hive_planner_root = self._hive_root_var.get().strip()
        self.config.python_executable = self._python_var.get().strip() or "py -3.11"
        save_config(self.config)
        self._advance_wizard(3)

    def _finish_onboarding(self) -> None:
        self.config.onboarding_complete = True
        save_config(self.config)
        self._show_dashboard()

    def _show_dashboard(self) -> None:
        self._clear_container()
        self.config = load_config()
        self.setup = get_setup_status(self.config)

        header = tk.Frame(self.container, bg=COLORS["bg"])
        header.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(header, text="Hive Planner", font=FONT_TITLE, bg=COLORS["bg"], fg=COLORS["fg"]).pack(side="left")
        proj = self.config.active_project
        if proj:
            proj_label = _linked_display_name(proj)
            profile_label = self._active_profile_label()
            header_detail = (
                f"Active: {proj_label}  ·  profile: {profile_label}"
                if profile_label
                else f"Active: {proj_label}"
            )
        else:
            header_detail = "No project selected"
        tk.Label(header, text=header_detail, font=FONT_SUBTITLE, bg=COLORS["bg"], fg=COLORS["muted"]).pack(
            side="right", padx=8
        )

        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True, padx=16, pady=8)

        home = tk.Frame(notebook, bg=COLORS["bg"])
        projects = tk.Frame(notebook, bg=COLORS["bg"])
        settings = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(home, text="Home")
        notebook.add(projects, text="Projects")
        notebook.add(settings, text="Settings")

        self._build_home_tab(home)
        self._build_projects_tab(projects)
        self._build_settings_tab(settings)

    def _scrollable_tab(self, parent: tk.Frame) -> tuple[tk.Frame, tk.Canvas]:
        canvas = tk.Canvas(parent, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        bind_mousewheel(scrollbar, target=canvas)
        inner = tk.Frame(canvas, bg=COLORS["bg"])
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _sync_scroll(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_width(event) -> None:
            canvas.itemconfig(window_id, width=event.width)

        inner.bind("<Configure>", _sync_scroll)
        canvas.bind("<Configure>", _sync_width)
        return inner, canvas

    _PAGE_WHEEL_SKIP = (tk.Listbox, tk.Text)

    def _bind_page_wheel(self, parent: tk.Misc, canvas: tk.Canvas) -> None:
        bind_mousewheel(canvas, target=canvas)
        self._bind_page_wheel_children(parent, canvas)

    def _bind_page_wheel_children(self, parent: tk.Misc, canvas: tk.Canvas) -> None:
        for child in parent.winfo_children():
            if isinstance(child, self._PAGE_WHEEL_SKIP):
                continue
            bind_mousewheel(child, target=canvas)
            self._bind_page_wheel_children(child, canvas)

    def _build_home_tab(self, parent: tk.Frame) -> None:
        body, canvas = self._scrollable_tab(parent)

        guide_card = card(body)
        card_title(guide_card, "How to use Hive Planner")
        tk.Label(
            guide_card,
            text="Plain-English guide — what this tool is and how to use it. Scroll to read.",
            wraplength=760,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
        ).pack(anchor="w", padx=12, pady=(0, 6))
        self.home_guide = scrolledtext.ScrolledText(
            guide_card,
            height=16,
            font=FONT,
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
            wrap="word",
        )
        self.home_guide.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.home_guide.insert("1.0", load_user_guide(self.config))
        self.home_guide.configure(state="disabled")
        bind_mousewheel(self.home_guide)
        guide_actions = tk.Frame(guide_card, bg=COLORS["card"])
        guide_actions.pack(fill="x", padx=12, pady=(0, 12))
        secondary_button(guide_actions, "Open guide in Explorer", self._on_open_user_guide)
        secondary_button(guide_actions, "Run setup wizard", self._on_reset_onboarding)

        stats = card(body)
        card_title(stats, "Status")
        row = tk.Frame(stats, bg=COLORS["card"])
        row.pack(fill="x", padx=12, pady=(0, 12))
        for title, value in [
            ("Hive", self.setup.hive_version or "not installed"),
            ("Profile", self._active_profile_label() or "—"),
            ("Handoff", self._active_handoff_label()),
            ("Feature", self._active_feature_label()),
        ]:
            cell = tk.Frame(row, bg=COLORS["secondary"], padx=12, pady=10)
            cell.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(cell, text=value, font=("Segoe UI", 14, "bold"), bg=COLORS["secondary"], fg=COLORS["primary"]).pack()
            tk.Label(cell, text=title, font=FONT_SUBTITLE, bg=COLORS["secondary"], fg=COLORS["muted"]).pack()

        actions = tk.Frame(body, bg=COLORS["bg"])
        actions.pack(fill="x", padx=16, pady=8)
        primary_button(actions, "Run health check", self._on_ci_check)
        secondary_button(actions, "Open in Cursor", self._on_open_cursor)
        secondary_button(actions, "Sync impact maps", self._on_map_sync)
        secondary_button(actions, "Deploy agent handoff", self._on_deploy_agent_handoff)
        secondary_button(actions, "Open in Explorer", self._on_explore)

        log_card = card(body)
        card_title(log_card, "Output")
        self.home_log = scrolledtext.ScrolledText(
            log_card,
            height=10,
            font=("Consolas", 9),
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
            wrap="word",
        )
        self.home_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.home_log.configure(state="disabled")
        bind_mousewheel(self.home_log)

        check_card = card(body)
        card_title(check_card, "Latest ci-check")
        self.ci_list = tk.Listbox(check_card, height=6, font=FONT, bg=COLORS["card"], fg=COLORS["fg"], relief="flat")
        self.ci_list.pack(fill="x", padx=12, pady=(0, 12))
        bind_mousewheel(self.ci_list)
        self._bind_page_wheel(body, canvas)

    def _build_projects_tab(self, parent: tk.Frame) -> None:
        top_row = tk.Frame(parent, bg=COLORS["bg"])
        top_row.pack(fill="x")
        top_row.columnconfigure(0, weight=1)
        top_row.columnconfigure(1, weight=1)

        hub_host = tk.Frame(top_row, bg=COLORS["bg"])
        hub_host.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form_host = tk.Frame(top_row, bg=COLORS["bg"])
        form_host.grid(row=0, column=1, sticky="nsew")

        hub = card(hub_host)
        card_title(hub, "Cursor workspace hub")
        tk.Label(
            hub,
            text="Link a Cursor workspace to Hive Planner, then use Open in Cursor to launch it. "
            "Health checks run when Hive planning files are present.",
            wraplength=360,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", padx=12, pady=(0, 8))
        hub_actions = tk.Frame(hub, bg=COLORS["card"])
        hub_actions.pack(fill="x", padx=12, pady=(0, 12))
        primary_button(hub_actions, "Open in Cursor", self._on_open_cursor)
        secondary_button(hub_actions, "Add link…", self._on_link_workspace)

        form = card(form_host)
        card_title(form, "New project")
        self.new_name = tk.StringVar()
        self.new_target = tk.StringVar()
        self.new_profile = tk.StringVar(value=self.config.default_profile)
        self.new_git = tk.BooleanVar(value=True)
        self.new_agent_handoff = tk.StringVar(value="unified")
        self._field(form, "Project name", self.new_name)
        self._field(form, "Target folder", self.new_target, browse=True)
        profile_row = tk.Frame(form, bg=COLORS["card"])
        profile_row.pack(fill="x", padx=12, pady=4)
        tk.Label(profile_row, text="Profile", width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
        ttk.Combobox(
            profile_row,
            textvariable=self.new_profile,
            values=["full", "minimal"],
            state="readonly",
            width=28,
        ).pack(side="left", fill="x", expand=True)
        handoff_row = tk.Frame(form, bg=COLORS["card"])
        handoff_row.pack(fill="x", padx=12, pady=(4, 4))
        tk.Label(
            handoff_row,
            text="Agent handoff",
            width=14,
            anchor="w",
            bg=COLORS["card"],
            fg=COLORS["fg"],
            font=FONT,
        ).pack(side="left")
        ttk.Combobox(
            handoff_row,
            textvariable=self.new_agent_handoff,
            values=["unified", "off"],
            state="readonly",
            width=28,
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            handoff_row,
            text="Unified = Spec Kit + Continual Learning together",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
        ).pack(anchor="w", padx=(14, 0), pady=(2, 0))
        git_row = tk.Frame(form, bg=COLORS["card"])
        git_row.pack(fill="x", padx=12, pady=(4, 12))
        tk.Checkbutton(
            git_row,
            text="Git init",
            variable=self.new_git,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            activebackground=COLORS["card"],
            font=FONT,
        ).pack(anchor="w")
        btn_row = tk.Frame(form, bg=COLORS["card"])
        btn_row.pack(fill="x", padx=12, pady=(0, 12))
        primary_button(btn_row, "Create project", self._on_create_project)

        recent_card = card(parent)
        card_title(recent_card, "Linked workspaces")
        tk.Label(
            recent_card,
            text="Hive Planner only — add or remove links here without changing Cursor.",
            wraplength=760,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
        ).pack(anchor="w", padx=12, pady=(0, 8))
        recent_list_frame = tk.Frame(recent_card, bg=COLORS["card"])
        recent_list_frame.pack(fill="x", padx=12, pady=(0, 8))
        self.recent_scroll = ttk.Scrollbar(recent_list_frame, orient="vertical")
        self.recent_list = tk.Listbox(
            recent_list_frame,
            height=self.RECENT_LIST_MIN_ROWS,
            font=FONT,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            selectbackground=COLORS["primary"],
            selectforeground="white",
            activestyle="none",
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["primary"],
        )
        self.recent_list.pack(side="left", fill="x", expand=True)
        self.recent_scroll.config(command=self.recent_list.yview)
        self.recent_list.bind("<Double-Button-1>", self._on_recent_double_click)
        bind_mousewheel(self.recent_scroll, target=self.recent_list)
        bind_mousewheel(recent_list_frame, target=self.recent_list)
        bind_mousewheel(self.recent_list)
        self._recent_project_paths: list[str] = []
        self._populate_recent_list()
        btn_row2 = tk.Frame(recent_card, bg=COLORS["card"])
        btn_row2.pack(fill="x", padx=12, pady=(0, 12))
        primary_button(btn_row2, "Add link…", self._on_link_workspace)
        secondary_button(btn_row2, "Set as active", self._on_select_recent)
        secondary_button(btn_row2, "Remove link", self._on_remove_recent)
        secondary_button(btn_row2, "Delete profile…", self._on_delete_profile)

    def _build_settings_tab(self, parent: tk.Frame) -> None:
        form = card(parent)
        card_title(form, "Configuration")
        self.cfg_hive = tk.StringVar(value=str(self.config.normalized_hive_root()))
        self.cfg_python = tk.StringVar(value=self.config.python_executable)
        self.cfg_cursor = tk.StringVar(value=self.config.cursor_executable)
        self.cfg_profile = tk.StringVar(value=self.config.default_profile)
        self._field(form, "Hive planner root", self.cfg_hive, browse=True)
        self._field(form, "Python command", self.cfg_python, scan_python=True)
        self._field(form, "Cursor executable", self.cfg_cursor, browse_exe=True)
        profile_row = tk.Frame(form, bg=COLORS["card"])
        profile_row.pack(fill="x", padx=12, pady=4)
        tk.Label(profile_row, text="Default profile", width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
        ttk.Combobox(profile_row, textvariable=self.cfg_profile, values=["full", "minimal"], state="readonly", width=28).pack(
            side="left", fill="x", expand=True
        )
        btn_row = tk.Frame(form, bg=COLORS["card"])
        btn_row.pack(fill="x", padx=12, pady=(8, 12))
        primary_button(btn_row, "Save settings", self._on_save_settings)
        secondary_button(btn_row, "Install / update Hive", self._on_install)
        secondary_button(btn_row, "Reset onboarding", self._on_reset_onboarding)
        if console_win.console_available():
            self.console_btn = tk.Button(
                btn_row,
                text="Show console",
                command=self._on_toggle_console,
                font=FONT,
                bg=COLORS["secondary"],
                fg=COLORS["fg"],
                activebackground=COLORS["border"],
                relief="flat",
                padx=12,
                pady=8,
                cursor="hand2",
            )
            self.console_btn.pack(side="left", padx=(0, 8), pady=4)
            if console_win.is_console_visible():
                self.console_btn.config(text="Hide console")

        tip = card(parent)
        card_title(tip, "Pro tip")
        tk.Label(
            tip,
            text="Run health check before every handoff. Green ci-check means Delta, spec, and impact maps align.",
            wraplength=760,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", padx=12, pady=(0, 12))

    def _field(
        self,
        parent,
        label: str,
        variable: tk.StringVar,
        *,
        browse: bool = False,
        browse_exe: bool = False,
        scan_python: bool = False,
    ) -> None:
        row = tk.Frame(parent, bg=COLORS["card"])
        row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text=label, width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
        entry = tk.Entry(row, textvariable=variable, font=FONT, bg=COLORS["card"], fg=COLORS["fg"], relief="solid", bd=1)
        entry.pack(side="left", fill="x", expand=True)
        if browse:
            secondary_button(row, "Browse…", lambda: self._browse_into(variable))
        if browse_exe:
            secondary_button(row, "Browse…", lambda: self._browse_exe_into(variable))
        if scan_python:
            secondary_button(row, "Scan…", lambda: self._on_scan_python(variable))

    def _browse_exe_into(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Choose Cursor executable",
            filetypes=[("Cursor", "Cursor.exe"), ("Executables", "*.exe"), ("All files", "*.*")],
        )
        if path:
            variable.set(path)

    def _browse_into(self, variable: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Choose folder")
        if path:
            variable.set(path)

    def _populate_recent_list(self) -> None:
        self.recent_list.delete(0, "end")
        self._recent_project_paths.clear()
        active_norm = (
            normalize_project_path(self.config.active_project)
            if self.config.active_project
            else ""
        )
        active_index: int | None = None
        for path in self.config.recent_projects:
            hive_root = resolve_linked_project_root(Path(path))
            stored = read_project_profile(hive_root) if hive_root else None
            cached = self.config.project_profiles.get(path) or self.config.project_profiles.get(
                normalize_project_path(path)
            )
            profile = stored.bootstrap_profile if stored else cached
            is_active = bool(active_norm and normalize_project_path(path) == active_norm)
            label = format_linked_workspace_label(
                path,
                profile,
                active=is_active,
            )
            if is_active:
                active_index = len(self._recent_project_paths)
            self._recent_project_paths.append(path)
            self.recent_list.insert("end", label)
        self._update_recent_scrollbar()
        if active_index is not None:
            self.recent_list.selection_set(active_index)
            self.recent_list.see(active_index)

    def _update_recent_scrollbar(self) -> None:
        count = self.recent_list.size()
        display_height = min(
            max(count, self.RECENT_LIST_MIN_ROWS),
            self.RECENT_LIST_MAX_ROWS,
        )
        self.recent_list.configure(height=display_height)
        if count > display_height:
            if not self.recent_scroll.winfo_ismapped():
                self.recent_scroll.pack(side="right", fill="y")
            self.recent_list.configure(yscrollcommand=self.recent_scroll.set)
        else:
            self.recent_scroll.pack_forget()
            self.recent_list.configure(yscrollcommand=lambda *_args: None)
            self.recent_list.yview_moveto(0)

    def _selected_recent_path(self) -> Path | None:
        selection = self.recent_list.curselection()
        if not selection:
            return None
        return Path(self._recent_project_paths[selection[0]])

    def _active_handoff_label(self) -> str:
        if not self.config.active_project:
            return "—"
        from hive_planner.agent_handoff import validate_unified_handoff

        root, _repair = prepare_linked_project_root(Path(self.config.active_project), repair_agents=False)
        if not root:
            return "—"
        status = validate_unified_handoff(root)
        if status.mode == "unified":
            return "unified ✓" if status.complete else "unified (incomplete)"
        return "off"

    def _active_feature_label(self) -> str:
        if not self.config.active_project:
            return "—"
        summary = summarize_linked_project(Path(self.config.active_project))
        if not summary.ok:
            return "—"
        return summary.active_feature or "—"

    def _active_profile_label(self) -> str:
        if not self.config.active_project:
            return "—"
        root, _repair = prepare_linked_project_root(Path(self.config.active_project))
        if not root:
            return ""
        stored = read_project_profile(root)
        if stored:
            return stored.bootstrap_profile
        cached = self.config.project_profiles.get(self.config.active_project)
        if cached:
            return cached
        normalized = normalize_project_path(self.config.active_project)
        return self.config.project_profiles.get(normalized) or ""

    def _append_log(self, widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.configure(state="normal")
        widget.insert("end", text.rstrip() + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _on_install(self) -> None:
        self._run_bg(lambda: run_install(load_config()), self._install_done)

    def _on_scan_python(self, target_var: tk.StringVar | None = None) -> None:
        if self._python_scan_active:
            return
        self._python_scan_active = True
        self._python_scan_target = target_var
        self._show_python_scan_progress()

        def work():
            def on_progress(current: int, total: int, message: str) -> None:
                self.root.after(
                    0,
                    lambda c=current, t=total, m=message: self._update_python_scan_progress(c, t, m),
                )

            return discover_python_installations(on_progress=on_progress)

        self._run_bg(work, self._python_scan_done)

    def _show_python_scan_progress(self) -> None:
        self._hide_python_scan_progress()
        dialog = tk.Toplevel(self.root)
        dialog.title("Scanning for Python")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.geometry("440x130")
        self._python_scan_dialog = dialog

        tk.Label(
            dialog,
            text="Scanning for Python installations",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT_BOLD,
        ).pack(anchor="w", padx=16, pady=(16, 4))

        self._python_scan_status = tk.StringVar(value="Starting scan…")
        tk.Label(
            dialog,
            textvariable=self._python_scan_status,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
            wraplength=400,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        self._python_scan_bar = ttk.Progressbar(dialog, mode="determinate", maximum=100, length=400)
        self._python_scan_bar.pack(padx=16, pady=(0, 16))
        self._python_scan_bar["value"] = 0

    def _update_python_scan_progress(self, current: int, total: int, message: str) -> None:
        dialog = getattr(self, "_python_scan_dialog", None)
        if dialog is None:
            return
        try:
            if not dialog.winfo_exists():
                return
        except tk.TclError:
            return

        if message == "Collecting candidates":
            self._python_scan_status.set("Collecting Python locations…")
            self._python_scan_bar["value"] = 5
            return
        if message == "Done":
            self._python_scan_status.set("Finishing scan…")
            self._python_scan_bar["value"] = 100
            return

        safe_total = max(total, 1)
        pct = min(99, int(((current + 1) / safe_total) * 100))
        self._python_scan_bar["value"] = pct
        self._python_scan_status.set(f"Checking {message} ({current + 1}/{safe_total})…")

    def _hide_python_scan_progress(self) -> None:
        dialog = getattr(self, "_python_scan_dialog", None)
        if dialog is not None:
            try:
                if dialog.winfo_exists():
                    dialog.grab_release()
                    dialog.destroy()
            except tk.TclError:
                pass
        self._python_scan_dialog = None

    def _python_scan_done(self, result) -> None:
        self._python_scan_active = False
        self._hide_python_scan_progress()
        if self._is_bg_error(result):
            messagebox.showerror("Python scan failed", self._result_detail(result))
            return
        installations = result if isinstance(result, list) else []
        target_var = getattr(self, "_python_scan_target", None)
        self._show_python_scan_results(installations, target_var)

    def _show_python_scan_results(self, installations, target_var: tk.StringVar | None) -> None:
        if not installations:
            messagebox.showwarning("Python scan", format_python_scan_report([]))
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Python installations")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("640x360")

        tk.Label(
            dialog,
            text="Select a Python to use for pip install and Hive commands.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
            wraplength=600,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(16, 8))

        list_frame = tk.Frame(dialog, bg=COLORS["bg"])
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)
        picker = tk.Listbox(
            list_frame,
            height=10,
            font=FONT,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            relief="flat",
            activestyle="dotbox",
        )
        picker.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(list_frame, command=picker.yview)
        scroll.pack(side="right", fill="y")
        picker.configure(yscrollcommand=scroll.set)
        bind_mousewheel(scroll, target=picker)
        bind_mousewheel(list_frame, target=picker)
        bind_mousewheel(picker)

        default_index = 0
        supported = [i for i, inst in enumerate(installations) if inst.supported]
        if supported:
            default_index = supported[0]
        for index, inst in enumerate(installations):
            status = "OK" if inst.supported else "old"
            label = f"{status}  {inst.version}  —  {inst.command}"
            picker.insert("end", label)
        picker.selection_set(default_index)
        picker.activate(default_index)

        report = scrolledtext.ScrolledText(
            dialog,
            height=5,
            font=("Consolas", 9),
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
            wrap="word",
        )
        report.pack(fill="x", padx=16, pady=(0, 8))
        report.insert("end", format_python_scan_report(installations))
        report.configure(state="disabled")
        bind_mousewheel(report)

        actions = tk.Frame(dialog, bg=COLORS["bg"])
        actions.pack(fill="x", padx=16, pady=(0, 16))

        def apply_selection() -> None:
            selection = picker.curselection()
            if not selection:
                messagebox.showwarning("No selection", "Pick a Python installation.", parent=dialog)
                return
            inst = installations[selection[0]]
            if not inst.supported:
                if not messagebox.askyesno(
                    "Python too old",
                    f"Python {inst.version} is older than 3.10.\n\nUse it anyway?",
                    parent=dialog,
                ):
                    return
            if target_var is not None:
                target_var.set(inst.command)
            else:
                self.config.python_executable = inst.command
                save_config(self.config)
                self.setup = get_setup_status(self.config)
            dialog.destroy()
            if target_var is None and not self.config.onboarding_complete:
                self._show_onboarding()

        primary_button(actions, "Use selected", apply_selection)
        secondary_button(actions, "Close", dialog.destroy)

    def _is_bg_error(self, result) -> bool:
        """True only for _run_bg exception wrappers, not ci-check/map-sync payloads."""
        return isinstance(result, dict) and bool(result.get("error"))

    def _result_failed(self, result) -> bool:
        if isinstance(result, dict):
            return result.get("ok") is False or bool(result.get("error"))
        return not getattr(result, "ok", True)

    def _result_detail(self, result) -> str:
        if isinstance(result, dict):
            return str(result.get("error") or result.get("detail") or result)
        return str(getattr(result, "detail", result))

    def _install_done(self, result) -> None:
        detail = self._result_detail(result)
        if self._result_failed(result):
            messagebox.showerror("Install failed", detail)
        else:
            messagebox.showinfo("Install", detail)
        self.config = load_config()
        self.setup = get_setup_status(self.config)
        if self.config.onboarding_complete:
            self._show_dashboard()
        else:
            self._show_onboarding()

    def _active_linked_root(self) -> Path | None:
        if not self.config.active_project:
            return None
        return resolve_linked_project_root(Path(self.config.active_project))

    def _on_ci_check(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        self._append_log(self.home_log, "Running ci-check…")
        self._run_bg(lambda: run_project_ci_check(root), self._ci_check_done)

    def _ci_check_done(self, report: dict) -> None:
        if self._is_bg_error(report):
            self.ci_list.delete(0, "end")
            self._append_log(self.home_log, self._result_detail(report))
            return
        self.ci_list.delete(0, "end")
        for step in report.get("steps", []):
            mark = "✓" if step.get("ok") else "✗"
            self.ci_list.insert("end", f"{mark}  {step.get('name')}: {step.get('detail')}")
        summary = "All checks passed." if report.get("ok") else "Some checks failed."
        self._append_log(self.home_log, summary)
        repair = report.get("repair")
        if repair:
            self._append_log(
                self.home_log,
                f"Repaired AGENTS.md — {repair.get('detail', 'updated Active feature')}.",
            )
            self._show_dashboard()
        for hint in report.get("hints", []):
            self._append_log(self.home_log, f"Tip: {hint}")

    def _on_map_sync(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        self._append_log(self.home_log, "Syncing impact maps…")
        self._run_bg(lambda: run_project_map_sync(root), self._map_sync_done)

    def _map_sync_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            return
        if result.get("ok") is False:
            self._append_log(self.home_log, self._result_detail(result))
            return
        added = len(result.get("project_added", [])) + len(result.get("test_added", []))
        updated = len(result.get("project_updated", [])) + len(result.get("test_updated", []))
        if added or updated:
            self._append_log(self.home_log, f"Impact maps synced: {added} added, {updated} updated.")
        else:
            self._append_log(self.home_log, "Impact maps already up to date.")

    def _on_deploy_agent_handoff(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        cfg = load_config()
        self._append_log(self.home_log, "Deploying unified agent handoff (Spec Kit + Continual Learning)…")
        self._run_bg(
            lambda: run_deploy_agent_handoff(
                root,
                hive_planner_root=cfg.normalized_hive_root(),
                force=False,
            ),
            self._deploy_handoff_done,
        )

    def _deploy_handoff_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            return
        if not result.get("ok"):
            self._append_log(self.home_log, self._result_detail(result))
            return
        count = len(result.get("files_written", []))
        self._append_log(
            self.home_log,
            f"Agent handoff deployed ({count} file(s)). Mode: {result.get('agent_handoff_mode', 'unified')}.",
        )
        repair = result.get("repair")
        if repair:
            self._append_log(self.home_log, f"Repaired AGENTS.md — {repair.get('detail', 'updated')}.")
        for warning in result.get("warnings", []):
            self._append_log(self.home_log, f"Warning: {warning}")
        self._show_dashboard()

    def _on_explore(self) -> None:
        if not self.config.active_project:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        linked = Path(self.config.active_project)
        if is_code_workspace_file(linked):
            explore_target = workspace_primary_folder(linked) or linked.parent
        else:
            explore_target = linked
        result = open_path_in_explorer(explore_target)
        if not result.get("ok"):
            messagebox.showerror("Open in Explorer", result.get("error", "Failed to open folder"))
            return
        if hasattr(self, "home_log"):
            self._append_log(self.home_log, f"Opened in Explorer: {result.get('path')}")

    def _on_open_user_guide(self) -> None:
        path = user_guide_path(self.config)
        if not path.is_file():
            messagebox.showwarning("Guide not found", f"Could not find:\n{path}")
            return
        result = open_path_in_explorer(path.parent)
        if not result.get("ok"):
            messagebox.showerror("Open guide", result.get("error", "Failed to open guide folder"))
            return
        messagebox.showinfo("User guide", f"Open this file in the folder:\n{path.name}")

    def _show_workspace_picker(self) -> None:
        self.config = load_config()
        linked_paths = {
            normalize_project_path(entry) for entry in self.config.recent_projects if entry
        }
        workspaces = discover_cursor_workspaces()
        dialog = tk.Toplevel(self.root)
        dialog.title("Add workspace link")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=COLORS["bg"])
        dialog.geometry("600x440")
        dialog.minsize(480, 320)

        tk.Label(
            dialog,
            text="Add workspace link",
            font=FONT_TITLE,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        ).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(
            dialog,
            text="Pick from Cursor's recent workspaces, or browse to any folder. "
            "Links are saved only in Hive Planner — Cursor is not changed.",
            wraplength=560,
            justify="left",
            font=FONT_SUBTITLE,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(anchor="w", padx=16, pady=(0, 12))

        list_card = tk.Frame(dialog, bg=COLORS["card"], highlightbackground=COLORS["border"], highlightthickness=1)
        list_card.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        picker_list = tk.Listbox(
            list_card,
            font=FONT,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            selectbackground=COLORS["primary"],
            selectforeground="white",
            activestyle="none",
            relief="flat",
            highlightthickness=0,
        )
        picker_list.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        picker_scroll = ttk.Scrollbar(list_card, orient="vertical", command=picker_list.yview)
        picker_scroll.pack(side="right", fill="y", pady=8)
        picker_list.configure(yscrollcommand=picker_scroll.set)
        bind_mousewheel(picker_scroll, target=picker_list)
        bind_mousewheel(list_card, target=picker_list)
        bind_mousewheel(picker_list)

        workspace_rows: list[CursorWorkspace] = list(workspaces)
        if workspace_rows:
            for workspace in workspace_rows:
                label = format_workspace_picker_label(workspace)
                if normalize_project_path(workspace.path) in linked_paths:
                    label = f"{label}  (linked)"
                picker_list.insert("end", label)
            picker_list.selection_set(0)
        else:
            picker_list.insert("end", "(No Cursor workspaces found — use Browse folder…)")

        actions = tk.Frame(dialog, bg=COLORS["bg"])
        actions.pack(fill="x", padx=16, pady=(0, 16))

        def link_selected() -> None:
            selection = picker_list.curselection()
            if not selection or not workspace_rows:
                messagebox.showwarning(
                    "No selection",
                    "Pick a workspace from the list, or use Browse folder…",
                    parent=dialog,
                )
                return
            workspace = workspace_rows[selection[0]]
            if not workspace.exists:
                messagebox.showerror(
                    "Missing folder",
                    f"That workspace folder no longer exists:\n{workspace.path}\n\n"
                    "Pick another workspace or browse to a valid folder.",
                    parent=dialog,
                )
                return
            dialog.destroy()
            self._link_workspace(Path(workspace.path))

        def browse_folder() -> None:
            dialog.destroy()
            path = filedialog.askdirectory(title="Choose Cursor workspace folder")
            if path:
                self._link_workspace(Path(path))

        primary_button(actions, "Add link", link_selected)
        secondary_button(actions, "Browse…", browse_folder)
        secondary_button(actions, "Cancel", dialog.destroy)

        picker_list.bind("<Double-Button-1>", lambda _event: link_selected())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.wait_window()

    def _link_workspace(self, path: Path, *, notify: bool = True) -> bool:
        workspace = classify_workspace(path)
        if not workspace.exists:
            messagebox.showerror("Workspace not found", f"Path does not exist:\n{workspace.path}")
            if hasattr(self, "recent_list") and callable(getattr(self.recent_list, "delete", None)):
                self._populate_recent_list()
            return False

        target = Path(workspace.path)
        hive_folder = (
            resolve_linked_project_root(target)
            or pick_hive_bootstrap_target(target)
            or workspace_primary_folder(target)
            or target
        )
        self.config = load_config()
        already_known = any(
            normalize_project_path(entry) == normalize_project_path(target)
            for entry in self.config.recent_projects
        )

        if not workspace.hive_ready and notify and not already_known:
            try:
                empty = hive_folder.is_dir() and not any(hive_folder.iterdir())
            except OSError:
                empty = False
            if empty:
                if messagebox.askyesno(
                    "Set up this folder?",
                    f"Folder is empty:\n{hive_folder}\n\nCreate Hive planning files here now?",
                ):
                    return self._bootstrap_and_activate(hive_folder, notify=notify, link_path=target)
                return False
            if workspace.has_cursor_dir or workspace.has_git or workspace.entry_kind == "workspace":
                label = workspace.name
                if messagebox.askyesno(
                    "Add Hive planning files?",
                    f"Cursor workspace:\n{label}\n\n"
                    f"Hive files will be added to:\n{hive_folder}\n\n"
                    "Health checks and handoff tools need START_HERE.md.\n\n"
                    "Add them now?",
                ):
                    return self._bootstrap_and_activate(hive_folder, notify=notify, link_path=target)
            elif not messagebox.askyesno(
                "Link this folder?",
                f"Link workspace:\n{hive_folder}\n\n"
                "This folder is not a Cursor or Hive project yet. Link it anyway?",
            ):
                return False

        self.config.add_recent_project(target)
        save_config(self.config)
        _, repair = prepare_linked_project_root(target, repair_agents=True)
        if notify:
            if workspace.hive_ready and hive_folder.is_dir():
                summary = summarize_linked_project(target, repair_agents=False)
                profile = summary.bootstrap_profile or "—"
                feature_line = summary.active_feature or "—"
                if repair and repair.repaired:
                    feature_line = repair.feature or feature_line
                messagebox.showinfo(
                    "Workspace linked",
                    f"{workspace.name}\n\nProfile: {profile}\nFeature: {feature_line}",
                )
            else:
                messagebox.showinfo(
                    "Workspace linked",
                    f"Linked: {workspace.name}\n\n"
                    "Use Open in Cursor to launch it. Add Hive planning files when you want health checks.",
                )
        self._show_dashboard()
        return True

    def _on_link_workspace(self) -> None:
        self._show_workspace_picker()

    def _bootstrap_and_activate(
        self,
        path: Path,
        *,
        notify: bool = True,
        force: bool = False,
        link_path: Path | None = None,
    ) -> bool:
        cfg = load_config()
        bootstrap_target = pick_hive_bootstrap_target(path) or path
        try:
            non_empty = bootstrap_target.is_dir() and any(bootstrap_target.iterdir())
        except OSError:
            non_empty = False
        if non_empty and not force and (bootstrap_target / "START_HERE.md").is_file():
            messagebox.showinfo(
                "Already a Hive project",
                f"Hive planning files already exist in:\n{bootstrap_target}",
            )
            self.config = load_config()
            self.config.add_recent_project(link_path or path)
            save_config(self.config)
            self._show_dashboard()
            return True
        if non_empty and not force:
            if not messagebox.askyesno(
                "Add to existing folder?",
                f"Add Hive planning files to:\n{bootstrap_target}\n\n"
                "Existing project files will be kept. Only missing Hive files are added.",
            ):
                return False
            force = True
        result = run_project_init(
            cfg,
            target=bootstrap_target,
            name=bootstrap_target.name,
            profile=cfg.default_profile,
            git_init=False,
            force=force,
            agent_handoff="unified",
        )
        if not result.get("ok"):
            messagebox.showerror("Setup failed", result.get("error", "Could not create Hive project."))
            return False
        self.config = load_config()
        self.config.add_recent_project(link_path or path)
        save_config(self.config)
        if notify:
            messagebox.showinfo(
                "Hive project ready",
                f"Created planning files in:\n{bootstrap_target}\n\nProfile: {cfg.default_profile}",
            )
        self._show_dashboard()
        return True

    def _on_open_cursor(self) -> None:
        root = self.config.active_project
        if not root or not _linked_path_exists(root):
            if messagebox.askyesno(
                "No linked workspace",
                "Link a Cursor workspace first?\n\n"
                "Pick one from Cursor's recent list, or browse to your repo folder.",
            ):
                self._show_workspace_picker()
            return
        result = open_in_cursor(Path(root), config=self.config)
        if not result.get("ok"):
            messagebox.showerror("Open in Cursor", result.get("error", "Failed to launch Cursor"))
            return
        if hasattr(self, "home_log"):
            name = _linked_display_name(root)
            hive_note = "hive ready" if result.get("hive_ready") else "cursor workspace"
            self._append_log(
                self.home_log,
                f"Opened in Cursor: {name} ({hive_note})",
            )

    def _on_create_project(self) -> None:
        target = self.new_target.get().strip()
        if not target:
            messagebox.showwarning("Missing path", "Choose a target folder.")
            return
        name = self.new_name.get().strip() or None
        profile = self.new_profile.get().strip() or "full"
        git_init = self.new_git.get()
        agent_handoff = self.new_agent_handoff.get().strip() or "unified"
        cfg = load_config()

        def work():
            return run_project_init(
                cfg,
                target=Path(target),
                name=name,
                profile=profile,
                git_init=git_init,
                force=False,
                agent_handoff=agent_handoff,
            )

        self._run_bg(work, self._create_done)

    def _create_done(self, result: dict) -> None:
        if not result.get("ok"):
            messagebox.showerror("Create failed", result.get("error", "Unknown error"))
            return
        self.config = load_config()
        self.config.add_recent_project(Path(result["target"]))
        save_config(self.config)
        messagebox.showinfo("Created", f"Project ready at:\n{result['target']}")
        self._show_dashboard()

    def _on_select_recent(self) -> None:
        path = self._selected_recent_path()
        if path is None:
            messagebox.showwarning("No selection", "Pick a linked workspace.")
            return
        self._link_workspace(path, notify=False)

    def _on_recent_double_click(self, _event=None) -> None:
        path = self._selected_recent_path()
        if path is None:
            return
        linked = Path(path)
        if is_code_workspace_file(linked):
            explore_target = workspace_primary_folder(linked) or linked.parent
        else:
            explore_target = linked
        result = open_path_in_explorer(explore_target)
        if not result.get("ok"):
            messagebox.showerror("Open folder", result.get("error", "Failed to open folder"))

    def _on_remove_recent(self) -> None:
        path = self._selected_recent_path()
        if path is None:
            messagebox.showwarning("No selection", "Pick a linked workspace.")
            return
        label = _linked_display_name(str(path))
        if not messagebox.askyesno(
            "Remove link",
            f"Remove the Hive Planner link for:\n{label}\n\n"
            "This only updates Hive Planner. Cursor and your files on disk are not changed.",
        ):
            return
        self.config = load_config()
        if not self.config.remove_recent_project(path):
            messagebox.showwarning("Not found", "That workspace link is not in your list.")
            return
        save_config(self.config)
        self._show_dashboard()

    def _on_delete_profile(self) -> None:
        from hive_planner.project_profile import delete_project_profile, project_meta_path

        path = self._selected_recent_path()
        if path is None:
            messagebox.showwarning("No selection", "Pick a linked workspace.")
            return
        profile_root = resolve_linked_project_root(path)
        if profile_root is None:
            messagebox.showerror(
                "Delete profile",
                "Could not resolve a project folder for this link.\n\n"
                "If this is a workspace file, check that its folders still exist on disk.",
            )
            return
        folder = profile_root.name
        meta_file = project_meta_path(profile_root)
        if not messagebox.askyesno(
            "Delete Hive profile",
            f"Delete Hive profile metadata for:\n{folder}\n\n"
            f"File removed: {meta_file.name}\n"
            "Your project code, docs, and other files are kept.\n\n"
            "Continue?",
        ):
            return
        if not messagebox.askyesno(
            "Confirm permanent deletion",
            f"Permanent action — delete the Hive profile for \"{folder}\"?\n\n"
            "This cannot be undone.",
        ):
            return
        ok, detail = delete_project_profile(profile_root)
        if not ok:
            messagebox.showerror("Delete profile", detail)
            return
        self.config = load_config()
        normalized = normalize_project_path(path)
        self.config.project_profiles.pop(normalized, None)
        save_config(self.config)
        messagebox.showinfo("Profile deleted", detail)
        self._show_dashboard()

    def _on_save_settings(self) -> None:
        self.config.hive_planner_root = self.cfg_hive.get().strip()
        self.config.python_executable = self.cfg_python.get().strip() or "py -3.11"
        self.config.cursor_executable = self.cfg_cursor.get().strip()
        self.config.default_profile = self.cfg_profile.get().strip() or "full"
        save_config(self.config)
        self.setup = get_setup_status(self.config)
        messagebox.showinfo("Saved", "Settings updated.")

    def _on_reset_onboarding(self) -> None:
        if not messagebox.askyesno(
            "Setup wizard",
            "Show the first-time setup wizard again?\n\nYour install and settings are kept.",
        ):
            return
        self.config.onboarding_complete = False
        save_config(self.config)
        self._wizard_step = 0
        self._show_onboarding()

    def _on_toggle_console(self) -> None:
        if not console_win.console_available():
            messagebox.showinfo("Console", "Console toggle is only available on Windows.")
            return
        if console_win.is_console_visible():
            console_win.hide_console()
            if hasattr(self, "console_btn"):
                self.console_btn.config(text="Show console")
            return
        if console_win.show_console():
            if console_win.is_console_visible() and hasattr(self, "console_btn"):
                self.console_btn.config(text="Hide console")
            print("Hive Planner — log output will appear here when running installs or checks.")
        else:
            messagebox.showerror("Console", "Could not open debug console.")


def run_app() -> None:
    root = tk.Tk()
    HivePlannerApp(root)
    root.mainloop()
