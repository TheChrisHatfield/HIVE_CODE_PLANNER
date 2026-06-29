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
    run_cartridge_import_folder,
    run_cartridge_load_sources,
    run_cartridge_translate,
    cartridge_load_needs_feature,
    cartridge_load_will_promote,
    candidates_path_in_project,
    find_staged_candidates,
    memory_candidates_picker_dir,
    run_agents_memory_apply,
    run_agents_memory_propose,
    run_deploy_agent_handoff,
    run_install,
    run_legacy_deployment_scan,
    run_cl_migrate,
    run_project_ci_check,
    run_project_init,
    run_project_map_sync,
    run_set_cl_runtime,
    run_unified_verify,
    run_wiring_audit_check,
    run_wiring_audit_record,
    summarize_linked_project,
    summarize_project,
    cl_runtime_status_label,
    wiring_audit_status_label,
    workspace_primary_folder,
)
from hive_planner.config import validate_feature_id
from hive_planner.agent_handoff import validate_unified_handoff
from hive_planner.launcher.theme import (
    COLORS,
    FONT,
    FONT_BOLD,
    FONT_SUBTITLE,
    FONT_TITLE,
    apply_ttk_style,
    attach_hover_tooltip,
    attach_combobox_tooltip,
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
        self._pending_home_log: list[str] = []
        self._pending_memory_candidates: Path | None = None
        self._pending_memory_link: str | None = None

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
                    else:
                        self._note_stale_bg_result(result)
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
        active_norm = (
            normalize_project_path(self.config.active_project)
            if self.config.active_project
            else ""
        )
        if self._pending_memory_link and self._pending_memory_link != active_norm:
            self._pending_memory_candidates = None
            self._pending_memory_link = None

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

    _PAGE_WHEEL_SKIP = (tk.Listbox, tk.Text, scrolledtext.ScrolledText, tk.Scrollbar)

    def _note_stale_bg_result(self, result: object) -> None:
        if isinstance(result, dict):
            err = result.get("error")
            mode = result.get("mode")
            if err:
                message = f"Background task finished after dashboard refresh: {err}"
            elif mode:
                message = (
                    f"Background task ({mode}) finished after dashboard refresh — "
                    "check project files or run the action again."
                )
            else:
                message = "Background task finished after dashboard refresh."
        else:
            message = f"Background task finished after dashboard refresh: {result}"
        self._pending_home_log.append(message)

    def _flush_pending_home_log(self) -> None:
        if not self._pending_home_log or not hasattr(self, "home_log"):
            return
        try:
            for line in self._pending_home_log:
                self._append_log(self.home_log, line)
        except tk.TclError:
            return
        self._pending_home_log.clear()

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
            ("CL runtime", self._active_cl_runtime_label()),
            ("Feature", self._active_feature_label()),
            ("Wiring", self._wiring_audit_label()),
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
        secondary_button(actions, "Load cartridge…", self._on_load_cartridge)
        secondary_button(actions, "Open in Explorer", self._on_explore)

        handoff_actions = tk.Frame(body, bg=COLORS["bg"])
        handoff_actions.pack(fill="x", padx=16, pady=(0, 8))
        secondary_button(
            handoff_actions,
            "Check wiring audit",
            self._on_wiring_audit_check,
            tooltip="Verify .hive/wiring-audit.json and tasks.md wiring checklist (unified handoff).",
        )
        secondary_button(
            handoff_actions,
            "Record wiring audit…",
            self._on_wiring_audit_record,
            tooltip="Record integration validation evidence after completing the wiring audit checklist.",
        )
        secondary_button(
            handoff_actions,
            "Promote memory…",
            self._on_agents_propose,
            tooltip="Run agents-propose on staged CL candidates (requires wiring audit attestation).",
        )
        secondary_button(
            handoff_actions,
            "Apply memory…",
            self._on_agents_apply,
            tooltip="Apply accepted CL candidates to AGENTS.md (agents-apply; requires prior propose).",
        )

        verify_actions = tk.Frame(body, bg=COLORS["bg"])
        verify_actions.pack(fill="x", padx=16, pady=(0, 8))
        secondary_button(
            verify_actions,
            "Verify vendor pins",
            self._on_unified_verify,
            tooltip="Check .hive/upstream-pins.json and vendored Spec Kit + CL overlay revs.",
        )
        secondary_button(
            verify_actions,
            "Scan legacy deployment",
            self._on_legacy_deployment_scan,
            tooltip="Detect marketplace CL, missing pins, or starter-kit-only layouts from pre-unified deploy.",
        )
        secondary_button(
            verify_actions,
            "Set CL runtime…",
            self._on_set_cl_runtime,
            tooltip="Choose Cursor plugin vs headless CLI memory loop (.hive/project.json cl_runtime).",
        )
        secondary_button(
            verify_actions,
            "Migrate marketplace CL…",
            self._on_cl_migrate,
            tooltip="Merge Learned Workspace Facts into Durable Workspace Facts; optionally remove marketplace plugin.",
        )

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
        self._flush_pending_home_log()

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
        self.new_agent_handoff = tk.StringVar(value=self.config.default_agent_handoff)
        self.new_cl_runtime = tk.StringVar(value="cursor")
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
        cl_runtime_row = tk.Frame(form, bg=COLORS["card"])
        cl_runtime_row.pack(fill="x", padx=12, pady=(4, 4))
        tk.Label(
            cl_runtime_row,
            text="CL runtime",
            width=14,
            anchor="w",
            bg=COLORS["card"],
            fg=COLORS["fg"],
            font=FONT,
        ).pack(side="left")
        ttk.Combobox(
            cl_runtime_row,
            textvariable=self.new_cl_runtime,
            values=["cursor", "headless"],
            state="readonly",
            width=28,
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            cl_runtime_row,
            text="cursor = vendored plugin; headless = CLI agents-propose path (other IDEs)",
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
        self.cfg_agent_handoff = tk.StringVar(value=self.config.default_agent_handoff)
        self._field(
            form,
            "Hive planner root",
            self.cfg_hive,
            browse=True,
            tooltip="Folder containing this Hive Planner checkout (pyproject.toml, src/hive_planner).",
            browse_tooltip="Pick the Hive Planner repo folder on disk.",
        )
        self._field(
            form,
            "Python command",
            self.cfg_python,
            scan_python=True,
            tooltip="Command used to run Hive (for example py -3.11 or a full python.exe path).",
            scan_tooltip="Search this PC for Python 3.11+ installations.",
        )
        self._field(
            form,
            "Cursor executable",
            self.cfg_cursor,
            browse_exe=True,
            tooltip="Path to Cursor.exe for Open in Cursor. Leave blank to auto-detect.",
            browse_tooltip="Browse to Cursor.exe if auto-detect fails.",
        )
        profile_row = tk.Frame(form, bg=COLORS["card"])
        profile_row.pack(fill="x", padx=12, pady=4)
        profile_label = tk.Label(
            profile_row,
            text="Default profile",
            width=14,
            anchor="w",
            bg=COLORS["card"],
            fg=COLORS["fg"],
            font=FONT,
        )
        profile_label.pack(side="left")
        attach_hover_tooltip(
            profile_label,
            "Bootstrap profile for new projects: full adds Spec Kit scaffolding; minimal is lighter.",
        )
        profile_combo = ttk.Combobox(
            profile_row,
            textvariable=self.cfg_profile,
            values=["full", "minimal"],
            state="readonly",
            width=28,
        )
        profile_combo.pack(side="left", fill="x", expand=True)
        attach_combobox_tooltip(profile_combo, "Used when creating or bootstrapping a new linked project.")
        handoff_row = tk.Frame(form, bg=COLORS["card"])
        handoff_row.pack(fill="x", padx=12, pady=4)
        handoff_label = tk.Label(
            handoff_row,
            text="Default handoff",
            width=14,
            anchor="w",
            bg=COLORS["card"],
            fg=COLORS["fg"],
            font=FONT,
        )
        handoff_label.pack(side="left")
        attach_hover_tooltip(
            handoff_label,
            "Unified deploys Spec Kit + Continual Learning together; off skips agent handoff scaffolding.",
        )
        handoff_combo = ttk.Combobox(
            handoff_row,
            textvariable=self.cfg_agent_handoff,
            values=["unified", "off"],
            state="readonly",
            width=28,
        )
        handoff_combo.pack(side="left", fill="x", expand=True)
        attach_combobox_tooltip(
            handoff_combo,
            "Default for New project and when bootstrapping a linked workspace.",
        )
        btn_row = tk.Frame(form, bg=COLORS["card"])
        btn_row.pack(fill="x", padx=12, pady=(8, 12))
        primary_button(
            btn_row,
            "Save settings",
            self._on_save_settings,
            tooltip="Write these paths and defaults to your Hive Planner config file.",
        )
        secondary_button(
            btn_row,
            "Install / update Hive",
            self._on_install,
            tooltip="Install or refresh the hive_planner Python package from the repo root above.",
        )
        secondary_button(
            btn_row,
            "Reset onboarding",
            self._on_reset_onboarding,
            tooltip="Show the first-time setup wizard again. Your links and settings are kept.",
        )
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
            attach_hover_tooltip(
                self.console_btn,
                "Show or hide the debug console window for launcher output.",
            )
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
        tooltip: str | None = None,
        browse_tooltip: str | None = None,
        scan_tooltip: str | None = None,
    ) -> None:
        row = tk.Frame(parent, bg=COLORS["card"])
        row.pack(fill="x", padx=12, pady=4)
        label_widget = tk.Label(row, text=label, width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT)
        label_widget.pack(side="left")
        if tooltip:
            attach_hover_tooltip(label_widget, tooltip)
        entry = tk.Entry(row, textvariable=variable, font=FONT, bg=COLORS["card"], fg=COLORS["fg"], relief="solid", bd=1)
        entry.pack(side="left", fill="x", expand=True)
        if tooltip:
            attach_hover_tooltip(entry, tooltip)
        if browse:
            secondary_button(
                row,
                "Browse…",
                lambda: self._browse_into(variable),
                tooltip=browse_tooltip or "Choose a folder.",
            )
        if browse_exe:
            secondary_button(
                row,
                "Browse…",
                lambda: self._browse_exe_into(variable),
                tooltip=browse_tooltip or "Choose an executable file.",
            )
        if scan_python:
            secondary_button(
                row,
                "Scan…",
                lambda: self._on_scan_python(variable),
                tooltip=scan_tooltip or "Search for Python installations.",
            )

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
            profile = stored.bootstrap_profile if stored else None
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
        root, _repair = prepare_linked_project_root(Path(self.config.active_project), repair_agents=False)
        if not root:
            return "—"
        status = validate_unified_handoff(root)
        if status.mode == "unified":
            return "unified ✓" if status.complete else "unified (incomplete)"
        return "off"

    def _active_cl_runtime_label(self) -> str:
        if not self.config.active_project:
            return "\u2014"
        root, _repair = prepare_linked_project_root(Path(self.config.active_project), repair_agents=False)
        if not root:
            return "\u2014"
        return cl_runtime_status_label(root)

    def _active_feature_label(self) -> str:
        if not self.config.active_project:
            return "—"
        summary = summarize_linked_project(Path(self.config.active_project))
        if not summary.ok:
            return "—"
        return summary.active_feature or "—"

    def _wiring_audit_label(self) -> str:
        if not self.config.active_project:
            return "—"
        root, _repair = prepare_linked_project_root(Path(self.config.active_project), repair_agents=False)
        if not root:
            return "—"
        return wiring_audit_status_label(root)

    def _active_profile_label(self) -> str:
        if not self.config.active_project:
            return "—"
        root, _repair = prepare_linked_project_root(Path(self.config.active_project))
        if not root:
            return ""
        stored = read_project_profile(root)
        if stored:
            return stored.bootstrap_profile
        return ""

    def _ask_cl_runtime(self, *, title: str, current: str) -> str | None:
        from hive_planner.cl_runtime import CL_RUNTIME_CURSOR, CL_RUNTIME_HEADLESS, cl_runtime_launcher_choice

        dialog_default = cl_runtime_launcher_choice(current)
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.geometry("520x280")

        choice = tk.StringVar(value=dialog_default)
        result: list[str | None] = [None]

        tk.Label(
            dialog,
            text="Continual Learning runtime for this project",
            font=FONT_TITLE,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        ).pack(anchor="w", padx=16, pady=(16, 8))
        tk.Label(
            dialog,
            text="Cursor installs the vendored hive-continual-learning plugin.\n"
            "Headless uses the Hive CLI memory loop for other IDEs (no Cursor hooks).",
            justify="left",
            wraplength=480,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        body = tk.Frame(dialog, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=16)
        for value, label in (
            (CL_RUNTIME_CURSOR, "Cursor plugin (.cursor/plugins/hive-continual-learning/)"),
            (CL_RUNTIME_HEADLESS, "Headless / other IDE (.hive/continual-learning/ + CLI)"),
        ):
            tk.Radiobutton(
                body,
                text=label,
                variable=choice,
                value=value,
                bg=COLORS["bg"],
                fg=COLORS["fg"],
                activebackground=COLORS["bg"],
                activeforeground=COLORS["fg"],
                selectcolor=COLORS["card"],
                anchor="w",
                justify="left",
            ).pack(anchor="w", pady=4)

        actions = tk.Frame(dialog, bg=COLORS["bg"])
        actions.pack(fill="x", padx=16, pady=(8, 16))

        def _confirm() -> None:
            result[0] = choice.get()
            dialog.destroy()

        def _cancel() -> None:
            result[0] = None
            dialog.destroy()

        primary_button(actions, "Continue", _confirm)
        secondary_button(actions, "Cancel", _cancel)
        dialog.wait_window()
        return result[0]

    def _on_set_cl_runtime(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        from hive_planner.cl_runtime import resolve_cl_runtime

        current = resolve_cl_runtime(root)
        selected = self._ask_cl_runtime(title="Set CL runtime", current=current)
        if selected is None:
            return
        self._append_log(self.home_log, f"Setting CL runtime to {selected}…")
        self._run_bg(lambda r=root, rt=selected: run_set_cl_runtime(r, rt), self._set_cl_runtime_done)

    def _set_cl_runtime_done(self, result: dict) -> None:
        if self._is_bg_error(result) or not result.get("ok"):
            self._append_log(self.home_log, self._result_detail(result))
            for hint in result.get("hints", []):
                self._append_log(self.home_log, f"Tip: {hint}")
            return
        runtime = result.get("cl_runtime", "")
        self._append_log(self.home_log, f"Set cl_runtime={runtime} in .hive/project.json.")
        for hint in result.get("hints", []):
            self._append_log(self.home_log, f"Tip: {hint}")
        self._show_dashboard()

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
        """True only for _run_bg bare exception wrappers, not structured failure payloads."""
        if not isinstance(result, dict) or not result.get("error"):
            return False
        structured_keys = (
            "files_written",
            "handoff",
            "steps",
            "warnings",
            "mode",
            "promote",
            "recorded",
            "check",
            "skipped",
            "hints",
            "proposal_path",
            "accepted",
            "rejected",
            "findings",
            "issues",
            "detail",
            "warnings",
            "actions",
            "merged_bullets",
        )
        return not any(key in result for key in structured_keys)

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
        self._run_bg(lambda r=root: run_project_ci_check(r), self._ci_check_done)

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
        for hint in report.get("hints", []):
            self._append_log(self.home_log, f"Tip: {hint}")
        self._show_dashboard()

    def _on_wiring_audit_check(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        self._append_log(self.home_log, "Checking wiring audit attestation…")
        self._run_bg(lambda r=root: run_wiring_audit_check(r), self._wiring_audit_check_done)

    def _wiring_audit_check_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            return
        if result.get("skipped"):
            self._append_log(self.home_log, result.get("detail", "Wiring audit not enforced."))
            return
        detail = result.get("detail", "ok")
        mark = "ok" if result.get("ok") else "failed"
        self._append_log(self.home_log, f"Wiring audit: {mark} — {detail}")
        for hint in result.get("hints", []):
            self._append_log(self.home_log, f"Tip: {hint}")
        self._show_dashboard()

    def _on_wiring_audit_record(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Record wiring audit")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        tk.Label(
            dialog,
            text="Integration validation command (evidence):",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT,
        ).pack(anchor="w", padx=16, pady=(16, 4))
        evidence_var = tk.StringVar(value="pytest -q")
        entry = tk.Entry(dialog, textvariable=evidence_var, width=52, font=FONT)
        entry.pack(padx=16, pady=(0, 8))
        entry.focus_set()
        tk.Label(
            dialog,
            text="Complete tasks.md wiring audit checklist before recording.",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

        def submit() -> None:
            evidence = evidence_var.get().strip()
            if not evidence:
                messagebox.showwarning("Evidence required", "Enter the validation command you ran.", parent=dialog)
                return
            dialog.destroy()
            self._append_log(self.home_log, f"Recording wiring audit (evidence: {evidence})…")
            self._run_bg(
                lambda r=root, e=evidence: run_wiring_audit_record(r, e),
                self._wiring_audit_record_done,
            )

        btn_row = tk.Frame(dialog, bg=COLORS["bg"])
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        primary_button(btn_row, "Record", submit)
        secondary_button(btn_row, "Cancel", dialog.destroy)

    def _wiring_audit_record_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            return
        if result.get("skipped"):
            self._append_log(self.home_log, result.get("detail", "Wiring audit not enforced."))
            return
        if result.get("recorded"):
            self._append_log(self.home_log, f"Wrote {result['recorded']}")
        if result.get("ok"):
            self._append_log(self.home_log, "Wiring audit attestation valid.")
        else:
            self._append_log(self.home_log, self._result_detail(result))
            for hint in result.get("hints", []):
                self._append_log(self.home_log, f"Tip: {hint}")
        self._show_dashboard()

    def _set_pending_memory_candidates(self, root: Path, candidates: Path) -> None:
        self._pending_memory_candidates = candidates
        link = self.config.active_project
        self._pending_memory_link = (
            normalize_project_path(link) if link else normalize_project_path(str(root))
        )

    def _pending_memory_for_root(self, root: Path) -> Path | None:
        if not self._pending_memory_candidates:
            return None
        active = (
            normalize_project_path(self.config.active_project)
            if self.config.active_project
            else normalize_project_path(str(root))
        )
        if self._pending_memory_link != active:
            return None
        return self._pending_memory_candidates

    def _on_agents_propose(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        default = find_staged_candidates(root)
        selected = filedialog.askopenfilename(
            title="Select CL candidates file",
            initialdir=memory_candidates_picker_dir(root, default),
            filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
        )
        if not selected:
            return
        candidates = Path(selected)
        if not candidates_path_in_project(root, candidates):
            messagebox.showerror(
                "Invalid candidates file",
                "Select a candidates file inside the linked project (docs/proposals/).",
                parent=self.root,
            )
            return
        self._set_pending_memory_candidates(root, candidates)
        self._append_log(self.home_log, f"Running agents-propose on {candidates.name}…")
        self._run_bg(
            lambda r=root, c=candidates: run_agents_memory_propose(r, c, apply=False),
            self._agents_propose_done,
        )

    def _on_agents_apply(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        default = self._pending_memory_for_root(root) or find_staged_candidates(root)
        selected = filedialog.askopenfilename(
            title="Select CL candidates file to apply",
            initialdir=memory_candidates_picker_dir(root, default),
            filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
        )
        if not selected:
            return
        candidates = Path(selected)
        if not candidates_path_in_project(root, candidates):
            messagebox.showerror(
                "Invalid candidates file",
                "Select a candidates file inside the linked project (docs/proposals/).",
                parent=self.root,
            )
            return
        self._set_pending_memory_candidates(root, candidates)
        if not messagebox.askyesno(
            "Apply memory",
            "Apply accepted candidates from this file to AGENTS.md?\n\n"
            "Run Promote memory first if you have not generated a proposal.",
            parent=self.root,
        ):
            return
        self._append_log(self.home_log, f"Running agents-apply on {candidates.name}…")
        self._run_bg(
            lambda r=root, c=candidates: run_agents_memory_apply(r, c),
            self._agents_apply_done,
        )

    def _agents_apply_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            self._show_dashboard()
            return
        if not result.get("ok"):
            self._append_log(self.home_log, self._result_detail(result))
            for hint in result.get("hints", []):
                self._append_log(self.home_log, f"Tip: {hint}")
            self._show_dashboard()
            return
        self._append_log(self.home_log, f"Proposal: {result.get('proposal_path')}")
        accepted = result.get("accepted") or []
        if accepted:
            self._append_log(self.home_log, f"Applied {len(accepted)} bullet(s) to AGENTS.md.")
        if result.get("applied"):
            self._append_log(self.home_log, "AGENTS.md updated.")
        self._show_dashboard()

    def _agents_propose_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            self._show_dashboard()
            return
        if not result.get("ok"):
            self._append_log(self.home_log, self._result_detail(result))
            for hint in result.get("hints", []):
                self._append_log(self.home_log, f"Tip: {hint}")
            self._show_dashboard()
            return
        self._append_log(self.home_log, f"Wrote proposal: {result.get('proposal_path')}")
        accepted = result.get("accepted") or []
        rejected = result.get("rejected") or []
        if accepted:
            self._append_log(self.home_log, f"Accepted {len(accepted)} candidate(s).")
        if rejected:
            self._append_log(self.home_log, f"Rejected {len(rejected)} candidate(s) — see proposal file.")
        if result.get("applied"):
            self._append_log(self.home_log, "Applied to AGENTS.md.")
        else:
            root = self._active_linked_root()
            if accepted and root and self._pending_memory_for_root(root):
                if messagebox.askyesno(
                    "Apply memory?",
                    f"Apply {len(accepted)} accepted bullet(s) to AGENTS.md now?",
                    parent=self.root,
                ):
                    candidates = self._pending_memory_for_root(root)
                    if candidates:
                        self._append_log(self.home_log, f"Running agents-apply on {candidates.name}…")
                        self._run_bg(
                            lambda r=root, c=candidates: run_agents_memory_apply(r, c),
                            self._agents_apply_done,
                        )
                        return
        self._show_dashboard()

    def _on_unified_verify(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        self._append_log(self.home_log, "Verifying upstream pins and vendored overlays…")
        self._run_bg(lambda r=root: run_unified_verify(r), self._unified_verify_done)

    def _unified_verify_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            return
        if result.get("ok"):
            self._append_log(self.home_log, "Vendor pins and overlays OK.")
        else:
            self._append_log(self.home_log, self._result_detail(result))
            for issue in result.get("issues") or []:
                self._append_log(self.home_log, f"  issue: {issue}")
            for hint in result.get("hints", []):
                self._append_log(self.home_log, f"Tip: {hint}")
        pins_match = result.get("pins_match")
        if pins_match is not None:
            self._append_log(self.home_log, f"Pins match packaged manifest: {pins_match}")
        self._show_dashboard()

    def _on_legacy_deployment_scan(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        self._append_log(self.home_log, "Scanning for legacy deployment traces…")
        self._run_bg(lambda r=root: run_legacy_deployment_scan(r), self._legacy_deployment_scan_done)

    def _legacy_deployment_scan_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            return
        self._append_log(self.home_log, result.get("detail", "Scan complete."))
        for finding in result.get("findings") or []:
            severity = finding.get("severity", "info")
            prefix = "WARN" if severity == "warn" else "info"
            self._append_log(self.home_log, f"  [{prefix}] {finding.get('detail')}")
            repair = finding.get("repair")
            if repair:
                self._append_log(self.home_log, f"    repair: {repair}")
        self._show_dashboard()

    def _on_cl_migrate(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        remove_plugin = messagebox.askyesno(
            "Remove marketplace plugin?",
            "Also remove .cursor/plugins/continual-learning/ from this project?\n\n"
            "Choose Yes to avoid dual CL hooks (recommended after Deploy agent handoff).\n"
            "Choose No to merge AGENTS.md data only.",
            parent=self.root,
        )
        self._append_log(self.home_log, "Migrating marketplace Continual Learning data to Hive format…")
        self._run_bg(
            lambda r=root, rm=remove_plugin: run_cl_migrate(r, remove_marketplace_plugin=rm),
            self._cl_migrate_done,
        )

    def _cl_migrate_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            self._show_dashboard()
            return
        if not result.get("ok"):
            self._append_log(self.home_log, self._result_detail(result))
            for hint in result.get("hints", []):
                self._append_log(self.home_log, f"Tip: {hint}")
            for warning in result.get("warnings", []):
                self._append_log(self.home_log, f"Warning: {warning}")
            self._show_dashboard()
            return
        for action in result.get("actions") or []:
            self._append_log(self.home_log, f"  {action}")
        for warning in result.get("warnings", []):
            self._append_log(self.home_log, f"Warning: {warning}")
        merged = result.get("merged_bullets", 0)
        if merged:
            self._append_log(self.home_log, f"Merged {merged} bullet(s) into ## Durable Workspace Facts.")
        if result.get("removed_marketplace_plugin"):
            self._append_log(self.home_log, "Removed marketplace continual-learning plugin from project.")
        if result.get("cl_source"):
            self._append_log(self.home_log, f"Set cl_source={result['cl_source']} in .hive/project.json.")
        if result.get("dry_run"):
            self._append_log(self.home_log, "CL migration dry run complete.")
        else:
            self._append_log(self.home_log, "CL migration complete.")
        self._show_dashboard()

    def _on_map_sync(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        self._append_log(self.home_log, "Syncing impact maps…")
        self._run_bg(lambda r=root: run_project_map_sync(r), self._map_sync_done)

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
        from hive_planner.cl_runtime import resolve_cl_runtime

        current = resolve_cl_runtime(root)
        selected = self._ask_cl_runtime(title="Deploy agent handoff", current=current)
        if selected is None:
            return
        cfg = load_config()
        self._append_log(
            self.home_log,
            f"Deploying unified agent handoff (Spec Kit + Continual Learning, cl_runtime={selected})…",
        )
        hive_root = cfg.normalized_hive_root()
        self._run_bg(
            lambda r=root, h=hive_root, rt=selected: run_deploy_agent_handoff(
                r,
                hive_planner_root=h,
                force=False,
                cl_runtime=rt,
            ),
            self._deploy_handoff_done,
        )

    def _on_load_cartridge(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        summary = summarize_linked_project(Path(self.config.active_project))
        default_feature = summary.active_feature or "example-feature"

        dialog = tk.Toplevel(self.root)
        dialog.title("Load cartridge")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("520x520")
        dialog.minsize(480, 460)

        action_row = tk.Frame(dialog, bg=COLORS["bg"])
        action_row.pack(side="bottom", fill="x", padx=16, pady=(8, 16))

        body_host = tk.Frame(dialog, bg=COLORS["bg"])
        body_host.pack(fill="both", expand=True)
        canvas = tk.Canvas(body_host, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_host, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=COLORS["bg"])
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")

        def _sync_body_scroll(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_body_width(event) -> None:
            canvas.itemconfig(body_window, width=event.width)

        body.bind("<Configure>", _sync_body_scroll)
        canvas.bind("<Configure>", _sync_body_width)
        bind_mousewheel(canvas, target=canvas)
        bind_mousewheel(body, target=canvas)

        tk.Label(
            body,
            text="Add reference docs, translate research into draft cartridge files, or import an existing cartridge folder.",
            wraplength=480,
            justify="left",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", padx=16, pady=(16, 8))

        mode_var = tk.StringVar(value="sources")
        for value, label in (
            ("sources", "Add source files — copy into context-library, ingest, and emit cartridge"),
            ("translate", "Translate research — one markdown file into draft cartridge/*.md"),
            ("import", "Import cartridge folder — copy cartridge markdown and manifest into the project"),
        ):
            tk.Radiobutton(
                body,
                text=label,
                variable=mode_var,
                value=value,
                bg=COLORS["bg"],
                fg=COLORS["fg"],
                activebackground=COLORS["bg"],
                activeforeground=COLORS["fg"],
                selectcolor=COLORS["card"],
                anchor="w",
                justify="left",
                font=FONT,
                wraplength=470,
            ).pack(anchor="w", padx=16, pady=2)

        feature_row = tk.Frame(body, bg=COLORS["bg"])
        feature_row.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(feature_row, text="Feature id", width=12, anchor="w", bg=COLORS["bg"], fg=COLORS["fg"], font=FONT).pack(
            side="left"
        )
        feature_var = tk.StringVar(value=default_feature)
        feature_entry = tk.Entry(feature_row, textvariable=feature_var, font=FONT, bg=COLORS["card"], fg=COLORS["fg"])
        feature_entry.pack(side="left", fill="x", expand=True)

        handoff_status = validate_unified_handoff(root)
        handoff_unified = handoff_status.mode == "unified"
        promote_var = tk.BooleanVar(value=handoff_unified)
        force_promote_var = tk.BooleanVar(value=False)
        promote_row = tk.Frame(body, bg=COLORS["bg"])
        promote_row.pack(fill="x", padx=16, pady=(0, 4))
        promote_cb = tk.Checkbutton(
            promote_row,
            text="Promote drafts to Delta/Spec Kit, stage CL candidates, and run spec-drift (unified handoff)",
            variable=promote_var,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            selectcolor=COLORS["card"],
            anchor="w",
            font=FONT,
            wraplength=470,
            justify="left",
            state="normal" if handoff_unified else "disabled",
        )
        promote_cb.pack(anchor="w")
        if not handoff_unified:
            promote_var.set(False)

        force_row = tk.Frame(body, bg=COLORS["bg"])
        force_row.pack(fill="x", padx=16, pady=(0, 4))
        force_cb = tk.Checkbutton(
            force_row,
            text="Force promote — overwrite existing Delta/spec files (review carefully)",
            variable=force_promote_var,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            selectcolor=COLORS["card"],
            anchor="w",
            font=FONT,
            wraplength=470,
            justify="left",
            state="disabled",
        )
        force_cb.pack(anchor="w")

        overwrite_var = tk.BooleanVar(value=False)
        overwrite_row = tk.Frame(body, bg=COLORS["bg"])
        overwrite_row.pack(fill="x", padx=16, pady=(0, 4))
        overwrite_cb = tk.Checkbutton(
            overwrite_row,
            text="Overwrite existing cartridge files in the project",
            variable=overwrite_var,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            selectcolor=COLORS["card"],
            anchor="w",
            font=FONT,
            wraplength=470,
            justify="left",
            state="disabled",
        )
        overwrite_cb.pack(anchor="w")

        def sync_promote_controls(*_args: object) -> None:
            if not handoff_unified:
                force_cb.configure(state="disabled")
                force_promote_var.set(False)
                return
            if promote_var.get():
                force_cb.configure(state="normal")
            else:
                force_cb.configure(state="disabled")
                force_promote_var.set(False)

        promote_var.trace_add("write", sync_promote_controls)
        sync_promote_controls()

        def sync_import_controls(*_args: object) -> None:
            if mode_var.get() == "import":
                overwrite_cb.configure(state="normal")
            else:
                overwrite_cb.configure(state="disabled")
                overwrite_var.set(False)

        mode_var.trace_add("write", sync_import_controls)
        sync_import_controls()

        selection_var = tk.StringVar(value="(none selected)")
        tk.Label(
            body,
            textvariable=selection_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            wraplength=480,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(8, 4))

        selected_files: list[Path] = []
        selected_folder: Path | None = None

        def clear_cartridge_selection(*_args: object) -> None:
            nonlocal selected_folder
            selected_files.clear()
            selected_folder = None
            selection_var.set("(none selected)")

        mode_var.trace_add("write", clear_cartridge_selection)

        source_types = [
            ("Supported sources", "*.md *.txt *.pdf *.docx *.html *.htm *.csv *.pptx"),
            ("Markdown", "*.md"),
            ("All files", "*.*"),
        ]

        def browse() -> None:
            nonlocal selected_folder
            mode = mode_var.get()
            if mode == "import":
                folder = filedialog.askdirectory(title="Choose cartridge folder", parent=dialog)
                if not folder:
                    return
                selected_folder = Path(folder)
                selected_files.clear()
                selection_var.set(selected_folder.as_posix())
                return
            if mode == "translate":
                path = filedialog.askopenfilename(
                    title="Choose research markdown",
                    parent=dialog,
                    filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
                )
                if not path:
                    return
                selected_files[:] = [Path(path)]
                selected_folder = None
                selection_var.set(path)
                return
            paths = filedialog.askopenfilenames(
                title="Choose source files",
                parent=dialog,
                filetypes=source_types,
            )
            if not paths:
                return
            selected_files[:] = [Path(p) for p in paths]
            selected_folder = None
            if len(selected_files) == 1:
                selection_var.set(str(selected_files[0]))
            else:
                selection_var.set(f"{len(selected_files)} files selected")

        browse_row = tk.Frame(body, bg=COLORS["bg"])
        browse_row.pack(fill="x", padx=16, pady=(4, 16))
        secondary_button(browse_row, "Browse…", browse)

        def run_load() -> None:
            mode = mode_var.get()
            feature = feature_var.get().strip()
            will_promote = cartridge_load_will_promote(
                promote_checked=promote_var.get(),
                handoff_unified=handoff_unified,
            )
            needs_feature = cartridge_load_needs_feature(mode, will_promote=will_promote)
            if needs_feature:
                if not feature:
                    messagebox.showwarning(
                        "Feature required",
                        "Enter a feature id for this load mode.",
                        parent=dialog,
                    )
                    return
                try:
                    validate_feature_id(feature)
                except ValueError as exc:
                    messagebox.showerror("Invalid feature", str(exc), parent=dialog)
                    return
            if mode == "import" and not selected_folder:
                messagebox.showwarning("Nothing selected", "Choose a cartridge folder first.", parent=dialog)
                return
            if mode == "sources" and not selected_files:
                messagebox.showwarning("Nothing selected", "Choose one or more source files first.", parent=dialog)
                return
            if mode == "translate" and not selected_files:
                messagebox.showwarning("Nothing selected", "Choose a research markdown file first.", parent=dialog)
                return

            do_promote = will_promote
            do_feature = feature.strip() if feature.strip() else None
            do_force = force_promote_var.get()
            do_overwrite = overwrite_var.get() if mode == "import" else False

            dialog.destroy()
            if mode == "sources":
                self._append_log(
                    self.home_log,
                    f"Loading {len(selected_files)} source file(s) and emitting cartridge for '{feature}'…",
                )
                self._run_bg(
                    lambda: run_cartridge_load_sources(
                        root,
                        selected_files,
                        do_feature,
                        promote=do_promote,
                        force_promote=do_force,
                    ),
                    self._cartridge_load_done,
                )
            elif mode == "translate":
                self._append_log(self.home_log, f"Translating research into draft cartridge for '{feature}'…")
                self._run_bg(
                    lambda: run_cartridge_translate(
                        root,
                        selected_files[0],
                        do_feature,
                        promote=do_promote,
                        force_promote=do_force,
                    ),
                    self._cartridge_load_done,
                )
            else:
                self._append_log(self.home_log, "Importing cartridge folder…")
                self._run_bg(
                    lambda: run_cartridge_import_folder(
                        root,
                        selected_folder,
                        overwrite=do_overwrite,
                        feature=do_feature,
                        promote=do_promote,
                        force_promote=do_force,
                    ),
                    self._cartridge_load_done,
                )

        primary_button(
            action_row,
            "Load cartridge",
            run_load,
            tooltip="Run the selected load mode on the linked project.",
        )
        secondary_button(action_row, "Cancel", dialog.destroy)

    def _cartridge_load_done(self, result: dict) -> None:
        if not isinstance(result, dict):
            self._append_log(self.home_log, str(result))
            return

        worked = bool(
            result.get("files_written")
            or result.get("copied")
            or result.get("written")
            or result.get("outputs")
        )

        if result.get("ok") is False:
            if result.get("error"):
                self._append_log(self.home_log, self._result_detail(result))
            for rel in result.get("copied", []):
                self._append_log(self.home_log, f"  copied: {rel}")
            for rel in result.get("skipped", []):
                self._append_log(self.home_log, f"  skipped (exists): cartridge/{rel}")
            for warning in result.get("warnings", []):
                self._append_log(self.home_log, f"Warning: {warning}")
            if worked:
                self._append_log(
                    self.home_log,
                    "Cartridge load incomplete — partial work saved; see errors above.",
                )
            elif result.get("mode") == "import" and result.get("skipped") and "already exist" in str(result.get("error", "")):
                self._append_log(
                    self.home_log,
                    "Tip: re-open Load cartridge, enable Overwrite existing cartridge files, then try again.",
                )
            self._log_cartridge_promote(result.get("promote"))
            promote = result.get("promote") or {}
            if promote and promote.get("ok") is False:
                self._append_log(
                    self.home_log,
                    "Cartridge load incomplete — files saved but promotion/handoff needs review (see above).",
                )
            return

        mode = result.get("mode")
        if mode == "sources":
            self._append_log(
                self.home_log,
                f"Cartridge sources loaded ({result.get('processed', 0)} indexed, feature: {result.get('feature')}).",
            )
            for rel in result.get("copied", []):
                self._append_log(self.home_log, f"  copied: {rel}")
            for name, rel in (result.get("outputs") or {}).items():
                self._append_log(self.home_log, f"  wrote {name}: {rel}")
        elif mode == "translate":
            self._append_log(
                self.home_log,
                f"Draft cartridge written for '{result.get('feature')}' ({len(result.get('files_written', []))} file(s)).",
            )
            for rel in result.get("files_written", []):
                self._append_log(self.home_log, f"  cartridge/{rel}")
        elif mode == "import":
            self._append_log(
                self.home_log,
                f"Imported {len(result.get('written', []))} cartridge file(s).",
            )
            for rel in result.get("written", []):
                self._append_log(self.home_log, f"  wrote: cartridge/{rel}")
            for rel in result.get("skipped", []):
                self._append_log(self.home_log, f"  skipped (exists): cartridge/{rel}")
            adapt = result.get("adapt")
            if adapt and adapt.get("adapted"):
                self._append_log(
                    self.home_log,
                    f"Adapted custom files to standard layout (feature: {adapt.get('feature')}).",
                )
                for rel in adapt.get("adapted", []):
                    self._append_log(self.home_log, f"  layer file: cartridge/{rel}")
                for src, dst in sorted((adapt.get("mappings") or {}).items()):
                    if src != dst:
                        self._append_log(self.home_log, f"  mapped: {src} -> cartridge/{dst}")
            if result.get("feature"):
                self._append_log(self.home_log, f"  using feature id: {result['feature']}")
        self._log_cartridge_promote(result.get("promote"))
        promote = result.get("promote") or {}
        if promote and promote.get("ok") is False:
            self._append_log(
                self.home_log,
                "Cartridge load incomplete — files saved but promotion/handoff needs review (see above).",
            )
        for warning in result.get("warnings", []):
            self._append_log(self.home_log, f"Warning: {warning}")

    def _log_cartridge_promote(self, promote: dict | None) -> None:
        if not promote:
            return
        from hive_planner.cartridge_promote import promote_nothing_written_guidance, promote_wrote_layers

        self._append_log(self.home_log, "Promotion / symbiotic handoff:")
        if promote.get("feature"):
            self._append_log(self.home_log, f"  feature: {promote['feature']}")
        for layer, status in sorted(promote.get("promotions", {}).items()):
            self._append_log(self.home_log, f"  {layer}: {status}")
        if promote.get("candidates_path"):
            self._append_log(
                self.home_log,
                f"  CL candidates (review, then promote memory): {promote['candidates_path']}",
            )
            self._append_log(
                self.home_log,
                "  Next: Home → Record wiring audit, then Home → Promote memory (or agents-propose CLI).",
            )
        if promote.get("ok") is False and promote.get("promotions", {}).get("status") == "skipped (agent handoff off)":
            self._append_log(
                self.home_log,
                "  Enable unified handoff (Deploy agent handoff) to promote cartridge drafts.",
            )
        repair = promote.get("agents_repair")
        if repair:
            self._append_log(self.home_log, f"  AGENTS.md repair: {repair.get('detail')}")
        rosetta = promote.get("rosetta_repair")
        if rosetta:
            self._append_log(self.home_log, f"  Rosetta navigation: {rosetta.get('detail')}")
            for rel in rosetta.get("patched") or []:
                self._append_log(self.home_log, f"    patched: {rel}")
        if promote_wrote_layers(promote.get("promotions", {})) or rosetta:
            self._append_log(
                self.home_log,
                "  Agent startup: load docs/planning-rosetta-stone.md (hook planning.rosetta) before spec/delta",
            )
        drift = promote.get("spec_drift")
        if drift is not None:
            mark = "ok" if drift.get("ok") else "review needed"
            self._append_log(self.home_log, f"  spec-drift: {mark}")
        for warning in promote.get("warnings", []):
            self._append_log(self.home_log, f"  Warning: {warning}")
        guidance = promote_nothing_written_guidance(promote)
        if guidance:
            self._append_log(self.home_log, f"  Note: {guidance}")
        if promote.get("ok") is False:
            self._append_log(self.home_log, "Promotion/spec-drift needs review before handoff.")

    def _deploy_handoff_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._append_log(self.home_log, self._result_detail(result))
            return
        if not result.get("ok"):
            if result.get("error"):
                self._append_log(self.home_log, self._result_detail(result))
            count = len(result.get("files_written", []))
            if count:
                self._append_log(
                    self.home_log,
                    f"Partial deploy — {count} file(s) written; unified handoff still incomplete.",
                )
            repair = result.get("repair")
            if repair:
                self._append_log(self.home_log, f"Repaired AGENTS.md — {repair.get('detail', 'updated')}.")
            rosetta = result.get("rosetta_repair")
            if rosetta:
                self._append_log(self.home_log, f"  Rosetta navigation: {rosetta.get('detail')}")
                for rel in rosetta.get("patched") or []:
                    self._append_log(self.home_log, f"    patched: {rel}")
            handoff = result.get("handoff") or {}
            for rel in handoff.get("missing") or []:
                self._append_log(self.home_log, f"  missing: {rel}")
            for warning in result.get("warnings", []):
                self._append_log(self.home_log, f"Warning: {warning}")
            for hint in result.get("hints", []):
                self._append_log(self.home_log, f"Tip: {hint}")
            return
        count = len(result.get("files_written", []))
        runtime = result.get("cl_runtime", "")
        self._append_log(
            self.home_log,
            f"Agent handoff deployed ({count} file(s)). Mode: {result.get('agent_handoff_mode', 'unified')}"
            + (f", cl_runtime={runtime}." if runtime else "."),
        )
        repair = result.get("repair")
        if repair:
            self._append_log(self.home_log, f"Repaired AGENTS.md — {repair.get('detail', 'updated')}.")
        rosetta = result.get("rosetta_repair")
        if rosetta:
            self._append_log(self.home_log, f"  Rosetta navigation: {rosetta.get('detail')}")
            for rel in rosetta.get("patched") or []:
                self._append_log(self.home_log, f"    patched: {rel}")
        for warning in result.get("warnings", []):
            self._append_log(self.home_log, f"Warning: {warning}")
        for hint in result.get("hints", []):
            self._append_log(self.home_log, f"Tip: {hint}")
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
            agent_handoff=cfg.default_agent_handoff,
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
                f"Created planning files in:\n{bootstrap_target}\n\n"
                f"Profile: {cfg.default_profile}\nHandoff: {cfg.default_agent_handoff}",
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
        from hive_planner.agent_handoff import normalize_agent_handoff_mode

        agent_handoff = normalize_agent_handoff_mode(self.new_agent_handoff.get(), default="unified")
        cl_runtime = self.new_cl_runtime.get().strip() or "cursor"
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
                cl_runtime=cl_runtime if agent_handoff == "unified" else None,
            )

        self._run_bg(work, self._create_done)

    def _create_done(self, result: dict) -> None:
        if not result.get("ok"):
            detail = result.get("error", "Unknown error")
            if result.get("target") and result.get("files_written"):
                detail = (
                    f"{detail}\n\nPartial bootstrap — {len(result['files_written'])} file(s) written to:\n"
                    f"{result['target']}"
                )
            messagebox.showerror("Create failed", detail)
            if hasattr(self, "home_log"):
                self._append_log(self.home_log, detail)
                for warning in result.get("warnings", []):
                    self._append_log(self.home_log, f"Warning: {warning}")
                handoff = result.get("handoff") or {}
                for rel in handoff.get("missing") or []:
                    self._append_log(self.home_log, f"  missing: {rel}")
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
        from hive_planner.launcher.config import clear_project_profile_cache

        clear_project_profile_cache(self.config, path)
        save_config(self.config)
        messagebox.showinfo("Profile deleted", detail)
        self._show_dashboard()

    def _on_save_settings(self) -> None:
        self.config.hive_planner_root = self.cfg_hive.get().strip()
        self.config.python_executable = self.cfg_python.get().strip() or "py -3.11"
        self.config.cursor_executable = self.cfg_cursor.get().strip()
        self.config.default_profile = self.cfg_profile.get().strip() or "full"
        from hive_planner.agent_handoff import normalize_agent_handoff_mode

        self.config.default_agent_handoff = normalize_agent_handoff_mode(
            self.cfg_agent_handoff.get(),
            default="unified",
        )
        save_config(self.config)
        self.setup = get_setup_status(self.config)
        self._show_dashboard()
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
