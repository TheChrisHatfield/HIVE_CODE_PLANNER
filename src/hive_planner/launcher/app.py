from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from hive_planner.launcher.bootstrap_state import (
    BootstrapState,
    LinkBootstrapChoice,
    summarize_bootstrap_state,
)
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
    run_agents_memory_finalize_apply,
    run_agents_memory_propose,
    run_deploy_agent_handoff,
    run_portable_bootstrap,
    run_install,
    run_legacy_deployment_scan,
    run_cl_migrate,
    peek_agnostic_loop_status,
    peek_bug_hunt_status,
    run_project_agnostic_loop_arm,
    run_project_agnostic_loop_begin,
    run_project_agnostic_loop_choose,
    run_project_agnostic_loop_install,
    run_project_agnostic_loop_observe,
    run_project_agnostic_loop_review,
    run_project_agnostic_loop_rewards,
    run_project_agnostic_loop_status,
    run_project_bug_hunt_install,
    peek_implementation_loop_pack,
    run_project_implementation_loop_accept,
    run_project_implementation_loop_check,
    run_project_implementation_loop_commit,
    run_project_implementation_loop_handoff,
    run_project_implementation_loop_install,
    run_project_implementation_loop_start,
    run_project_implementation_loop_status,
    run_project_ci_check,
    run_project_init,
    run_project_map_sync,
    run_set_cl_runtime,
    run_source4s_upload,
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
from hive_planner.launcher.agent_prompt_templates import (
    default_agent_prompt_templates,
    get_agent_prompt_template_by_title,
)
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
        self._home_log_history: list[str] = []
        self._home_log_scope = (
            normalize_project_path(self.config.active_project)
            if self.config.active_project
            else "__global__"
        )
        self._home_log_histories: dict[str, list[str]] = {
            self._home_log_scope: self._home_log_history,
        }
        self._last_ci_report: dict | None = None
        self._last_ci_link: str | None = None
        self._ci_check_target: str | None = None
        self._pending_memory_candidates: Path | None = None
        self._pending_memory_link: str | None = None
        self._memory_work_root: Path | None = None
        self._memory_work_candidates_path: Path | None = None
        self._agent_prompt_expanded = False
        self._agent_prompt_saved_title: str | None = None
        self._home_guide_expanded = False
        self._rosetta_eject_expanded = False
        self._rosetta_eject_project_names: dict[str, str] = {}
        self._dashboard_tab = 0
        self._home_scroll_y = 0.0
        self.notebook: ttk.Notebook | None = None
        self.controls_last = tk.StringVar(
            master=root,
            value="Pick the active project on Projects, then use these controls.",
        )
        self.controls_active_label = tk.StringVar(master=root, value="")
        self._controls_link_key = ""
        self._header_detail_label: tk.Label | None = None
        self._status_value_labels: dict[str, tk.Label] = {}
        self._home_canvas: tk.Canvas | None = None

        root.title("Hive Planner")
        root.geometry("920x680")
        root.minsize(780, 580)
        root.configure(bg=COLORS["bg"])
        apply_ttk_style(root)

        self.container = tk.Frame(root, bg=COLORS["bg"])
        self.container.pack(fill="both", expand=True)

        if self._is_portable_mode() and not self.setup.unified_handoff_ready:
            self._run_bg(lambda: run_portable_bootstrap(force=False), self._portable_bootstrap_done)
        elif not self.config.onboarding_complete:
            self._show_onboarding()
        else:
            self._show_dashboard()

    def _is_portable_mode(self) -> bool:
        from hive_planner.runtime_paths import is_portable_runtime

        return is_portable_runtime()

    def _portable_bootstrap_done(self, result: dict) -> None:
        self.config = load_config()
        self.setup = get_setup_status(self.config)
        if not result.get("ok"):
            detail = result.get("detail") or result.get("error") or "Portable bootstrap failed"
            messagebox.showwarning("Portable setup", detail)
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

    def _project_done_callback(self, label: str, on_done):
        """Deliver a background result only while its originating project is active."""
        origin = self._active_link_key()

        def scoped_done(result) -> None:
            if origin and origin != self._active_link_key():
                self._remember_home_log_for_scope(
                    origin,
                    f"{label} finished after switching profiles; result retained for this project.",
                )
                return
            on_done(result)

        return scoped_done

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
            card_title(intro, "What you get" if not self._is_portable_mode() else "Portable edition")
            intro_text = (
                "• Bootstrap Hive projects with Delta planning layout\n"
                "• Unified agent handoff: Spec Kit + Continual Learning (symbiotic)\n"
                "• Run ci-check health gates before handoff\n"
                "• Sync impact maps and open projects in Cursor"
            )
            if self._is_portable_mode():
                intro_text = (
                    "Self-contained Windows app — no Python install required.\n\n"
                    "• Spec Kit + Continual Learning vendored overlays deploy beside this exe\n"
                    "• Link or create Cursor projects from the dashboard\n"
                    "• Deploy agent handoff copies the same unified bundle into your projects"
                )
            tk.Label(
                intro,
                text=intro_text,
                justify="left",
                font=FONT,
                bg=COLORS["card"],
                fg=COLORS["muted"],
            ).pack(anchor="w", padx=12, pady=(0, 12))
            ready = self.setup.python_ok and self.setup.hive_installed and self.setup.hive_root_ok
            if self._is_portable_mode():
                ready = ready and self.setup.unified_handoff_ready
            if ready:
                primary_button(actions, "Open dashboard →", self._finish_onboarding)
            else:
                primary_button(actions, "Get started →", lambda: self._advance_wizard(1))
        elif self._wizard_step == 1:
            self.setup = get_setup_status(self.config)
            status_card = card(body)
            card_title(status_card, "Environment")
            status_rows = [
                ("Python", self.setup.python_ok, self.setup.python_version),
                ("Hive installed", self.setup.hive_installed, self.setup.hive_version or "missing"),
            ]
            if self._is_portable_mode():
                status_rows = [
                    ("Runtime", self.setup.python_ok, self.setup.python_version),
                    ("Hive Planner", self.setup.hive_installed, self.setup.hive_version or "bundled"),
                    (
                        "Spec Kit + CL",
                        self.setup.unified_handoff_ready,
                        self.setup.unified_handoff_detail,
                    ),
                ]
            status_rows.append(
                ("Git", self.setup.git_available, "available" if self.setup.git_available else "optional")
            )
            for label, ok, detail in status_rows:
                row = tk.Frame(status_card, bg=COLORS["card"])
                row.pack(fill="x", padx=12, pady=4)
                tk.Label(row, text=label, width=16, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
                badge = COLORS["success"] if ok else COLORS["warning"]
                tk.Label(row, text=detail, bg=COLORS["card"], fg=badge, font=FONT_BOLD).pack(side="left")
            secondary_button(actions, "← Back", lambda: self._advance_wizard(0))
            if not self._is_portable_mode():
                secondary_button(
                    actions,
                    "Scan for Python",
                    self._on_scan_python,
                    tooltip="Search this computer for a suitable Python installation.",
                )
            install_label = "Verify install" if self._is_portable_mode() else "Install / update"
            install_tip = (
                "Make sure the built-in planning and memory tools are installed next to this app."
                if self._is_portable_mode()
                else "Install or update Hive Planner from the folder you chose above."
            )
            secondary_button(actions, install_label, self._on_install, tooltip=install_tip)
            ready = self.setup.python_ok and self.setup.hive_installed and self.setup.hive_root_ok
            if self._is_portable_mode():
                ready = ready and self.setup.unified_handoff_ready
            if ready:
                primary_button(actions, "Open dashboard →", self._finish_onboarding)
            else:
                primary_button(actions, "Continue →", lambda: self._advance_wizard(2))
        elif self._wizard_step == 2 and self._is_portable_mode():
            paths_card = card(body)
            card_title(paths_card, "Portable folder")
            tk.Label(
                paths_card,
                text=f"App folder (settings + deployed overlays):\n{self.setup.hive_root}",
                justify="left",
                wraplength=640,
                bg=COLORS["card"],
                fg=COLORS["muted"],
                font=FONT,
            ).pack(anchor="w", padx=12, pady=(0, 12))
            tk.Label(
                paths_card,
                text="config\\config.json stores linked projects.\n"
                ".hive\\spec-kit and .cursor\\plugins\\hive-continual-learning are deployed here for project handoff.",
                justify="left",
                wraplength=640,
                bg=COLORS["card"],
                fg=COLORS["muted"],
                font=FONT_SUBTITLE,
            ).pack(anchor="w", padx=12, pady=(0, 12))
            secondary_button(actions, "← Back", lambda: self._advance_wizard(1))
            primary_button(actions, "Continue →", lambda: self._advance_wizard(3))
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
        self.setup = get_setup_status(self.config)
        if self._is_portable_mode() and not self.setup.unified_handoff_ready:
            messagebox.showwarning(
                "Setup incomplete",
                "Spec Kit + Continual Learning are not deployed yet.\n\n"
                "Use Verify install on the Setup step, then try again.",
            )
            return
        self.config.onboarding_complete = True
        save_config(self.config)
        self._show_dashboard()

    def _capture_dashboard_view(self) -> None:
        notebook = getattr(self, "notebook", None)
        if notebook is not None:
            try:
                if notebook.winfo_exists():
                    self._dashboard_tab = int(notebook.index(notebook.select()))
            except (tk.TclError, ValueError, TypeError):
                pass
        canvas = getattr(self, "_home_canvas", None)
        if canvas is not None:
            try:
                if canvas.winfo_exists():
                    self._home_scroll_y = float(canvas.yview()[0])
            except (tk.TclError, ValueError, TypeError, IndexError):
                pass

    def _restore_dashboard_view(self) -> None:
        notebook = getattr(self, "notebook", None)
        if notebook is not None:
            try:
                tabs = notebook.tabs()
                if tabs and 0 <= self._dashboard_tab < len(tabs):
                    notebook.select(self._dashboard_tab)
            except tk.TclError:
                pass
        # Defer scroll restore until canvas scrollregion is laid out (and Home may be mapped).
        try:
            self.root.after_idle(self._restore_home_scroll)
        except tk.TclError:
            self._restore_home_scroll()

    def _restore_home_scroll(self) -> None:
        canvas = getattr(self, "_home_canvas", None)
        if canvas is None or not self._home_scroll_y:
            return
        try:
            if canvas.winfo_exists():
                canvas.yview_moveto(self._home_scroll_y)
        except (tk.TclError, ValueError, TypeError):
            return

    def _on_dashboard_tab_changed(self, _event=None) -> None:
        notebook = getattr(self, "notebook", None)
        if notebook is None:
            return
        try:
            self._dashboard_tab = int(notebook.index(notebook.select()))
        except (tk.TclError, ValueError, TypeError):
            pass

    def _dashboard_alive(self) -> bool:
        notebook = getattr(self, "notebook", None)
        if notebook is None:
            return False
        try:
            return bool(notebook.winfo_exists())
        except tk.TclError:
            return False

    def _header_detail_text(self) -> str:
        proj = self.config.active_project
        if not proj:
            return "No project selected"
        proj_label = _linked_display_name(proj)
        profile_label = self._active_profile_label()
        if profile_label:
            return f"Active: {proj_label}  ·  profile: {profile_label}"
        return f"Active: {proj_label}"

    def _status_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = [
            ("Hive", self.setup.hive_version or "not installed"),
            ("Profile", self._active_profile_label() or "—"),
            ("Handoff", self._active_handoff_label()),
            ("CL runtime", self._active_cl_runtime_label()),
        ]
        if self.setup.portable_mode:
            items.append(("Bundle", "ready ✓" if self.setup.unified_handoff_ready else "repair"))
        items.extend(
            [
                ("Feature", self._active_feature_label()),
                ("Wiring", self._wiring_audit_label()),
            ]
        )
        return items

    def _sync_pending_memory_for_active(self) -> None:
        active_norm = (
            normalize_project_path(self.config.active_project)
            if self.config.active_project
            else ""
        )
        pending_link = getattr(self, "_pending_memory_link", None)
        pending_norm = normalize_project_path(pending_link) if pending_link else ""
        if pending_norm and pending_norm != active_norm:
            self._clear_memory_work_context()

    def _active_link_key(self) -> str:
        if not self.config.active_project:
            return ""
        return normalize_project_path(self.config.active_project)

    def _sync_ci_report_for_active(self) -> None:
        """Drop health-check results that belong to a different active project."""
        active = self._active_link_key()
        last_link = getattr(self, "_last_ci_link", None)
        last_n = normalize_project_path(last_link) if last_link else ""
        last_report = getattr(self, "_last_ci_report", None)
        if not last_report:
            self._last_ci_link = None
            self._last_ci_report = None
            return
        if last_n and active and last_n == active:
            return
        # Active switched (or cleared) — do not show another project's Latest ci-check.
        self._last_ci_report = None
        self._last_ci_link = None

    def _update_header_detail(self) -> None:
        label = getattr(self, "_header_detail_label", None)
        if label is None:
            return
        try:
            label.configure(text=self._header_detail_text())
        except tk.TclError:
            return

    def _update_status_cards(self) -> None:
        labels = getattr(self, "_status_value_labels", None) or {}
        for title, value in self._status_items():
            label = labels.get(title)
            if label is None:
                continue
            try:
                label.configure(text=value)
            except tk.TclError:
                continue

    def _soft_refresh_dashboard(self, *, reload_config: bool = True) -> None:
        """Update live dashboard widgets without destroying the notebook (no blink / tab reset).

        When reload_config is False, keep the in-memory LauncherConfig (preserves unsaved
        Settings StringVars) and only re-paint Home from the current active project.
        """
        if reload_config:
            self.config = load_config()
        self.setup = get_setup_status(self.config)
        self._sync_home_log_for_active()
        self._sync_pending_memory_for_active()
        self._sync_ci_report_for_active()
        self._update_header_detail()
        self._update_status_cards()
        self._sync_controls_for_active()
        self._sync_rosetta_eject_for_active()
        if hasattr(self, "recent_list"):
            try:
                self._populate_recent_list()
            except tk.TclError:
                pass
        self._populate_ci_list(self._last_ci_report)
        self._flush_pending_home_log()

    def _sync_new_project_defaults(self) -> None:
        """Keep Projects → New project comboboxes aligned with saved Settings defaults."""
        try:
            if hasattr(self, "new_profile"):
                self.new_profile.set(self.config.default_profile)
            if hasattr(self, "new_agent_handoff"):
                self.new_agent_handoff.set(self.config.default_agent_handoff)
        except tk.TclError:
            return

    def _show_dashboard(self) -> None:
        self._capture_dashboard_view()
        saved_tab = self._dashboard_tab
        saved_scroll = self._home_scroll_y
        self._clear_container()
        self.config = load_config()
        self.setup = get_setup_status(self.config)
        self._sync_home_log_for_active()
        self._sync_pending_memory_for_active()
        self._sync_ci_report_for_active()
        self._status_value_labels = {}
        self._header_detail_label = None
        self._home_canvas = None

        header = tk.Frame(self.container, bg=COLORS["bg"])
        header.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(header, text="Hive Planner", font=FONT_TITLE, bg=COLORS["bg"], fg=COLORS["fg"]).pack(side="left")
        self._header_detail_label = tk.Label(
            header,
            text=self._header_detail_text(),
            font=FONT_SUBTITLE,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        )
        self._header_detail_label.pack(side="right", padx=8)

        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True, padx=16, pady=8)
        self.notebook = notebook
        notebook.bind("<<NotebookTabChanged>>", self._on_dashboard_tab_changed)

        home = tk.Frame(notebook, bg=COLORS["bg"])
        controls = tk.Frame(notebook, bg=COLORS["bg"])
        projects = tk.Frame(notebook, bg=COLORS["bg"])
        settings = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(home, text="Home")
        notebook.add(controls, text="Controls")
        notebook.add(projects, text="Projects")
        notebook.add(settings, text="Settings")

        self._build_home_tab(home)
        self._build_controls_tab(controls)
        self._build_projects_tab(projects)
        self._build_settings_tab(settings)

        self._dashboard_tab = saved_tab
        self._home_scroll_y = saved_scroll
        self._restore_dashboard_view()

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
        if isinstance(result, dict) and result.get("cancelled"):
            self._queue_home_log(self._result_detail(result))
            self._clear_memory_work_context()
            self._refresh_home_dashboard()
            return
        if isinstance(result, dict) and self._is_memory_propose_result(result):
            self._deliver_memory_propose_result(result, stale=True)
            return
        if isinstance(result, dict) and result.get("mode") in ("sources", "import", "translate"):
            self._queue_cartridge_result_log(result)
            self._queue_home_log("(Cartridge load finished after dashboard refresh — output preserved above.)")
            self._refresh_home_dashboard()
            return
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
        self._queue_home_log(message)
        self._refresh_home_dashboard()

    def _home_log_scope_key(self) -> str:
        config = getattr(self, "config", None)
        if config is not None and config.active_project:
            return normalize_project_path(config.active_project)
        return "__global__"

    def _remember_home_log_for_scope(self, scope: str, text: str) -> None:
        histories = getattr(self, "_home_log_histories", None)
        if histories is None:
            histories = {}
            self._home_log_histories = histories
        current_scope = getattr(self, "_home_log_scope", self._home_log_scope_key())
        active_scope = self._home_log_scope_key()
        if scope == active_scope:
            self._remember_home_log(text)
            return
        if scope == current_scope:
            histories[scope] = getattr(self, "_home_log_history", [])
        history = histories.setdefault(scope, [])
        history.append(text)
        overflow = len(history) - 500
        if overflow > 0:
            del history[:overflow]

    def _sync_home_log_for_active(self) -> None:
        """Switch Output history to the newly active project without mixing logs."""
        scope = self._home_log_scope_key()
        current_scope = getattr(self, "_home_log_scope", None)
        histories = getattr(self, "_home_log_histories", None)
        if histories is None:
            histories = {}
            self._home_log_histories = histories
        if current_scope is None:
            self._home_log_scope = scope
            histories[scope] = getattr(self, "_home_log_history", [])
            return
        if current_scope == scope:
            histories[scope] = getattr(self, "_home_log_history", [])
            return

        histories[current_scope] = list(getattr(self, "_home_log_history", []) or [])
        self._home_log_scope = scope
        self._home_log_history = list(histories.get(scope, []))
        histories[scope] = self._home_log_history
        self._pending_home_log = []

        log = getattr(self, "home_log", None)
        if log is None:
            return
        try:
            log.configure(state="normal")
            log.delete("1.0", "end")
            log.configure(state="disabled")
            self._restore_home_log_history()
        except (tk.TclError, AttributeError):
            return

    def _remember_home_log(self, text: str) -> None:
        self._sync_home_log_for_active()
        if not hasattr(self, "_home_log_history") or self._home_log_history is None:
            self._home_log_history = []
            self._home_log_histories[self._home_log_scope_key()] = self._home_log_history
        self._home_log_history.append(text)
        overflow = len(self._home_log_history) - 500
        if overflow > 0:
            del self._home_log_history[:overflow]

    def _restore_home_log_history(self) -> None:
        if not hasattr(self, "home_log"):
            return
        history = getattr(self, "_home_log_history", None) or []
        try:
            for line in history:
                self._append_log(self.home_log, line)
        except tk.TclError:
            return

    def _flush_pending_home_log(self) -> None:
        if not self._pending_home_log or not hasattr(self, "home_log"):
            return
        try:
            for line in self._pending_home_log:
                self._append_log(self.home_log, line)
        except tk.TclError:
            return
        self._pending_home_log.clear()

    def _queue_home_log(self, message: str) -> None:
        text = str(message).rstrip()
        if not text:
            return
        if not hasattr(self, "_pending_home_log") or self._pending_home_log is None:
            self._pending_home_log = []
        self._remember_home_log(text)
        self._pending_home_log.append(text)

    def _emit_home_log(self, message: str) -> None:
        """Write to Output now and retain in history for the next dashboard rebuild."""
        text = str(message).rstrip()
        if not text:
            return
        self._remember_home_log(text)
        if hasattr(self, "home_log"):
            try:
                self._append_log(self.home_log, text)
                return
            except tk.TclError:
                pass
        if not hasattr(self, "_pending_home_log") or self._pending_home_log is None:
            self._pending_home_log = []
        self._pending_home_log.append(text)

    def _queue_handoff_repair_warning(self, state: BootstrapState) -> None:
        if not state.needs_handoff_repair:
            return
        missing_preview = ", ".join(state.handoff_missing[:3])
        if len(state.handoff_missing) > 3:
            missing_preview += f", +{len(state.handoff_missing) - 3} more"
        self._queue_home_log(
            f"Warning: unified handoff incomplete — missing: {missing_preview}. "
            "Use Deploy agent handoff or re-link with repair.",
        )

    def _refresh_home_dashboard(self, *, reload_config: bool = True) -> None:
        """Refresh dashboard state without blinking when the notebook is already open."""
        if self._dashboard_alive():
            self._soft_refresh_dashboard(reload_config=reload_config)
            return
        self._show_dashboard()

    def _start_home_action(self, message: str) -> None:
        """Show an in-progress line immediately; keep it in history across full rebuilds."""
        text = str(message).rstrip()
        if not text:
            return
        self._remember_home_log(text)
        self._set_controls_last(text)
        if hasattr(self, "home_log"):
            try:
                self._append_log(self.home_log, text)
                return
            except tk.TclError:
                pass
        if not hasattr(self, "_pending_home_log") or self._pending_home_log is None:
            self._pending_home_log = []
        self._pending_home_log.append(text)

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
        self._home_canvas = canvas

        self._build_home_guide_card(body)
        self._build_agent_prompt_templates_card(body)
        self._build_rosetta_eject_card(body)

        stats = card(body)
        card_title(stats, "Status")
        row = tk.Frame(stats, bg=COLORS["card"])
        row.pack(fill="x", padx=12, pady=(0, 12))
        self._status_value_labels = {}
        for title, value in self._status_items():
            cell = tk.Frame(row, bg=COLORS["secondary"], padx=12, pady=10)
            cell.pack(side="left", fill="x", expand=True, padx=4)
            value_label = tk.Label(
                cell,
                text=value,
                font=("Segoe UI", 14, "bold"),
                bg=COLORS["secondary"],
                fg=COLORS["primary"],
            )
            value_label.pack()
            self._status_value_labels[title] = value_label
            tk.Label(cell, text=title, font=FONT_SUBTITLE, bg=COLORS["secondary"], fg=COLORS["muted"]).pack()

        actions = tk.Frame(body, bg=COLORS["bg"])
        actions.pack(fill="x", padx=16, pady=8)
        primary_button(
            actions,
            "Run health check",
            self._on_ci_check,
            tooltip="Check that plans, specs, and code maps match before you hand work to an AI agent.",
        )
        secondary_button(
            actions,
            "Open in Cursor",
            self._on_open_cursor,
            tooltip="Open your active linked project in the Cursor editor.",
        )
        secondary_button(
            actions,
            "Sync impact maps",
            self._on_map_sync,
            tooltip="Refresh the lists that link source files to tests so you know what to re-test after edits.",
        )
        secondary_button(
            actions,
            "Deploy agent handoff",
            self._on_deploy_agent_handoff,
            tooltip="Copy planning and memory tools into your project so AI agents can follow your workflow.",
        )
        secondary_button(
            actions,
            "Loop controls",
            self._on_open_loop_controls,
            tooltip="Open the Controls tab: one Run command for bug hunt, implementation loop, and agnostic loop on the active repo.",
        )
        secondary_button(
            actions,
            "Load cartridge…",
            self._on_load_cartridge,
            tooltip="Open the dialog to add reference files, turn a research note into drafts, or import a cartridge folder.",
        )
        secondary_button(
            actions,
            "Open in Explorer",
            self._on_explore,
            tooltip="Open your active project folder in Windows File Explorer.",
        )

        source_actions = tk.Frame(body, bg=COLORS["bg"])
        source_actions.pack(fill="x", padx=16, pady=(0, 8))
        secondary_button(
            source_actions,
            "Load Sources…",
            self._on_load_sources,
            tooltip="Add PDF or text files (notes, papers, specs) for AI agents to reference while planning.",
        )

        handoff_actions = tk.Frame(body, bg=COLORS["bg"])
        handoff_actions.pack(fill="x", padx=16, pady=(0, 8))
        secondary_button(
            handoff_actions,
            "Check wiring audit",
            self._on_wiring_audit_check,
            tooltip="See whether required integration checks were completed before agent handoff.",
        )
        secondary_button(
            handoff_actions,
            "Record wiring audit…",
            self._on_wiring_audit_record,
            tooltip="Mark integration checks as done after you verify agents and tools are connected correctly.",
        )
        secondary_button(
            handoff_actions,
            "Promote memory…",
            self._on_agents_propose,
            tooltip="Autonomously route and apply candidates to AGENTS.md (auto-splits long bullets; no preview).",
        )
        secondary_button(
            handoff_actions,
            "Apply memory…",
            self._on_agents_apply,
            tooltip="Re-run autonomous apply on a candidates file (same routing as Promote memory).",
        )

        verify_actions = tk.Frame(body, bg=COLORS["bg"])
        verify_actions.pack(fill="x", padx=16, pady=(0, 8))
        secondary_button(
            verify_actions,
            "Verify vendor pins",
            self._on_unified_verify,
            tooltip="Confirm bundled planning tool versions match what this Hive release expects.",
        )
        secondary_button(
            verify_actions,
            "Scan legacy deployment",
            self._on_legacy_deployment_scan,
            tooltip="Find older project setups that may need upgrading to the current agent handoff format.",
        )
        secondary_button(
            verify_actions,
            "Set CL runtime…",
            self._on_set_cl_runtime,
            tooltip="Choose how AI memory runs: inside Cursor, or through a separate command-line tool.",
        )
        secondary_button(
            verify_actions,
            "Migrate marketplace CL…",
            self._on_cl_migrate,
            tooltip="Move learned facts from the Cursor plugin into your project's own memory file.",
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
        self._populate_ci_list(self._last_ci_report)
        self._bind_page_wheel(body, canvas)
        self._restore_home_log_history()
        self._pending_home_log.clear()

    LOOP_CONTROL_COMMANDS = {
        "Bug hunt": ("Enable", "Check install"),
        "Implementation loop": (
            "Enable",
            "Check pack",
            "Status",
            "Start",
            "Handoff",
            "Check",
            "Accept",
            "Commit",
        ),
        "Agnostic loop": (
            "Enable",
            "Check install",
            "Rewards",
            "Status",
            "Arm",
            "Begin",
            "Review",
            "Observe hit",
            "Observe miss",
            "Choose",
        ),
    }

    def _build_controls_tab(self, parent: tk.Frame) -> None:
        from hive_planner.bug_hunt import DEFAULT_ITERATIONS
        from hive_planner.implementation_loop import PACK_1, PACK_4

        body, canvas = self._scrollable_tab(parent)
        panel = card(body)
        card_title(panel, "Loop command — active repo")
        tk.Label(
            panel,
            textvariable=self.controls_active_label,
            wraplength=760,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", padx=12, pady=(0, 8))
        tk.Label(
            panel,
            textvariable=self.controls_last,
            wraplength=760,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["fg"],
            font=FONT,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        if not hasattr(self, "controls_loop"):
            self.controls_loop = tk.StringVar(value="Implementation loop")
        if not hasattr(self, "controls_command"):
            self.controls_command = tk.StringVar(value="Status")
        if not hasattr(self, "controls_bug_iterations"):
            self.controls_bug_iterations = tk.StringVar(value=str(DEFAULT_ITERATIONS))
        if not hasattr(self, "controls_impl_pack"):
            self.controls_impl_pack = tk.StringVar(value=PACK_1)
        if not hasattr(self, "controls_impl_feature"):
            feature = self._active_feature_label()
            self.controls_impl_feature = tk.StringVar(value="" if feature == "—" else feature)
        if not hasattr(self, "controls_impl_role"):
            self.controls_impl_role = tk.StringVar(value="coder")
        if not hasattr(self, "controls_impl_allow_dirty"):
            self.controls_impl_allow_dirty = tk.BooleanVar(value=False)
        if not hasattr(self, "controls_impl_force_feature"):
            self.controls_impl_force_feature = tk.BooleanVar(value=False)
        if not hasattr(self, "controls_impl_continue_cap"):
            self.controls_impl_continue_cap = tk.BooleanVar(value=False)
        if not hasattr(self, "controls_agn_reward"):
            self.controls_agn_reward = tk.StringVar(value="inspect")
        if not hasattr(self, "controls_agn_cycles"):
            self.controls_agn_cycles = tk.StringVar(value="1")
        if not hasattr(self, "controls_agn_note"):
            self.controls_agn_note = tk.StringVar(value="")
        if not hasattr(self, "controls_agn_open"):
            self.controls_agn_open = tk.StringVar(value="")
        if not hasattr(self, "controls_agn_arm_choose"):
            self.controls_agn_arm_choose = tk.BooleanVar(value=False)

        loop_row = tk.Frame(panel, bg=COLORS["card"])
        loop_row.pack(fill="x", padx=12, pady=4)
        tk.Label(loop_row, text="Loop", width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
        loop_box = ttk.Combobox(
            loop_row,
            textvariable=self.controls_loop,
            values=tuple(self.LOOP_CONTROL_COMMANDS),
            state="readonly",
            width=28,
        )
        loop_box.pack(side="left", fill="x", expand=True)
        loop_box.bind("<<ComboboxSelected>>", self._on_controls_loop_changed)

        cmd_row = tk.Frame(panel, bg=COLORS["card"])
        cmd_row.pack(fill="x", padx=12, pady=4)
        tk.Label(cmd_row, text="Command", width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
        self.controls_command_box = ttk.Combobox(
            cmd_row,
            textvariable=self.controls_command,
            values=self.LOOP_CONTROL_COMMANDS[self.controls_loop.get()],
            state="readonly",
            width=28,
        )
        self.controls_command_box.pack(side="left", fill="x", expand=True)
        self._sync_controls_command_choices()

        self._field(
            panel,
            "Iterations",
            self.controls_bug_iterations,
            tooltip="Bug hunt: find/fix cycles written into the installed command (1–200).",
        )
        pack_row = tk.Frame(panel, bg=COLORS["card"])
        pack_row.pack(fill="x", padx=12, pady=4)
        tk.Label(pack_row, text="Pack", width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
        ttk.Combobox(
            pack_row,
            textvariable=self.controls_impl_pack,
            values=[PACK_1, PACK_4],
            state="readonly",
            width=28,
        ).pack(side="left", fill="x", expand=True)
        self._field(panel, "Feature id", self.controls_impl_feature, tooltip="Implementation loop. Blank uses AGENTS.md Active feature.")
        role_row = tk.Frame(panel, bg=COLORS["card"])
        role_row.pack(fill="x", padx=12, pady=4)
        tk.Label(role_row, text="Role", width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
        ttk.Combobox(
            role_row,
            textvariable=self.controls_impl_role,
            values=["coder", "checker", "reviewer", "coordinator"],
            state="readonly",
            width=28,
        ).pack(side="left", fill="x", expand=True)
        self._field(panel, "Reward", self.controls_agn_reward, tooltip="Agnostic loop catalog reward.")
        self._field(panel, "Cycles", self.controls_agn_cycles, tooltip="Agnostic loop arm / choose cycles.")
        self._field(panel, "Review note", self.controls_agn_note, tooltip="Agnostic loop review note.")
        self._field(panel, "Choose open", self.controls_agn_open, tooltip="Agnostic choose, e.g. inspect=4,fill=1.")
        flags = tk.Frame(panel, bg=COLORS["card"])
        flags.pack(fill="x", padx=12, pady=4)
        tk.Checkbutton(
            flags,
            text="Allow dirty start",
            variable=self.controls_impl_allow_dirty,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            selectcolor=COLORS["card"],
            activebackground=COLORS["card"],
            font=FONT,
        ).pack(side="left", padx=(0, 12))
        tk.Checkbutton(
            flags,
            text="Force feature",
            variable=self.controls_impl_force_feature,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            selectcolor=COLORS["card"],
            activebackground=COLORS["card"],
            font=FONT,
        ).pack(side="left", padx=(0, 12))
        tk.Checkbutton(
            flags,
            text="Continue after cap",
            variable=self.controls_impl_continue_cap,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            selectcolor=COLORS["card"],
            activebackground=COLORS["card"],
            font=FONT,
        ).pack(side="left", padx=(0, 12))
        tk.Checkbutton(
            flags,
            text="Arm after choose",
            variable=self.controls_agn_arm_choose,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            selectcolor=COLORS["card"],
            activebackground=COLORS["card"],
            font=FONT,
        ).pack(side="left")

        run_row = tk.Frame(panel, bg=COLORS["card"])
        run_row.pack(fill="x", padx=12, pady=(8, 12))
        primary_button(
            run_row,
            "Run",
            self._on_controls_run,
            tooltip="Run the selected loop command on the active repo.",
        )

        self._sync_controls_for_active()
        self._bind_page_wheel(body, canvas)

    def _controls_active_caption(self) -> str:
        active = self.config.active_project or "No project linked. Open Projects and set an active folder."
        return f"Pick a loop and one command, then Run. Same functions as the CLI on:\n{active}"

    def _sync_controls_for_active(self) -> None:
        """Keep Controls pointed at the live active repo after a project switch."""
        if hasattr(self, "controls_active_label"):
            self.controls_active_label.set(self._controls_active_caption())
        key = self._active_link_key()
        last = getattr(self, "_controls_link_key", None)
        if last == key:
            return
        self._controls_link_key = key
        if not hasattr(self, "controls_impl_feature"):
            return
        feature = self._active_feature_label() if key else ""
        self.controls_impl_feature.set("" if feature == "—" else feature)

    def _sync_controls_command_choices(self) -> None:
        loop = str(self.controls_loop.get() if hasattr(self, "controls_loop") else "Implementation loop")
        choices = self.LOOP_CONTROL_COMMANDS.get(loop) or self.LOOP_CONTROL_COMMANDS["Implementation loop"]
        box = getattr(self, "controls_command_box", None)
        if box is not None:
            box.configure(values=choices)
        current = str(self.controls_command.get() if hasattr(self, "controls_command") else "")
        if current not in choices:
            self.controls_command.set(choices[0])

    def _on_controls_loop_changed(self, _event=None) -> None:
        self._sync_controls_command_choices()

    def _on_open_loop_controls(self) -> None:
        notebook = self.notebook
        if notebook is None:
            return
        try:
            for index, tab in enumerate(notebook.tabs()):
                if str(notebook.tab(tab, "text")) == "Controls":
                    notebook.select(tab)
                    self._dashboard_tab = index
                    return
        except tk.TclError:
            return

    @classmethod
    def resolved_loop_command(cls, loop: str, command: str) -> tuple[str, str] | None:
        loop_name = str(loop or "")
        cmd = str(command or "")
        choices = cls.LOOP_CONTROL_COMMANDS.get(loop_name)
        if not choices or cmd not in choices:
            return None
        return loop_name, cmd

    def _on_controls_run(self) -> None:
        loop = str(self.controls_loop.get() if hasattr(self, "controls_loop") else "")
        command = str(self.controls_command.get() if hasattr(self, "controls_command") else "")
        resolved = self.resolved_loop_command(loop, command)
        if resolved is None:
            messagebox.showwarning(
                "Loop command",
                "Pick a loop and a command that belong together, then Run.",
            )
            self._sync_controls_command_choices()
            return
        loop, command = resolved
        if loop == "Bug hunt":
            if command == "Enable":
                self._on_bug_hunt_install()
            else:
                self._on_bug_hunt_status()
            return
        if loop == "Implementation loop":
            actions = {
                "Enable": lambda: self._on_implementation_loop_install(from_controls=True),
                "Check pack": self._on_implementation_loop_peek_pack,
                "Status": lambda: self._on_implementation_loop_status(from_controls=True),
                "Start": lambda: self._on_implementation_loop_start(from_controls=True),
                "Handoff": lambda: self._on_implementation_loop_handoff(from_controls=True),
                "Check": self._on_implementation_loop_check,
                "Accept": lambda: self._on_implementation_loop_accept(from_controls=True),
                "Commit": self._on_implementation_loop_commit,
            }
            handler = actions.get(command)
            if handler:
                handler()
            return
        if loop == "Agnostic loop":
            actions = {
                "Enable": self._on_agnostic_loop_install,
                "Check install": self._on_agnostic_loop_peek,
                "Rewards": self._on_agnostic_loop_rewards,
                "Status": self._on_agnostic_loop_status,
                "Arm": self._on_agnostic_loop_arm,
                "Begin": self._on_agnostic_loop_begin,
                "Review": self._on_agnostic_loop_review,
                "Observe hit": lambda: self._on_agnostic_loop_observe(True),
                "Observe miss": lambda: self._on_agnostic_loop_observe(False),
                "Choose": self._on_agnostic_loop_choose,
            }
            handler = actions.get(command)
            if handler:
                handler()

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
        primary_button(
            hub_actions,
            "Open in Cursor",
            self._on_open_cursor,
            tooltip="Open the active linked project in Cursor.",
        )
        secondary_button(
            hub_actions,
            "Add link…",
            self._on_link_workspace,
            tooltip="Connect a folder you already use in Cursor to Hive Planner.",
        )

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
        primary_button(
            btn_row,
            "Create project",
            self._on_create_project,
            tooltip="Create a new project folder with Hive planning templates and optional Git setup.",
        )

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
        primary_button(
            btn_row2,
            "Add link…",
            self._on_link_workspace,
            tooltip="Add an existing folder to Hive's linked workspace list.",
        )
        secondary_button(
            btn_row2,
            "Set as active",
            self._on_select_recent,
            tooltip="Make the selected folder the project Home uses for health checks and actions.",
        )
        secondary_button(
            btn_row2,
            "Remove link",
            self._on_remove_recent,
            tooltip="Remove the selected folder from Hive's list (does not delete files on disk).",
        )
        secondary_button(
            btn_row2,
            "Delete profile…",
            self._on_delete_profile,
            tooltip="Remove Hive planning files from the selected folder (use with care).",
        )

    def _build_settings_tab(self, parent: tk.Frame) -> None:
        form = card(parent)
        card_title(form, "Configuration")
        self.cfg_hive = tk.StringVar(value=str(self.config.normalized_hive_root()))
        self.cfg_python = tk.StringVar(value=self.config.python_executable)
        self.cfg_cursor = tk.StringVar(value=self.config.cursor_executable)
        self.cfg_profile = tk.StringVar(value=self.config.default_profile)
        self.cfg_agent_handoff = tk.StringVar(value=self.config.default_agent_handoff)
        portable = self.setup.portable_mode
        if portable:
            portable_card = card(parent)
            card_title(portable_card, "Portable runtime")
            bundle_status = self.setup.unified_handoff_detail or "unknown"
            tk.Label(
                portable_card,
                text=f"App folder:\n{self.setup.hive_root}\n\n"
                f"Unified handoff bundle: {bundle_status}",
                justify="left",
                wraplength=760,
                bg=COLORS["card"],
                fg=COLORS["muted"],
                font=FONT,
            ).pack(anchor="w", padx=12, pady=(0, 12))
        else:
            self._field(
                form,
                "Hive planner root",
                self.cfg_hive,
                browse=True,
                tooltip="Folder where Hive Planner is installed (contains pyproject.toml).",
                browse_tooltip="Browse to the Hive Planner install folder.",
            )
            self._field(
                form,
                "Python command",
                self.cfg_python,
                scan_python=True,
                tooltip="Command that runs Python for Hive (for example py -3.11).",
                scan_tooltip="Search this computer for Python 3.11 or newer.",
            )
        self._field(
            form,
            "Cursor executable",
            self.cfg_cursor,
            browse_exe=True,
            tooltip="Path to Cursor.exe. Leave blank and Hive will try to find it automatically.",
            browse_tooltip="Browse to Cursor.exe if automatic detection fails.",
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
            "Full = richer planning templates for new projects. Minimal = lighter, faster setup.",
        )
        profile_combo = ttk.Combobox(
            profile_row,
            textvariable=self.cfg_profile,
            values=["full", "minimal"],
            state="readonly",
            width=28,
        )
        profile_combo.pack(side="left", fill="x", expand=True)
        attach_combobox_tooltip(
            profile_combo,
            "Default template size when you create a new linked project.",
        )
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
            "Unified = install AI planning and memory tools with new projects. Off = skip that step.",
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
            "Default agent tool setup for new projects and when bootstrapping a workspace.",
        )
        btn_row = tk.Frame(form, bg=COLORS["card"])
        btn_row.pack(fill="x", padx=12, pady=(8, 12))
        primary_button(
            btn_row,
            "Save settings",
            self._on_save_settings,
            tooltip="Save these paths and defaults for next time you open Hive Planner.",
        )
        secondary_button(
            btn_row,
            "Verify install" if portable else "Install / update Hive",
            self._on_install,
            tooltip=(
                "Make sure built-in planning and memory tools are installed next to this app."
                if portable
                else "Install or update Hive Planner from the folder above."
            ),
        )
        secondary_button(
            btn_row,
            "Reset onboarding",
            self._on_reset_onboarding,
            tooltip="Show the welcome setup wizard again. Your links and saved settings are kept.",
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
                "Show or hide an extra window with technical log messages (for troubleshooting).",
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
                tooltip=browse_tooltip or "Browse to choose a folder on your computer.",
            )
        if browse_exe:
            secondary_button(
                row,
                "Browse…",
                lambda: self._browse_exe_into(variable),
                tooltip=browse_tooltip or "Browse to choose a program file (.exe).",
            )
        if scan_python:
            secondary_button(
                row,
                "Scan…",
                lambda: self._on_scan_python(variable),
                tooltip=scan_tooltip or "Search this computer for Python installations.",
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

    def _populate_recent_list(self, *, prefer_path: str | None = None) -> None:
        selected_path: str | None = None
        if prefer_path:
            selected_path = prefer_path
        else:
            try:
                current = self._selected_recent_path()
                if current is not None:
                    selected_path = str(current)
            except (tk.TclError, AttributeError, IndexError):
                selected_path = None

        self.recent_list.delete(0, "end")
        self._recent_project_paths.clear()
        active_norm = (
            normalize_project_path(self.config.active_project)
            if self.config.active_project
            else ""
        )
        active_index: int | None = None
        prefer_index: int | None = None
        prefer_norm = normalize_project_path(selected_path) if selected_path else ""
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
            idx = len(self._recent_project_paths)
            if is_active:
                active_index = idx
            if prefer_norm and normalize_project_path(path) == prefer_norm:
                prefer_index = idx
            self._recent_project_paths.append(path)
            self.recent_list.insert("end", label)
        self._update_recent_scrollbar()
        select_index = prefer_index if prefer_index is not None else active_index
        if select_index is not None:
            self.recent_list.selection_set(select_index)
            self.recent_list.see(select_index)

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
        # Display-only: never repair AGENTS.md / Rosetta during status refresh.
        summary = summarize_linked_project(Path(self.config.active_project), repair_agents=False)
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
        # Display-only: never repair project files while painting Home status.
        root, _repair = prepare_linked_project_root(
            Path(self.config.active_project),
            repair_agents=False,
        )
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
        self._start_home_action(f"Setting CL runtime to {selected}…")
        self._run_bg(
            lambda r=root, rt=selected: run_set_cl_runtime(r, rt),
            self._project_done_callback("CL runtime update", self._set_cl_runtime_done),
        )

    def _set_cl_runtime_done(self, result: dict) -> None:
        if self._is_bg_error(result) or not result.get("ok"):
            self._queue_home_log(self._result_detail(result))
            for hint in result.get("hints", []):
                self._queue_home_log(f"Tip: {hint}")
            self._refresh_home_dashboard()
            return
        runtime = result.get("cl_runtime", "")
        self._queue_home_log(f"Set cl_runtime={runtime} in .hive/project.json.")
        for hint in result.get("hints", []):
            self._queue_home_log(f"Tip: {hint}")
        self._refresh_home_dashboard()

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

    def _populate_ci_list(self, report: dict | None) -> None:
        if not hasattr(self, "ci_list"):
            return
        try:
            self.ci_list.delete(0, "end")
            if not report:
                return
            for step in report.get("steps", []):
                mark = "✓" if step.get("ok") else "✗"
                self.ci_list.insert("end", f"{mark}  {step.get('name')}: {step.get('detail')}")
        except tk.TclError:
            return

    def _queue_ci_check_log(self, report: dict, *, link: str | None = None) -> None:
        if self._is_bg_error(report):
            self._last_ci_report = None
            self._last_ci_link = None
            self._queue_home_log(self._result_detail(report))
            return
        self._last_ci_report = report
        link_n = normalize_project_path(link) if link else ""
        if not link_n:
            target = getattr(self, "_ci_check_target", None)
            link_n = (
                normalize_project_path(target) if target else self._active_link_key()
            ) or ""
        self._last_ci_link = link_n or None
        for step in report.get("steps", []):
            mark = "✓" if step.get("ok") else "✗"
            self._queue_home_log(f"  {mark}  {step.get('name')}: {step.get('detail')}")
        summary = "All checks passed." if report.get("ok") else "Some checks failed."
        self._queue_home_log(summary)
        repair = report.get("repair")
        if repair:
            self._queue_home_log(
                f"Repaired AGENTS.md — {repair.get('detail', 'updated Active feature')}."
            )
        for hint in report.get("hints", []):
            self._queue_home_log(f"Tip: {hint}")

    def _on_ci_check(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).", parent=self.root)
            return
        job_target = self._active_link_key() or normalize_project_path(str(root))
        self._ci_check_target = job_target
        self._start_home_action("Running ci-check…")
        # Stamp expected_link on the callback so overlapping jobs cannot overwrite
        # shared _ci_check_target and mis-attribute an older result.
        self._run_bg(
            lambda r=root: run_project_ci_check(r),
            lambda report, expected=job_target: self._ci_check_done(
                report, expected_link=expected
            ),
        )

    def _ci_check_done(self, report: dict, *, expected_link: str | None = None) -> None:
        expected_n = normalize_project_path(expected_link) if expected_link else ""
        if not expected_n:
            shared = getattr(self, "_ci_check_target", None)
            expected_n = normalize_project_path(shared) if shared else ""
        active_n = self._active_link_key()
        if expected_n and active_n and expected_n != active_n:
            self._remember_home_log_for_scope(
                expected_n,
                "Health check finished after switching profiles; discarded for the prior project.",
            )
            shared = getattr(self, "_ci_check_target", None)
            if shared and normalize_project_path(shared) == expected_n:
                self._ci_check_target = None
            return
        self._queue_ci_check_log(report, link=expected_n or None)
        shared = getattr(self, "_ci_check_target", None)
        if not shared or normalize_project_path(shared) == expected_n:
            self._ci_check_target = None
        if self._is_bg_error(report):
            messagebox.showerror("Health check", self._result_detail(report), parent=self.root)
        elif report.get("ok"):
            messagebox.showinfo("Health check", "All checks passed.", parent=self.root)
        else:
            messagebox.showwarning(
                "Health check",
                "Some checks failed — see Latest ci-check and Output below.",
                parent=self.root,
            )
        self._refresh_home_dashboard()

    def _on_wiring_audit_check(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        self._start_home_action("Checking wiring audit attestation…")
        self._run_bg(
            lambda r=root: run_wiring_audit_check(r),
            self._project_done_callback("Wiring audit check", self._wiring_audit_check_done),
        )

    def _wiring_audit_check_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        if result.get("skipped"):
            self._queue_home_log(result.get("detail", "Wiring audit not enforced."))
            self._refresh_home_dashboard()
            return
        detail = result.get("detail", "ok")
        mark = "ok" if result.get("ok") else "failed"
        self._queue_home_log(f"Wiring audit: {mark} — {detail}")
        for hint in result.get("hints", []):
            self._queue_home_log(f"Tip: {hint}")
        self._refresh_home_dashboard()

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
            self._start_home_action(f"Recording wiring audit (evidence: {evidence})…")
            self._run_bg(
                lambda r=root, e=evidence: run_wiring_audit_record(r, e),
                self._project_done_callback("Wiring audit record", self._wiring_audit_record_done),
            )

        btn_row = tk.Frame(dialog, bg=COLORS["bg"])
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        primary_button(btn_row, "Record", submit)
        secondary_button(btn_row, "Cancel", dialog.destroy)

    def _wiring_audit_record_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        if result.get("skipped"):
            self._queue_home_log(result.get("detail", "Wiring audit not enforced."))
            self._refresh_home_dashboard()
            return
        if result.get("recorded"):
            self._queue_home_log(f"Wrote {result['recorded']}")
        if result.get("ok"):
            self._queue_home_log("Wiring audit attestation valid.")
        else:
            self._queue_home_log(self._result_detail(result))
            for hint in result.get("hints", []):
                self._queue_home_log(f"Tip: {hint}")
        self._refresh_home_dashboard()

    def _set_pending_memory_candidates(self, root: Path, candidates: Path) -> None:
        self._pending_memory_candidates = candidates
        self._memory_work_root = root.resolve()
        self._memory_work_candidates_path = candidates
        link = self.config.active_project
        self._pending_memory_link = (
            normalize_project_path(link) if link else normalize_project_path(str(root))
        )

    def _clear_memory_work_context(self) -> None:
        self._pending_memory_candidates = None
        self._pending_memory_link = None
        self._memory_work_root = None
        self._memory_work_candidates_path = None

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

    def _memory_work_candidates(self) -> Path | None:
        work_root = getattr(self, "_memory_work_root", None)
        work_candidates = getattr(self, "_memory_work_candidates_path", None)
        if work_root and work_candidates:
            return work_candidates
        root = self._resolve_memory_work_root()
        if root is None:
            return None
        return self._pending_memory_for_root(root)

    def _resolve_memory_work_root(self) -> Path | None:
        work_root = getattr(self, "_memory_work_root", None)
        if work_root is not None:
            return work_root
        pending_link = getattr(self, "_pending_memory_link", None)
        pending_candidates = getattr(self, "_pending_memory_candidates", None)
        if pending_link and pending_candidates:
            root = resolve_linked_project_root(Path(pending_link))
            if root is not None:
                return root
        return self._active_linked_root()

    @staticmethod
    def _is_memory_propose_result(result: dict) -> bool:
        return isinstance(result.get("proposal_path"), str) and (
            "accepted" in result or "rejected" in result or result.get("all_rejected")
        )

    def _deliver_memory_propose_result(self, result: dict, *, stale: bool = False) -> None:
        if stale:
            self._queue_home_log(
                "Memory propose finished after dashboard refresh — showing result below.",
            )
        if not result.get("ok"):
            self._queue_home_log(self._result_detail(result))
            for hint in result.get("hints", []):
                self._queue_home_log(f"Tip: {hint}")
            root = self._resolve_memory_work_root()
            if root and result.get("proposal_path"):
                if result.get("accepted"):
                    self._show_memory_proposal_preview(result, root=root, allow_apply=False)
                elif result.get("rejected"):
                    self._show_memory_rejection_preview(result, root=root)
            self._refresh_home_dashboard()
            return
        self._queue_home_log(f"Wrote proposal: {result.get('proposal_path')}")
        accepted = result.get("accepted") or []
        rejected = result.get("rejected") or []
        if rejected:
            self._queue_home_log(f"Rejected {len(rejected)} candidate(s) — see proposal file.")
        if result.get("noop"):
            self._queue_home_log("AGENTS.md unchanged — accepted bullets already present.")
            self._clear_memory_work_context()
            self._refresh_home_dashboard()
            return
        if result.get("applied"):
            if accepted:
                self._queue_home_log(f"Accepted {len(accepted)} candidate(s).")
            self._queue_home_log("Applied to AGENTS.md.")
            for item in result.get("routing") or []:
                arm = item.get("arm")
                reason = item.get("reason")
                if arm or reason:
                    self._queue_home_log(f"  route/{arm}: {reason}")
            self._clear_memory_work_context()
            self._refresh_home_dashboard()
            return
        root = self._resolve_memory_work_root()
        candidates = self._memory_work_candidates()
        if accepted and root and candidates:
            if stale:
                self._queue_home_log(
                    "Memory promotion finished after dashboard refresh — "
                    "check AGENTS.md or re-run Promote memory if needed.",
                )
                self._refresh_home_dashboard()
                return
            # Autonomous path: apply without modal preview (CLI/CL parity).
            # Defer accepted-count logging until apply_done confirms outcome.
            self._start_home_action(f"Running agents-apply on {candidates.name}…")
            generation = getattr(self, "_bg_generation", 0)
            self._run_bg(
                lambda r=root, c=candidates, g=generation, p=result: self._run_memory_apply_if_current(
                    r, c, g, prior=p
                ),
                self._project_done_callback("Memory apply", self._agents_apply_done),
            )
            return
        if accepted:
            self._queue_home_log(f"Accepted {len(accepted)} candidate(s).")
        self._refresh_home_dashboard()

    def _run_memory_apply_if_current(
        self,
        root: Path,
        candidates: Path,
        generation: int,
        *,
        prior: dict | None = None,
    ) -> dict:
        if generation != self._bg_generation:
            return {
                "ok": False,
                "error": "Memory apply cancelled — project or dashboard changed.",
                "cancelled": True,
            }
        if prior and prior.get("accepted"):
            return run_agents_memory_finalize_apply(root, prior)
        return run_agents_memory_apply(root, candidates)

    def _open_project_file(self, root: Path, rel_path: str) -> None:
        project_root = root.resolve()
        target = (project_root / rel_path).resolve()
        try:
            target.relative_to(project_root)
        except ValueError:
            messagebox.showwarning(
                "Invalid path",
                "The proposal file must stay inside the linked project.",
                parent=self.root,
            )
            return
        if not target.is_file():
            messagebox.showwarning("File not found", f"Could not find:\n{target}", parent=self.root)
            return
        if sys.platform == "win32":
            try:
                os.startfile(target)  # noqa: S606
                return
            except OSError:
                open_path_in_explorer(target.parent)
                messagebox.showinfo(
                    "Open proposal file",
                    "No app is associated with .md files, so the containing folder was opened instead:\n"
                    f"{target.parent}",
                    parent=self.root,
                )
                return
        open_path_in_explorer(target)

    def _format_memory_proposal_preview(self, result: dict) -> str:
        lines: list[str] = []
        accepted = result.get("accepted") or []
        if accepted:
            lines.extend(["Proposed additions", ""])
            for bullet in accepted:
                lines.append(f"- {bullet}")
            lines.append("")
        before = (result.get("current_facts") or "").strip()
        lines.extend(["Current memory (Durable Workspace Facts)", ""])
        lines.append(before if before else "(section missing or empty)")
        lines.append("")
        after = (result.get("after_section") or "").strip()
        lines.extend(["After apply", ""])
        lines.append(after if after else before or "(unchanged)")
        lines.append("")
        rejected = result.get("rejected") or []
        if rejected:
            lines.extend([f"Rejected ({len(rejected)})", ""])
            for item in rejected:
                if isinstance(item, dict):
                    candidate = item.get("candidate", "")
                    reason = item.get("reason", "")
                else:
                    candidate, reason = item
                lines.append(f"- {candidate}")
                if reason:
                    lines.append(f"  Reason: {reason}")
            lines.append("")
        spec_actions = result.get("spec_actions") or []
        if spec_actions:
            lines.extend(["Spec Kit actions required", ""])
            for action in spec_actions:
                lines.append(f"- {action}")
            lines.append("")
        proposal = result.get("proposal_path")
        if proposal:
            lines.append(f"Full proposal file: {proposal}")
        return "\n".join(lines).rstrip() + "\n"

    def _show_memory_proposal_preview(
        self, result: dict, *, root: Path, allow_apply: bool = True
    ) -> bool:
        """Show before/after preview; return True when user chooses Apply."""
        accepted = result.get("accepted") or []
        if not accepted:
            return False

        dialog = tk.Toplevel(self.root)
        dialog.title("Memory proposal preview" if allow_apply else "Apply failed — review proposal")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("620x520")
        dialog.minsize(520, 420)

        body = tk.Frame(dialog, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            body,
            text=(
                "Review what would change in AGENTS.md before applying. "
                "Behavioral requirements belong in spec.md, not memory."
            ),
            wraplength=560,
            justify="left",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", pady=(0, 8))

        proposal_rel = result.get("proposal_path")
        if proposal_rel:
            tk.Label(
                body,
                text=f"Proposal: {proposal_rel}",
                bg=COLORS["bg"],
                fg=COLORS["muted"],
                font=FONT_SUBTITLE,
                wraplength=560,
                justify="left",
            ).pack(anchor="w", pady=(0, 8))

        preview = scrolledtext.ScrolledText(
            body,
            height=18,
            font=("Consolas", 9),
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
            wrap="word",
        )
        preview.pack(fill="both", expand=True, pady=(0, 12))
        preview.insert("1.0", self._format_memory_proposal_preview(result))
        preview.configure(state="disabled")
        bind_mousewheel(preview)

        apply_choice = {"value": False}

        def choose_apply() -> None:
            apply_choice["value"] = True
            dialog.destroy()

        btn_row = tk.Frame(dialog, bg=COLORS["bg"])
        btn_row.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
        if allow_apply:
            primary_button(
                btn_row,
                f"Apply {len(accepted)} bullet(s) to AGENTS.md",
                choose_apply,
                tooltip="Merge accepted operational bullets into Durable Workspace Facts.",
            )
        if proposal_rel:
            secondary_button(
                btn_row,
                "Open proposal file",
                lambda: self._open_project_file(root, proposal_rel),
                tooltip="Open the saved proposal markdown in your default editor.",
            )
        secondary_button(
            btn_row,
            "Close" if allow_apply else "Close",
            dialog.destroy,
            tooltip="Close without changing AGENTS.md." if allow_apply else "Return without retrying apply.",
        )

        dialog.wait_window()
        return apply_choice["value"]

    def _show_memory_rejection_preview(self, result: dict, *, root: Path) -> None:
        """Show why every candidate was rejected (no apply path)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Memory promotion rejected")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("620x520")
        dialog.minsize(520, 420)

        body = tk.Frame(dialog, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            body,
            text=(
                "Every candidate was rejected. Nothing will be written to AGENTS.md. "
                "Fix the candidates file or update spec.md for behavioral requirements."
            ),
            wraplength=560,
            justify="left",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", pady=(0, 8))

        proposal_rel = result.get("proposal_path")
        if proposal_rel:
            tk.Label(
                body,
                text=f"Proposal: {proposal_rel}",
                bg=COLORS["bg"],
                fg=COLORS["muted"],
                font=FONT_SUBTITLE,
                wraplength=560,
                justify="left",
            ).pack(anchor="w", pady=(0, 8))

        preview = scrolledtext.ScrolledText(
            body,
            height=18,
            font=("Consolas", 9),
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
            wrap="word",
        )
        preview.pack(fill="both", expand=True, pady=(0, 12))
        preview.insert("1.0", self._format_memory_proposal_preview(result))
        preview.configure(state="disabled")
        bind_mousewheel(preview)

        btn_row = tk.Frame(dialog, bg=COLORS["bg"])
        btn_row.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
        if proposal_rel:
            secondary_button(
                btn_row,
                "Open proposal file",
                lambda: self._open_project_file(root, proposal_rel),
                tooltip="Open the saved rejection report in your default editor.",
            )
        secondary_button(btn_row, "Close", dialog.destroy, tooltip="Return without changing AGENTS.md.")
        dialog.wait_window()

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
        self._start_home_action(f"Running agents-propose --apply on {candidates.name}…")
        self._run_bg(
            lambda r=root, c=candidates: run_agents_memory_propose(r, c, apply=True),
            self._project_done_callback("Memory promotion", self._agents_propose_done),
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
        self._start_home_action(f"Applying memory from {candidates.name}…")
        self._run_bg(
            lambda r=root, c=candidates: run_agents_memory_propose(r, c, apply=True),
            self._project_done_callback("Memory apply", self._agents_propose_done),
        )

    def _agents_apply_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        if result.get("cancelled"):
            self._queue_home_log(self._result_detail(result))
            self._clear_memory_work_context()
            self._refresh_home_dashboard()
            return
        if not result.get("ok"):
            self._queue_home_log(self._result_detail(result))
            for hint in result.get("hints", []):
                self._queue_home_log(f"Tip: {hint}")
            root = self._resolve_memory_work_root()
            if root and result.get("proposal_path"):
                if result.get("accepted"):
                    self._show_memory_proposal_preview(result, root=root, allow_apply=False)
                elif result.get("rejected"):
                    self._show_memory_rejection_preview(result, root=root)
            self._refresh_home_dashboard()
            return
        self._queue_home_log(f"Proposal: {result.get('proposal_path')}")
        accepted = result.get("accepted") or []
        rejected = result.get("rejected") or []
        if rejected:
            self._queue_home_log(f"Rejected {len(rejected)} candidate(s) — see proposal file.")
        if result.get("noop"):
            self._queue_home_log("AGENTS.md unchanged — accepted bullets already present.")
        elif result.get("applied"):
            if accepted:
                self._queue_home_log(f"Accepted {len(accepted)} candidate(s).")
            self._queue_home_log("AGENTS.md updated.")
            for item in result.get("routing") or []:
                arm = item.get("arm")
                reason = item.get("reason")
                if arm or reason:
                    self._queue_home_log(f"  route/{arm}: {reason}")
        self._clear_memory_work_context()
        self._refresh_home_dashboard()

    def _agents_propose_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        self._deliver_memory_propose_result(result)

    def _on_unified_verify(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        self._start_home_action("Verifying upstream pins and vendored overlays…")
        self._run_bg(
            lambda r=root: run_unified_verify(r),
            self._project_done_callback("Vendor verification", self._unified_verify_done),
        )

    def _unified_verify_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        if result.get("ok"):
            self._queue_home_log("Vendor pins and overlays OK.")
        else:
            self._queue_home_log(self._result_detail(result))
            for issue in result.get("issues") or []:
                self._queue_home_log(f"  issue: {issue}")
            for hint in result.get("hints", []):
                self._queue_home_log(f"Tip: {hint}")
        pins_match = result.get("pins_match")
        if pins_match is not None:
            self._queue_home_log(f"Pins match packaged manifest: {pins_match}")
        self._refresh_home_dashboard()

    def _on_legacy_deployment_scan(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        self._start_home_action("Scanning for legacy deployment traces…")
        self._run_bg(
            lambda r=root: run_legacy_deployment_scan(r),
            self._project_done_callback("Legacy deployment scan", self._legacy_deployment_scan_done),
        )

    def _legacy_deployment_scan_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        self._queue_home_log(result.get("detail", "Scan complete."))
        for finding in result.get("findings") or []:
            severity = finding.get("severity", "info")
            prefix = "WARN" if severity == "warn" else "info"
            self._queue_home_log(f"  [{prefix}] {finding.get('detail')}")
            repair = finding.get("repair")
            if repair:
                self._queue_home_log(f"    repair: {repair}")
        self._refresh_home_dashboard()

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
        self._start_home_action("Migrating marketplace Continual Learning data to Hive format…")
        self._run_bg(
            lambda r=root, rm=remove_plugin: run_cl_migrate(r, remove_marketplace_plugin=rm),
            self._project_done_callback("Continual Learning migration", self._cl_migrate_done),
        )

    def _cl_migrate_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        if not result.get("ok"):
            self._queue_home_log(self._result_detail(result))
            for hint in result.get("hints", []):
                self._queue_home_log(f"Tip: {hint}")
            for warning in result.get("warnings", []):
                self._queue_home_log(f"Warning: {warning}")
            self._refresh_home_dashboard()
            return
        for action in result.get("actions") or []:
            self._queue_home_log(f"  {action}")
        for warning in result.get("warnings", []):
            self._queue_home_log(f"Warning: {warning}")
        merged = result.get("merged_bullets", 0)
        if merged:
            self._queue_home_log(f"Merged {merged} bullet(s) into ## Durable Workspace Facts.")
        if result.get("removed_marketplace_plugin"):
            self._queue_home_log("Removed marketplace continual-learning plugin from project.")
        if result.get("cl_source"):
            self._queue_home_log(f"Set cl_source={result['cl_source']} in .hive/project.json.")
        if result.get("dry_run"):
            self._queue_home_log("CL migration dry run complete.")
        else:
            self._queue_home_log("CL migration complete.")
        self._refresh_home_dashboard()

    def _on_map_sync(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        self._start_home_action("Syncing impact maps…")
        self._run_bg(
            lambda r=root: run_project_map_sync(r),
            self._project_done_callback("Impact map sync", self._map_sync_done),
        )

    def _map_sync_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        if result.get("ok") is False:
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        added = len(result.get("project_added", [])) + len(result.get("test_added", []))
        updated = len(result.get("project_updated", [])) + len(result.get("test_updated", []))
        if added or updated:
            self._queue_home_log(f"Impact maps synced: {added} added, {updated} updated.")
        else:
            self._queue_home_log("Impact maps already up to date.")
        self._refresh_home_dashboard()

    def _controls_bug_hunt_iterations(self) -> int | None:
        from hive_planner.bug_hunt import (
            DEFAULT_ITERATIONS,
            MAX_ITERATIONS,
            MIN_ITERATIONS,
            BugHuntError,
            validate_iterations,
        )

        raw = str(self.controls_bug_iterations.get() if hasattr(self, "controls_bug_iterations") else "").strip()
        if not raw:
            return DEFAULT_ITERATIONS
        try:
            value = int(raw)
        except ValueError:
            messagebox.showwarning("Iterations", "Iterations must be a whole number.")
            return None
        try:
            return validate_iterations(value)
        except BugHuntError:
            messagebox.showwarning(
                "Iterations",
                f"Iterations must be between {MIN_ITERATIONS} and {MAX_ITERATIONS}.",
            )
            return None

    def _on_bug_hunt_install(self) -> None:
        if not self.config.active_project:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        link = Path(self.config.active_project)
        iterations = self._controls_bug_hunt_iterations()
        if iterations is None:
            return
        self._start_home_action("Installing bug-hunt chat trigger…")
        self._run_bg(
            lambda r=link, n=iterations: run_project_bug_hunt_install(r, iterations=n),
            self._project_done_callback("Bug-hunt install", self._bug_hunt_install_done),
        )

    def _bug_hunt_install_done(self, result: dict) -> None:
        if self._is_bg_error(result) or result.get("ok") is not True:
            self._controls_action_failed(result)
            return
        count = len(result.get("files_written") or [])
        iterations = result.get("iterations", 50)
        message = (
            f"Bug hunt enabled ({count} file(s), {iterations} iterations). "
            "In any Cursor chat on this project, say bug hunt — or hunt for bugs / start a bug hunt."
        )
        self._queue_home_log(message)
        self._set_controls_last(message)
        self._refresh_home_dashboard()

    def _on_agnostic_loop_install(self) -> None:
        if not self.config.active_project:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        link = Path(self.config.active_project)
        self._start_home_action("Installing hive-loop-kit…")
        self._run_bg(
            lambda r=link: run_project_agnostic_loop_install(r),
            self._project_done_callback("Agnostic-loop install", self._agnostic_loop_install_done),
        )

    def _agnostic_loop_install_done(self, result: dict) -> None:
        if self._is_bg_error(result) or result.get("ok") is not True:
            self._controls_action_failed(result)
            return
        count = len(result.get("files_written") or [])
        message = (
            f"Agnostic loop enabled ({count} file(s)). "
            "Use Controls → Agnostic loop, or say agnostic loop / hive loop kit in Cursor chat."
        )
        self._queue_home_log(message)
        self._set_controls_last(message)
        self._refresh_home_dashboard()

    def _on_implementation_loop_install(self, *, from_controls: bool = False) -> None:
        if not self.config.active_project:
            messagebox.showwarning("No project", "Link a workspace first.")
            return
        from hive_planner.implementation_loop import PACK_1, PACK_4

        if from_controls and hasattr(self, "controls_impl_pack"):
            pack = str(self.controls_impl_pack.get() or "").strip()
        else:
            pack = simpledialog.askstring(
                "Implementation loop pack",
                f"Pack ({PACK_1} or {PACK_4}):",
                parent=self.root,
            )
            if not pack:
                return
            pack = pack.strip()
        if pack not in (PACK_1, PACK_4):
            messagebox.showwarning("Invalid pack", f"Use {PACK_1} or {PACK_4}.")
            return
        link = Path(self.config.active_project)
        peek = peek_implementation_loop_pack(link)
        if peek.get("ok") is not True:
            messagebox.showwarning("No project", peek.get("error") or "Could not resolve the linked project.")
            return
        existing = peek.get("pack")
        force_pack = False
        if existing and existing != pack:
            if not messagebox.askyesno(
                "Replace pack",
                f"This project already has {existing}. Replace it with {pack}?",
                parent=self.root,
            ):
                return
            force_pack = True
        self._start_home_action(f"Installing implementation loop ({pack})…")
        self._run_bg(
            lambda r=link, p=pack, f=force_pack: run_project_implementation_loop_install(r, p, force_pack=f),
            self._project_done_callback("Implementation loop install", self._implementation_loop_install_done),
        )

    def _implementation_loop_install_done(self, result: dict) -> None:
        if self._is_bg_error(result) or result.get("ok") is not True:
            self._controls_action_failed(result)
            return
        count = len(result.get("files_written") or [])
        pack = result.get("pack", "")
        message = (
            f"Implementation loop enabled ({pack}, {count} file(s)). "
            "Use Controls → Implementation loop, or say implementation loop in Cursor chat."
        )
        self._queue_home_log(message)
        self._set_controls_last(message)
        self._refresh_home_dashboard()

    def _require_active_link(self) -> Path | None:
        if not self.config.active_project:
            messagebox.showwarning("No project", "Link a workspace first.")
            return None
        return Path(self.config.active_project)

    def _ask_loop_feature(self) -> str | None:
        initial = self._active_feature_label()
        if initial == "—":
            initial = ""
        value = simpledialog.askstring(
            "Implementation loop feature",
            "Feature id (leave blank to use AGENTS.md Active feature):",
            initialvalue=initial,
            parent=self.root,
        )
        if value is None:
            return None
        return value.strip()

    def _ask_loop_role(self) -> str | None:
        value = simpledialog.askstring(
            "Implementation loop role",
            "Role: coder, checker, reviewer (4-pack) or coordinator (1-pack):",
            parent=self.root,
        )
        if value is None:
            return None
        role = value.strip()
        if not role:
            messagebox.showwarning("Role required", "Enter a role.")
            return None
        return role

    def _format_loop_gate(self, result: dict) -> str:
        parts: list[str] = []
        if "ready" in result:
            parts.append(f"ready={result.get('ready')}")
        for key in (
            "ok",
            "action",
            "feature",
            "task",
            "current_task",
            "role",
            "next_role",
            "round_trips",
            "blocked_reason",
            "commit",
            "pr_url",
            "pack",
            "state_status",
        ):
            val = result.get(key)
            if val not in (None, "", []):
                parts.append(f"{key}={val}")
        missing = result.get("missing") or []
        if missing:
            parts.append("missing=" + ", ".join(str(item) for item in missing))
        dirty = result.get("dirty") or []
        if dirty:
            parts.append("dirty=" + ", ".join(str(item) for item in dirty))
        err = result.get("error")
        if err and result.get("blocked_reason") != err:
            parts.append(str(err))
        if parts:
            return "Implementation loop: " + "; ".join(parts)
        return "Implementation loop: " + str(result)

    def _set_controls_last(self, text: str) -> None:
        if hasattr(self, "controls_last"):
            self.controls_last.set(text)

    def _controls_action_failed(self, result) -> None:
        line = self._result_detail(result)
        self._queue_home_log(line)
        self._set_controls_last(line)
        self._refresh_home_dashboard()

    def _log_loop_gate(self, result: dict) -> None:
        line = self._format_loop_gate(result) if isinstance(result, dict) else self._result_detail(result)
        self._queue_home_log(line)
        self._set_controls_last(line)
        self._refresh_home_dashboard()

    def _controls_feature_value(self) -> str:
        if hasattr(self, "controls_impl_feature"):
            return str(self.controls_impl_feature.get() or "").strip()
        return ""

    def _controls_role_value(self) -> str:
        if hasattr(self, "controls_impl_role"):
            return str(self.controls_impl_role.get() or "").strip()
        return ""

    def _on_implementation_loop_status(self, *, from_controls: bool = False) -> None:
        link = self._require_active_link()
        if link is None:
            return
        if from_controls:
            feature = self._controls_feature_value()
        else:
            feature = self._ask_loop_feature()
            if feature is None:
                return
        self._start_home_action("Checking implementation-loop status…")
        self._run_bg(
            lambda r=link, f=feature: run_project_implementation_loop_status(r, f or None),
            self._project_done_callback("Implementation loop status", self._log_loop_gate),
        )

    def _on_implementation_loop_start(self, *, from_controls: bool = False) -> None:
        link = self._require_active_link()
        if link is None:
            return
        if from_controls:
            feature = self._controls_feature_value()
            allow_dirty = bool(self.controls_impl_allow_dirty.get()) if hasattr(self, "controls_impl_allow_dirty") else False
            force_feature = bool(self.controls_impl_force_feature.get()) if hasattr(self, "controls_impl_force_feature") else False
        else:
            feature = self._ask_loop_feature()
            if feature is None:
                return
            allow_dirty = False
            force_feature = False
        self._run_loop_start(link, feature, allow_dirty=allow_dirty, force_feature=force_feature)

    def _run_loop_start(
        self,
        link: Path,
        feature: str,
        *,
        allow_dirty: bool,
        force_feature: bool,
    ) -> None:
        self._loop_start_ctx = {
            "link": link,
            "feature": feature,
            "allow_dirty": allow_dirty,
            "force_feature": force_feature,
        }
        self._start_home_action("Starting implementation loop…")
        self._run_bg(
            lambda r=link, f=feature, d=allow_dirty, ff=force_feature: run_project_implementation_loop_start(
                r,
                f or None,
                allow_dirty=d,
                force_feature=ff,
            ),
            self._project_done_callback("Implementation loop start", self._implementation_loop_start_done),
        )

    def _implementation_loop_start_done(self, result: dict) -> None:
        if self._is_bg_error(result) or result.get("ok") is not True:
            err = str(result.get("error") or result.get("blocked_reason") or "")
            ctx = getattr(self, "_loop_start_ctx", None) or {}
            if "unrelated dirty" in err and not ctx.get("allow_dirty"):
                dirty = result.get("dirty") or []
                extra = ""
                if dirty:
                    listed = "\n".join(str(path) for path in dirty[:12])
                    if len(dirty) > 12:
                        listed += f"\n(+{len(dirty) - 12} more)"
                    extra = f"\n\n{listed}"
                if messagebox.askyesno(
                    "Unrelated dirty files",
                    "Unrelated dirty paths block start. Continue anyway (same as --allow-dirty)?"
                    + extra,
                    parent=self.root,
                ):
                    self._run_loop_start(
                        ctx["link"],
                        ctx["feature"],
                        allow_dirty=True,
                        force_feature=bool(ctx.get("force_feature")),
                    )
                    return
            if ("loop is blocked" in err or "loop is running for" in err) and not ctx.get("force_feature"):
                if messagebox.askyesno(
                    "Force start",
                    "The loop is blocked or already running for another feature. Force start (same as --force-feature)?",
                    parent=self.root,
                ):
                    self._run_loop_start(
                        ctx["link"],
                        ctx["feature"],
                        allow_dirty=bool(ctx.get("allow_dirty")),
                        force_feature=True,
                    )
                    return
            self._log_loop_gate(result)
            return
        self._log_loop_gate(result)

    def _on_implementation_loop_handoff(self, *, from_controls: bool = False) -> None:
        link = self._require_active_link()
        if link is None:
            return
        if from_controls:
            role = self._controls_role_value()
            if not role:
                messagebox.showwarning("Role required", "Pick a role on the Controls tab.")
                return
            continue_after_cap = bool(self.controls_impl_continue_cap.get()) if hasattr(self, "controls_impl_continue_cap") else False
        else:
            role = self._ask_loop_role()
            if role is None:
                return
            continue_after_cap = False
        self._run_loop_handoff(link, role, continue_after_cap=continue_after_cap)

    def _run_loop_handoff(self, link: Path, role: str, *, continue_after_cap: bool) -> None:
        self._loop_handoff_ctx = {"link": link, "role": role, "continue_after_cap": continue_after_cap}
        self._start_home_action(f"Writing implementation-loop handoff ({role})…")
        self._run_bg(
            lambda r=link, n=role, c=continue_after_cap: run_project_implementation_loop_handoff(
                r,
                n,
                continue_after_cap=c,
            ),
            self._project_done_callback("Implementation loop handoff", self._implementation_loop_handoff_done),
        )

    def _implementation_loop_handoff_done(self, result: dict) -> None:
        if self._is_bg_error(result) or result.get("ok") is not True:
            err = str(result.get("error") or result.get("blocked_reason") or "")
            ctx = getattr(self, "_loop_handoff_ctx", None) or {}
            if "continue-after-cap" in err and not ctx.get("continue_after_cap"):
                if messagebox.askyesno(
                    "Round-trip cap",
                    "This slice has 10 round trips. Continue anyway (same as --continue-after-cap)?",
                    parent=self.root,
                ):
                    self._run_loop_handoff(ctx["link"], ctx["role"], continue_after_cap=True)
                    return
            self._log_loop_gate(result)
            return
        self._log_loop_gate(result)

    def _on_implementation_loop_check(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        self._start_home_action("Running implementation-loop check…")
        self._run_bg(
            lambda r=link: run_project_implementation_loop_check(r),
            self._project_done_callback("Implementation loop check", self._log_loop_gate),
        )

    def _on_implementation_loop_accept(self, *, from_controls: bool = False) -> None:
        link = self._require_active_link()
        if link is None:
            return
        if from_controls:
            role = self._controls_role_value()
            if not role:
                messagebox.showwarning("Role required", "Pick a role on the Controls tab.")
                return
        else:
            role = self._ask_loop_role()
            if role is None:
                return
        self._start_home_action(f"Accepting implementation-loop result ({role})…")
        self._run_bg(
            lambda r=link, n=role: run_project_implementation_loop_accept(r, n),
            self._project_done_callback("Implementation loop accept", self._log_loop_gate),
        )

    def _on_implementation_loop_commit(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        self._start_home_action("Running implementation-loop commit…")
        self._run_bg(
            lambda r=link: run_project_implementation_loop_commit(r),
            self._project_done_callback("Implementation loop commit", self._log_loop_gate),
        )

    def _on_bug_hunt_status(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        self._start_home_action("Checking bug-hunt install…")
        self._run_bg(
            lambda r=link: peek_bug_hunt_status(r),
            self._project_done_callback("Bug-hunt status", self._log_controls_result),
        )

    def _on_implementation_loop_peek_pack(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        self._start_home_action("Checking implementation-loop pack…")
        self._run_bg(
            lambda r=link: peek_implementation_loop_pack(r),
            self._project_done_callback("Implementation loop pack", self._log_controls_result),
        )

    def _on_agnostic_loop_peek(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        self._start_home_action("Checking agnostic-loop install…")
        self._run_bg(
            lambda r=link: peek_agnostic_loop_status(r),
            self._project_done_callback("Agnostic-loop install check", self._log_controls_result),
        )

    def _on_agnostic_loop_rewards(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        self._start_home_action("Listing agnostic-loop rewards…")
        self._run_bg(
            lambda r=link: run_project_agnostic_loop_rewards(r),
            self._project_done_callback("Agnostic-loop rewards", self._log_agnostic_gate),
        )

    def _on_agnostic_loop_status(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        self._start_home_action("Reading agnostic-loop status…")
        self._run_bg(
            lambda r=link: run_project_agnostic_loop_status(r),
            self._project_done_callback("Agnostic-loop status", self._log_agnostic_gate),
        )

    def _controls_agn_cycles(self) -> int | None:
        raw = str(self.controls_agn_cycles.get() if hasattr(self, "controls_agn_cycles") else "1").strip() or "1"
        try:
            value = int(raw)
        except ValueError:
            messagebox.showwarning("Cycles", "Cycles must be a whole number.")
            return None
        if value < 1:
            messagebox.showwarning("Cycles", "Cycles must be at least 1.")
            return None
        return value

    def _on_agnostic_loop_arm(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        reward = str(self.controls_agn_reward.get() if hasattr(self, "controls_agn_reward") else "").strip()
        if not reward:
            messagebox.showwarning("Reward", "Enter a catalog reward name.")
            return
        cycles = self._controls_agn_cycles()
        if cycles is None:
            return
        self._start_home_action(f"Arming agnostic-loop reward {reward}…")
        self._run_bg(
            lambda r=link, w=reward, n=cycles: run_project_agnostic_loop_arm(r, w, n),
            self._project_done_callback("Agnostic-loop arm", self._log_agnostic_gate),
        )

    def _on_agnostic_loop_begin(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        self._start_home_action("Beginning agnostic-loop tick…")
        self._run_bg(
            lambda r=link: run_project_agnostic_loop_begin(r),
            self._project_done_callback("Agnostic-loop begin", self._log_agnostic_gate),
        )

    def _on_agnostic_loop_review(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        note = str(self.controls_agn_note.get() if hasattr(self, "controls_agn_note") else "").strip()
        if not note:
            messagebox.showwarning("Review note", "Enter a review note.")
            return
        self._start_home_action("Writing agnostic-loop review…")
        self._run_bg(
            lambda r=link, n=note: run_project_agnostic_loop_review(r, n),
            self._project_done_callback("Agnostic-loop review", self._log_agnostic_gate),
        )

    def _on_agnostic_loop_observe(self, hit: bool) -> None:
        link = self._require_active_link()
        if link is None:
            return
        reward = str(self.controls_agn_reward.get() if hasattr(self, "controls_agn_reward") else "").strip()
        if not reward:
            messagebox.showwarning("Reward", "Enter a catalog reward name.")
            return
        self._start_home_action("Recording agnostic-loop observation…")
        self._run_bg(
            lambda r=link, w=reward, h=hit: run_project_agnostic_loop_observe(r, w, h),
            self._project_done_callback("Agnostic-loop observe", self._log_agnostic_gate),
        )

    def _on_agnostic_loop_choose(self) -> None:
        link = self._require_active_link()
        if link is None:
            return
        open_text = str(self.controls_agn_open.get() if hasattr(self, "controls_agn_open") else "").strip() or None
        do_arm = bool(self.controls_agn_arm_choose.get()) if hasattr(self, "controls_agn_arm_choose") else False
        cycles = self._controls_agn_cycles()
        if cycles is None:
            return
        self._start_home_action("Choosing agnostic-loop reward…")
        self._run_bg(
            lambda r=link, o=open_text, a=do_arm, n=cycles: run_project_agnostic_loop_choose(
                r, o, do_arm=a, cycles=n
            ),
            self._project_done_callback("Agnostic-loop choose", self._log_agnostic_gate),
        )

    def _format_agnostic_gate(self, result: dict) -> str:
        parts: list[str] = []
        for key in (
            "ok",
            "action",
            "reward",
            "hook",
            "hit",
            "completed",
            "max_cycles",
            "blocked_reason",
            "installed",
            "pack",
        ):
            val = result.get(key)
            if val not in (None, "", []):
                parts.append(f"{key}={val}")
        names = result.get("rewards") or []
        if names:
            parts.append("rewards=" + ", ".join(str(item) for item in names))
        missing = result.get("missing") or []
        if missing:
            parts.append("missing=" + ", ".join(str(item) for item in missing))
        err = result.get("error")
        if err and "blocked_reason" not in (result or {}):
            parts.append(str(err))
        elif err and result.get("blocked_reason") != err:
            parts.append(str(err))
        if parts:
            return "Agnostic loop: " + "; ".join(parts)
        return "Agnostic loop: " + str(result)

    def _log_agnostic_gate(self, result: dict) -> None:
        line = self._format_agnostic_gate(result) if isinstance(result, dict) else self._result_detail(result)
        self._queue_home_log(line)
        self._set_controls_last(line)
        self._refresh_home_dashboard()

    def _log_controls_result(self, result: dict) -> None:
        if isinstance(result, dict) and result.get("action", "").startswith("bug-hunt"):
            installed = result.get("installed")
            missing = result.get("missing") or []
            if result.get("ok") is True and installed:
                line = f"Bug hunt: installed in {result.get('root')}"
            else:
                line = "Bug hunt: " + (result.get("error") or ("missing " + ", ".join(str(item) for item in missing) if missing else self._result_detail(result)))
        elif isinstance(result, dict) and result.get("action") == "agnostic-status":
            missing = result.get("missing") or []
            if result.get("ok") is True and result.get("installed"):
                line = f"Agnostic loop: installed in {result.get('root')}"
            else:
                line = "Agnostic loop: " + (result.get("error") or ("missing " + ", ".join(str(item) for item in missing) if missing else self._result_detail(result)))
        elif isinstance(result, dict) and "pack" in result:
            line = f"Implementation loop pack: {result.get('pack') or 'not installed'}"
            if result.get("error"):
                line = f"Implementation loop pack: {result.get('error')}"
        else:
            line = self._result_detail(result)
        self._queue_home_log(line)
        self._set_controls_last(line)
        self._refresh_home_dashboard()

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
        self._start_home_action(
            f"Deploying unified agent handoff (Spec Kit + Continual Learning, cl_runtime={selected})…"
        )
        hive_root = cfg.normalized_hive_root()
        self._run_bg(
            lambda r=root, h=hive_root, rt=selected: run_deploy_agent_handoff(
                r,
                hive_planner_root=h,
                force=False,
                cl_runtime=rt,
            ),
            self._project_done_callback("Agent handoff deployment", self._deploy_handoff_done),
        )

    def _on_load_sources(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        summary = summarize_linked_project(Path(self.config.active_project))
        default_feature = summary.active_feature or "example-feature"

        from hive_planner.config import RepoPaths
        from hive_planner.source4s import list_source4s_files

        existing = list_source4s_files(RepoPaths(root=root))
        existing_hint = (
            f"{len(existing)} file(s) already in context-library/sources/source4s/"
            if existing
            else "No reference sources staged yet in this project."
        )

        dialog = tk.Toplevel(self.root)
        dialog.title("Load Sources")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("520x580")
        dialog.minsize(480, 520)

        body = tk.Frame(dialog, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            body,
            text=(
                "Upload .txt and .pdf files for agents to reference during planning. "
                "Files are indexed in context-library and linked to your cartridge via source-context.md."
            ),
            wraplength=480,
            justify="left",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            body,
            text=existing_hint,
            wraplength=480,
            justify="left",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
        ).pack(anchor="w", pady=(0, 12))

        feature_row = tk.Frame(body, bg=COLORS["bg"])
        feature_row.pack(fill="x", pady=(0, 8))
        tk.Label(
            feature_row,
            text="Feature id",
            width=12,
            anchor="w",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT,
        ).pack(side="left")
        feature_var = tk.StringVar(value=default_feature)
        tk.Entry(feature_row, textvariable=feature_var, font=FONT).pack(side="left", fill="x", expand=True)

        link_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            body,
            text="Update cartridge source-context.md (link excerpts to active feature)",
            variable=link_var,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            selectcolor=COLORS["card"],
            anchor="w",
            font=FONT,
            wraplength=470,
        ).pack(anchor="w", pady=4)

        force_var = tk.BooleanVar(value=False)
        force_cb = tk.Checkbutton(
            body,
            text="Force overwrite source-context (ignore draft/manual banners)",
            variable=force_var,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            selectcolor=COLORS["card"],
            anchor="w",
            font=FONT,
            wraplength=470,
        )
        force_cb.pack(anchor="w", pady=4)

        embed_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            body,
            text="Build embeddings (hybrid retrieval — slower, optional)",
            variable=embed_var,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            selectcolor=COLORS["card"],
            anchor="w",
            font=FONT,
            wraplength=470,
        ).pack(anchor="w", pady=4)

        from hive_planner.ocr_runtime import ensure_ocr_runtime

        ocr_status = ensure_ocr_runtime()
        ocr_default = ocr_status.available
        ocr_var = tk.BooleanVar(value=ocr_default)
        ocr_hint = (
            "OCR image-only PDFs with Tesseract (scanned documents)"
            if ocr_status.available
            else "OCR unavailable — install Tesseract or set HIVE_TESSERACT_EXE"
        )
        ocr_cb = tk.Checkbutton(
            body,
            text=ocr_hint,
            variable=ocr_var,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            selectcolor=COLORS["card"],
            anchor="w",
            font=FONT,
            wraplength=470,
        )
        ocr_cb.pack(anchor="w", pady=4)
        if not ocr_status.available:
            ocr_cb.configure(state="disabled")
            ocr_var.set(False)

        from hive_planner.format_deps import pdf_support_available, pdf_support_message

        pdf_ok = pdf_support_available()
        if not pdf_ok:
            tk.Label(
                body,
                text=pdf_support_message(),
                bg=COLORS["bg"],
                fg=COLORS.get("warn", "#c9a227"),
                font=FONT_SUBTITLE,
                wraplength=470,
                justify="left",
            ).pack(anchor="w", pady=(0, 8))

        def sync_force_control(*_args: object) -> None:
            if link_var.get():
                force_cb.configure(state="normal")
            else:
                force_cb.configure(state="disabled")
                force_var.set(False)

        link_var.trace_add("write", sync_force_control)
        sync_force_control()

        selection_mode_var = tk.StringVar(value="multiple")
        mode_row = tk.Frame(body, bg=COLORS["bg"])
        mode_row.pack(fill="x", pady=(0, 4))
        tk.Label(
            mode_row,
            text="Add via",
            width=12,
            anchor="w",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT,
        ).pack(side="left", anchor="n")
        mode_col = tk.Frame(mode_row, bg=COLORS["bg"])
        mode_col.pack(side="left", fill="x", expand=True)
        for value, label in (
            ("folder", "Folder — all .txt and .pdf files in a directory (recursive)"),
            ("single", "Single file"),
            ("multiple", "Multiple files — pick from one or more directories"),
        ):
            tk.Radiobutton(
                mode_col,
                text=label,
                variable=selection_mode_var,
                value=value,
                bg=COLORS["bg"],
                fg=COLORS["fg"],
                activebackground=COLORS["bg"],
                activeforeground=COLORS["fg"],
                selectcolor=COLORS["card"],
                anchor="w",
                justify="left",
                font=FONT,
                wraplength=400,
            ).pack(anchor="w", pady=1)

        selection_var = tk.StringVar(value="(none selected)")
        tk.Label(
            body,
            textvariable=selection_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            wraplength=480,
            justify="left",
        ).pack(anchor="w", pady=(12, 4))

        selected_files: list[Path] = []
        selected_folder: Path | None = None

        def refresh_selection_label() -> None:
            if not selected_files:
                selection_var.set("(none selected)")
            elif len(selected_files) == 1 and selected_files[0].is_dir():
                folder_path = selected_files[0]
                count = len(discover_source4s_files_in_folder(folder_path))
                selection_var.set(f"{count} file(s) from folder {folder_path}")
            elif len(selected_files) == 1:
                selection_var.set(str(selected_files[0]))
            elif selected_folder is not None:
                selection_var.set(
                    f"{len(selected_files)} file(s) from folder {selected_folder}"
                )
            elif all(path.is_dir() for path in selected_files):
                selection_var.set(f"{len(selected_files)} folder(s) selected")
            else:
                selection_var.set(f"{len(selected_files)} files selected")

        def clear_selection(*_args: object) -> None:
            nonlocal selected_folder
            selected_files.clear()
            selected_folder = None
            selection_var.set("(none selected)")

        def set_selection(
            files: list[Path],
            *,
            folder: Path | None = None,
            append: bool = False,
        ) -> None:
            nonlocal selected_folder
            from hive_planner.source4s import merge_source4s_selection

            if append and files:
                selected_files[:] = merge_source4s_selection(selected_files, files)
                selected_folder = None
            else:
                selected_files[:] = files
                selected_folder = folder
            refresh_selection_label()

        selection_mode_var.trace_add("write", clear_selection)

        from hive_planner.source4s import SOURCE4S_FILETYPES, discover_source4s_files_in_folder

        def browse(*, append: bool = False) -> None:
            mode = selection_mode_var.get()
            if mode == "folder":
                folder = filedialog.askdirectory(
                    title="Choose folder with .txt or .pdf reference files",
                    parent=dialog,
                )
                if not folder:
                    return
                folder_path = Path(folder)
                discovered = discover_source4s_files_in_folder(folder_path)
                if not discovered:
                    messagebox.showwarning(
                        "No supported files",
                        f"No .txt or .pdf files found under:\n{folder_path}",
                        parent=dialog,
                    )
                    if not append:
                        clear_selection()
                    return
                if append:
                    set_selection([folder_path], append=True)
                else:
                    set_selection([folder_path], folder=folder_path)
                return
            if mode == "single":
                path = filedialog.askopenfilename(
                    title="Choose a .txt or .pdf reference file",
                    parent=dialog,
                    filetypes=SOURCE4S_FILETYPES,
                )
                if not path:
                    return
                set_selection([Path(path)])
                return
            paths = filedialog.askopenfilenames(
                title="Choose .txt or .pdf reference files",
                parent=dialog,
                filetypes=SOURCE4S_FILETYPES,
            )
            if not paths:
                return
            picked = [Path(p) for p in paths]
            if append:
                set_selection(picked, append=True)
            else:
                set_selection(picked)

        browse_row = tk.Frame(body, bg=COLORS["bg"])
        browse_row.pack(fill="x", pady=(0, 8))
        browse_btn = secondary_button(
            browse_row,
            "Choose files…",
            lambda: browse(append=False),
            tooltip="Pick reference files or a folder, depending on the mode you selected above.",
        )
        add_more_btn = secondary_button(
            browse_row,
            "Add more…",
            lambda: browse(append=True),
            tooltip="Add more files or another folder to the current selection.",
        )
        secondary_button(
            browse_row,
            "Clear",
            clear_selection,
            tooltip="Clear the file list and start over.",
        )

        def sync_selection_mode(*_args: object) -> None:
            mode = selection_mode_var.get()
            if mode == "folder":
                browse_btn.configure(text="Choose folder…")
                add_more_btn.configure(state="normal")
            elif mode == "single":
                browse_btn.configure(text="Choose file…")
                add_more_btn.configure(state="disabled")
            else:
                browse_btn.configure(text="Choose files…")
                add_more_btn.configure(state="normal")

        selection_mode_var.trace_add("write", sync_selection_mode)
        sync_selection_mode()

        action_row = tk.Frame(dialog, bg=COLORS["bg"])
        action_row.pack(side="bottom", fill="x", padx=16, pady=(8, 16))

        def run_upload() -> None:
            if not selected_files:
                mode = selection_mode_var.get()
                if mode == "folder":
                    hint = "Choose a folder containing .txt or .pdf files."
                elif mode == "single":
                    hint = "Choose one .txt or .pdf file."
                else:
                    hint = "Choose one or more .txt or .pdf files."
                messagebox.showwarning("Nothing selected", hint, parent=dialog)
                return
            from hive_planner.config import RepoPaths
            from hive_planner.source4s import (
                expand_source4s_inputs,
                source4s_needs_pdf_support,
                source4s_selection_error,
            )

            expanded_selection = expand_source4s_inputs(selected_files)
            check_files = expanded_selection if expanded_selection else selected_files
            selection_problem = source4s_selection_error(check_files)
            if selection_problem:
                messagebox.showwarning("Invalid selection", selection_problem, parent=dialog)
                return

            repo_paths = RepoPaths(root=root)
            if not pdf_ok and source4s_needs_pdf_support(repo_paths, check_files):
                messagebox.showerror("PDF support missing", pdf_support_message(), parent=dialog)
                return
            feature = feature_var.get().strip()
            if link_var.get():
                try:
                    validate_feature_id(feature)
                except ValueError as exc:
                    messagebox.showerror("Invalid feature id", str(exc), parent=dialog)
                    return
            upload_root = root
            upload_files = list(selected_files)
            upload_feature = feature if link_var.get() else None
            upload_embed = embed_var.get()
            upload_cartridge = link_var.get()
            upload_force = force_var.get()
            upload_ocr = ocr_var.get()
            file_count = len(check_files)
            ingest_only = not upload_cartridge
            dialog.destroy()
            self._start_home_action(
                f"Loading {file_count} source file(s)"
                + (f" for '{feature}'…" if not ingest_only else " (ingest only)…"),
            )
            self._run_bg(
                lambda: run_source4s_upload(
                    upload_root,
                    upload_files,
                    upload_feature,
                    embed=upload_embed,
                    update_cartridge=upload_cartridge,
                    force_delta=upload_force,
                    ocr_pdf=upload_ocr,
                ),
                self._project_done_callback("Source loading", self._load_sources_done),
            )

        primary_button(
            action_row,
            "Load Sources",
            run_upload,
            tooltip="Copy your selected files into the project and index them for AI agents.",
        )
        secondary_button(
            action_row,
            "Cancel",
            dialog.destroy,
            tooltip="Close without uploading anything.",
        )

    def _load_sources_done(self, result: dict) -> None:
        from hive_planner.source4s import pdf_ocr_quality_warnings

        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        warnings = result.get("warnings", [])
        ocr_warnings = pdf_ocr_quality_warnings(warnings)
        if not result.get("ok"):
            if result.get("error"):
                self._queue_home_log(f"Load Sources failed: {result['error']}")
            elif result.get("copied"):
                self._queue_home_log("Load Sources incomplete — see warnings below.")
            if ocr_warnings:
                self._queue_home_log(
                    f"  PDF OCR warnings on {len(ocr_warnings)} staged file(s) — see warnings below."
                )
            indexed = result.get("indexed_staged", 0)
            copied_count = len(result.get("copied", []))
            if indexed and copied_count and indexed < copied_count:
                self._queue_home_log(
                    f"  partial: {indexed} of {copied_count} staged file(s) indexed before failure."
                )
        else:
            indexed = result.get("indexed_staged", len(result.get("copied", [])))
            copied_count = len(result.get("copied", []))
            self._queue_home_log(
                f"Sources loaded — staged {copied_count} file(s), "
                f"indexed {indexed} staged file(s).",
            )
        for rel in result.get("copied", []):
            self._queue_home_log(f"  staged: {rel}")
        if result.get("source_context_path"):
            self._queue_home_log(f"  cartridge link: {result['source_context_path']}")
        for warning in result.get("warnings", []):
            self._queue_home_log(f"Warning: {warning}")
        existing = result.get("existing_sources") or []
        if existing:
            self._queue_home_log(
                f"Reference library: {len(existing)} file(s) in context-library/sources/source4s/"
            )
        self._refresh_home_dashboard()

    def _on_load_cartridge(self) -> None:
        root = self._active_linked_root()
        if not root:
            messagebox.showwarning("No project", "Link a workspace first (Projects tab).")
            return
        summary = summarize_linked_project(Path(self.config.active_project))
        default_feature = summary.active_feature or "example-feature"

        dialog = tk.Toplevel(self.root)
        dialog.title("Bring documents into your project")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("540x580")
        dialog.minsize(500, 500)

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

        from hive_planner.format_deps import pdf_support_available, pdf_support_message

        pdf_ok = pdf_support_available()

        tk.Label(
            body,
            text="Choose how to bring outside documents into your linked project.",
            wraplength=480,
            justify="left",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT_BOLD,
        ).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(
            body,
            text=(
                "Reference files go into your project's library so AI agents can search them. "
                "Planning drafts update your spec and delta docs when promotion is enabled."
            ),
            wraplength=480,
            justify="left",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", padx=16, pady=(0, 10))

        tk.Label(
            body,
            text="What do you want to do?",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT_BOLD,
        ).pack(anchor="w", padx=16, pady=(0, 6))

        mode_var = tk.StringVar(value="sources")
        mode_options: tuple[tuple[str, str, str, str], ...] = (
            (
                "sources",
                "Add reference files (recommended)",
                "PDFs, notes, specs, or markdown — copy into your searchable project library.",
                "Best for research papers, exports, and notes you want AI to find later. "
                "Files are indexed and linked in cartridge/source-context.md.",
            ),
            (
                "translate",
                "Turn one research note into planning drafts",
                "One markdown file → draft holistic/macro/micro/memory files in cartridge/.",
                "Use when you already wrote a planning summary and want draft cartridge files quickly. "
                "Does not add the file to your searchable library — choose Add reference files for that.",
            ),
            (
                "import",
                "Copy an existing cartridge folder",
                "Paste in a cartridge/ folder you exported or copied from another machine.",
                "Use when you already have a complete cartridge/ directory (manifest + markdown layers).",
            ),
        )
        for value, title, subtitle, tip in mode_options:
            row = tk.Frame(body, bg=COLORS["bg"])
            row.pack(fill="x", padx=16, pady=3)
            rb = tk.Radiobutton(
                row,
                text=title,
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
                wraplength=460,
            )
            rb.pack(anchor="w")
            tk.Label(
                row,
                text=subtitle,
                wraplength=440,
                justify="left",
                bg=COLORS["bg"],
                fg=COLORS["muted"],
                font=FONT_SUBTITLE,
            ).pack(anchor="w", padx=(22, 0))
            attach_hover_tooltip(row, tip)
            attach_hover_tooltip(rb, tip)

        tk.Label(
            body,
            text="Options",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT_BOLD,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        feature_row = tk.Frame(body, bg=COLORS["bg"])
        feature_row.pack(fill="x", padx=16, pady=(0, 4))
        feature_label = tk.Label(
            feature_row,
            text="Feature name",
            width=12,
            anchor="w",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT,
        )
        feature_label.pack(side="left")
        feature_var = tk.StringVar(value=default_feature)
        feature_entry = tk.Entry(feature_row, textvariable=feature_var, font=FONT, bg=COLORS["card"], fg=COLORS["fg"])
        feature_entry.pack(side="left", fill="x", expand=True)
        attach_hover_tooltip(
            feature_label,
            "Short id for the feature you are planning (letters, numbers, hyphens only). "
            "Example: mlp-decimacon. Used to pick the right spec and delta files.",
        )
        attach_hover_tooltip(
            feature_entry,
            "Short id for the feature you are planning (letters, numbers, hyphens only). "
            "Example: mlp-decimacon.",
        )

        handoff_status = validate_unified_handoff(root)
        handoff_unified = handoff_status.mode == "unified"
        promote_var = tk.BooleanVar(value=handoff_unified)
        force_promote_var = tk.BooleanVar(value=False)
        mark_draft_var = tk.BooleanVar(value=self.config.default_cartridge_mark_draft)
        promote_row = tk.Frame(body, bg=COLORS["bg"])
        promote_row.pack(fill="x", padx=16, pady=(0, 4))
        promote_cb = tk.Checkbutton(
            promote_row,
            text="Update planning files in the project (spec, delta, memory candidates)",
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
        attach_hover_tooltip(
            promote_cb,
            "After loading, merge draft cartridge content into docs/delta/, stage memory bullets for AGENTS.md, "
            "and run alignment checks. Requires unified agent handoff to be deployed.",
        )
        if not handoff_unified:
            promote_var.set(False)

        force_row = tk.Frame(body, bg=COLORS["bg"])
        force_row.pack(fill="x", padx=16, pady=(0, 4))
        force_cb = tk.Checkbutton(
            force_row,
            text="Replace existing planning files (review carefully)",
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
        attach_hover_tooltip(
            force_cb,
            "Overwrite delta and spec files even when they already contain real content. "
            "Use only when you intend to replace what is there.",
        )

        mark_draft_row = tk.Frame(body, bg=COLORS["bg"])
        mark_draft_row.pack(fill="x", padx=16, pady=(0, 4))
        mark_draft_cb = tk.Checkbutton(
            mark_draft_row,
            text="Mark synced cartridge files as draft (only if delta→cartridge sync wrote them)",
            variable=mark_draft_var,
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
        mark_draft_cb.pack(anchor="w")
        attach_hover_tooltip(
            mark_draft_cb,
            "Adds a draft banner to cartridge layer files this Sources run actually wrote "
            "(usually only when docs/delta already exists and was synced into cartridge/). "
            "Uploading reference files alone does not create holistic/macro drafts — "
            "use 'Turn one research note into planning drafts' for that.",
        )

        embed_var = tk.BooleanVar(value=False)
        embed_row = tk.Frame(body, bg=COLORS["bg"])
        embed_row.pack(fill="x", padx=16, pady=(0, 4))
        embed_cb = tk.Checkbutton(
            embed_row,
            text="Improve AI search quality — build embeddings (slower, recommended for new uploads)",
            variable=embed_var,
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
        embed_cb.pack(anchor="w")
        attach_hover_tooltip(
            embed_cb,
            "Creates semantic search vectors so agents can find the best excerpts from your uploaded files. "
            "Turn on when adding new reference documents.",
        )

        mode_hint_var = tk.StringVar(value="")
        mode_hint = tk.Label(
            body,
            textvariable=mode_hint_var,
            bg=COLORS["bg"],
            fg=COLORS.get("warn", "#c9a227"),
            font=FONT_SUBTITLE,
            wraplength=480,
            justify="left",
        )
        mode_hint.pack(anchor="w", padx=16, pady=(0, 4))

        overwrite_var = tk.BooleanVar(value=False)
        overwrite_row = tk.Frame(body, bg=COLORS["bg"])
        overwrite_row.pack(fill="x", padx=16, pady=(0, 4))
        overwrite_cb = tk.Checkbutton(
            overwrite_row,
            text="Replace cartridge files already in this project",
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
        attach_hover_tooltip(
            overwrite_cb,
            "When importing a cartridge folder, copy over matching files in cartridge/ instead of skipping them.",
        )

        def sync_promote_controls(*_args: object) -> None:
            if not handoff_unified:
                force_cb.configure(state="disabled")
                force_promote_var.set(False)
                mark_draft_cb.configure(state="disabled")
                return
            if promote_var.get():
                force_cb.configure(state="normal")
            else:
                force_cb.configure(state="disabled")
                force_promote_var.set(False)
            sources_promote = mode_var.get() == "sources" and promote_var.get()
            mark_draft_cb.configure(state="normal" if sources_promote else "disabled")

        def sync_mode_hints(*_args: object) -> None:
            sync_promote_controls()
            mode = mode_var.get()
            if mode == "sources":
                embed_cb.configure(state="normal")
                mode_hint_var.set(
                    "Reference files are copied into your project library and linked for AI search. "
                    "Turn on Improve AI search quality when adding new documents."
                )
            elif mode == "translate":
                embed_cb.configure(state="disabled")
                embed_var.set(False)
                mode_hint_var.set(
                    "Creates draft planning files from one markdown note. "
                    "It does not add the file to your searchable library — use Add reference files for that."
                )
            else:
                embed_cb.configure(state="disabled")
                embed_var.set(False)
                mode_hint_var.set(
                    "Copies an entire cartridge/ folder into your project. "
                    "Use when you already exported or copied cartridge files elsewhere."
                )

        promote_var.trace_add("write", sync_mode_hints)
        mode_var.trace_add("write", sync_mode_hints)
        sync_mode_hints()

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
            text="Your selection",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT_BOLD,
        ).pack(anchor="w", padx=16, pady=(8, 2))
        selection_label = tk.Label(
            body,
            textvariable=selection_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            wraplength=480,
            justify="left",
        )
        selection_label.pack(anchor="w", padx=16, pady=(0, 4))
        attach_hover_tooltip(
            selection_label,
            "Shows the file or folder you picked with Browse. Required before you can bring documents into the project.",
        )

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
        secondary_button(
            browse_row,
            "Browse…",
            browse,
            tooltip="Pick the file(s) or folder for the option you selected above.",
        )

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
                        "Feature name required",
                        "Enter a feature name (for example mlp-decimacon).",
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
            if feature and feature != "example-feature":
                try:
                    validate_feature_id(feature)
                except ValueError as exc:
                    messagebox.showerror("Invalid feature name", str(exc), parent=dialog)
                    return
            if mode == "sources":
                from hive_planner.config import RepoPaths
                from hive_planner.source4s import expand_source4s_inputs, source4s_needs_pdf_support

                check_files = expand_source4s_inputs(selected_files) or selected_files
                if not pdf_ok and source4s_needs_pdf_support(RepoPaths(root=root), check_files):
                    messagebox.showerror("PDF support missing", pdf_support_message(), parent=dialog)
                    return

            do_promote = will_promote
            do_feature = feature.strip() if feature.strip() else None
            do_force = force_promote_var.get()
            do_mark_draft = (
                mark_draft_var.get()
                if mode == "sources" and will_promote
                else False
            )
            do_overwrite = overwrite_var.get() if mode == "import" else False

            if mode == "sources" and will_promote:
                self.config.default_cartridge_mark_draft = mark_draft_var.get()
                save_config(self.config)

            dialog.destroy()
            if mode == "sources":
                self._start_home_action(
                    f"Loading {len(selected_files)} source file(s) and emitting cartridge for '{feature}'…",
                )
                self._run_bg(
                    lambda: run_cartridge_load_sources(
                        root,
                        selected_files,
                        do_feature,
                        embed=embed_var.get(),
                        promote=do_promote,
                        force_promote=do_force,
                        mark_emitted_draft=do_mark_draft,
                    ),
                    self._project_done_callback("Cartridge source load", self._cartridge_load_done),
                )
            elif mode == "translate":
                self._start_home_action(
                    f"Translating research into draft cartridge for '{feature}'…",
                )
                self._run_bg(
                    lambda: run_cartridge_translate(
                        root,
                        selected_files[0],
                        do_feature,
                        promote=do_promote,
                        force_promote=do_force,
                    ),
                    self._project_done_callback("Cartridge translation", self._cartridge_load_done),
                )
            else:
                self._start_home_action("Importing cartridge folder…")
                self._run_bg(
                    lambda: run_cartridge_import_folder(
                        root,
                        selected_folder,
                        overwrite=do_overwrite,
                        feature=do_feature,
                        promote=do_promote,
                        force_promote=do_force,
                    ),
                    self._project_done_callback("Cartridge import", self._cartridge_load_done),
                )

        primary_button(
            action_row,
            "Bring into project",
            run_load,
            tooltip="Run the steps for your selected option: add reference files, translate a note, or import a folder.",
        )
        secondary_button(
            action_row,
            "Cancel",
            dialog.destroy,
            tooltip="Close this window without changing your project.",
        )

    def _queue_cartridge_result_log(self, result: dict) -> None:
        worked = bool(
            result.get("files_written")
            or result.get("copied")
            or result.get("written")
            or result.get("outputs")
        )

        if result.get("ok") is False:
            if result.get("error"):
                self._queue_home_log(self._result_detail(result))
            for rel in result.get("copied", []):
                self._queue_home_log(f"  copied: {rel}")
            for rel in result.get("skipped", []):
                self._queue_home_log(f"  skipped (exists): cartridge/{rel}")
            for warning in result.get("warnings", []):
                self._queue_home_log(f"Warning: {warning}")
            if worked:
                self._queue_home_log(
                    "Cartridge load incomplete — partial work saved; see errors above.",
                )
            elif result.get("mode") == "import" and result.get("skipped") and "already exist" in str(result.get("error", "")):
                self._queue_home_log(
                    "Tip: re-open Load cartridge, enable Overwrite existing cartridge files, then try again.",
                )
            self._log_cartridge_promote(result.get("promote"))
            promote = result.get("promote") or {}
            if promote and promote.get("ok") is False:
                self._queue_home_log(
                    "Cartridge load incomplete — files saved but promotion/handoff needs review (see above).",
                )
            return

        mode = result.get("mode")
        if mode == "sources":
            self._queue_home_log(
                f"Cartridge sources loaded ({result.get('processed', 0)} indexed, feature: {result.get('feature')}).",
            )
            for rel in result.get("copied", []):
                self._queue_home_log(f"  copied: {rel}")
            for name, rel in (result.get("outputs") or {}).items():
                self._queue_home_log(f"  wrote {name}: {rel}")
            mark_draft = result.get("mark_draft")
            if mark_draft:
                self._queue_home_log("Marked emitted cartridge layers as draft:")
                for layer, status in sorted(mark_draft.items()):
                    self._queue_home_log(f"  {layer}: {status}")
        elif mode == "translate":
            self._queue_home_log(
                f"Draft cartridge written for '{result.get('feature')}' ({len(result.get('files_written', []))} file(s)).",
            )
            for rel in result.get("files_written", []):
                self._queue_home_log(f"  cartridge/{rel}")
        elif mode == "import":
            self._queue_home_log(
                f"Imported {len(result.get('written', []))} cartridge file(s).",
            )
            for rel in result.get("written", []):
                self._queue_home_log(f"  wrote: cartridge/{rel}")
            for rel in result.get("skipped", []):
                self._queue_home_log(f"  skipped (exists): cartridge/{rel}")
            adapt = result.get("adapt")
            if adapt and adapt.get("adapted"):
                self._queue_home_log(
                    f"Adapted custom files to standard layout (feature: {adapt.get('feature')}).",
                )
                for rel in adapt.get("adapted", []):
                    self._queue_home_log(f"  layer file: cartridge/{rel}")
                for src, dst in sorted((adapt.get("mappings") or {}).items()):
                    if src != dst:
                        self._queue_home_log(f"  mapped: {src} -> cartridge/{dst}")
            if result.get("feature"):
                self._queue_home_log(f"  using feature id: {result['feature']}")
        self._log_cartridge_promote(result.get("promote"))
        promote = result.get("promote") or {}
        if promote and promote.get("ok") is False:
            self._queue_home_log(
                "Cartridge load incomplete — files saved but promotion/handoff needs review (see above).",
            )
        for warning in result.get("warnings", []):
            self._queue_home_log(f"Warning: {warning}")

    def _cartridge_load_done(self, result: dict) -> None:
        if not isinstance(result, dict):
            self._queue_home_log(str(result))
            self._refresh_home_dashboard()
            return
        self._queue_cartridge_result_log(result)
        self._refresh_home_dashboard()

    def _log_cartridge_promote(self, promote: dict | None) -> None:
        if not promote:
            return
        from hive_planner.cartridge_promote import promote_nothing_written_guidance, promote_wrote_layers

        self._queue_home_log("Promotion / symbiotic handoff:")
        if promote.get("feature"):
            self._queue_home_log(f"  feature: {promote['feature']}")
        for layer, status in sorted(promote.get("promotions", {}).items()):
            self._queue_home_log(f"  {layer}: {status}")
        if promote.get("candidates_path"):
            self._queue_home_log(
                f"  CL candidates (review, then promote memory): {promote['candidates_path']}",
            )
            self._queue_home_log(
                "  Next: Home → Record wiring audit, then Home → Promote memory (or agents-propose CLI).",
            )
        if promote.get("ok") is False and promote.get("promotions", {}).get("status") == "skipped (agent handoff off)":
            self._queue_home_log(
                "  Enable unified handoff (Deploy agent handoff) to promote cartridge drafts.",
            )
        repair = promote.get("agents_repair")
        if repair:
            self._queue_home_log(f"  AGENTS.md repair: {repair.get('detail')}")
        rosetta = promote.get("rosetta_repair")
        if rosetta:
            self._queue_home_log(f"  Rosetta navigation: {rosetta.get('detail')}")
            for rel in rosetta.get("patched") or []:
                self._queue_home_log(f"    patched: {rel}")
        if promote_wrote_layers(promote.get("promotions", {})) or rosetta:
            self._queue_home_log(
                "  Agent startup: load docs/planning-rosetta-stone.md (hook planning.rosetta) before spec/delta",
            )
        drift = promote.get("spec_drift")
        if drift is not None:
            mark = "ok" if drift.get("ok") else "review needed"
            self._queue_home_log(f"  spec-drift: {mark}")
        for warning in promote.get("warnings", []):
            self._queue_home_log(f"  Warning: {warning}")
        guidance = promote_nothing_written_guidance(promote)
        if guidance:
            self._queue_home_log(f"  Note: {guidance}")
        if promote.get("ok") is False:
            self._queue_home_log("Promotion/spec-drift needs review before handoff.")

    def _deploy_handoff_done(self, result: dict) -> None:
        if self._is_bg_error(result):
            self._queue_home_log(self._result_detail(result))
            self._refresh_home_dashboard()
            return
        if not result.get("ok"):
            if result.get("error"):
                self._queue_home_log(self._result_detail(result))
            count = len(result.get("files_written", []))
            if count:
                self._queue_home_log(
                    f"Partial deploy — {count} file(s) written; unified handoff still incomplete."
                )
            repair = result.get("repair")
            if repair:
                self._queue_home_log(f"Repaired AGENTS.md — {repair.get('detail', 'updated')}.")
            rosetta = result.get("rosetta_repair")
            if rosetta:
                self._queue_home_log(f"  Rosetta navigation: {rosetta.get('detail')}")
                for rel in rosetta.get("patched") or []:
                    self._queue_home_log(f"    patched: {rel}")
            handoff = result.get("handoff") or {}
            for rel in handoff.get("missing") or []:
                self._queue_home_log(f"  missing: {rel}")
            for warning in result.get("warnings", []):
                self._queue_home_log(f"Warning: {warning}")
            for hint in result.get("hints", []):
                self._queue_home_log(f"Tip: {hint}")
            self._refresh_home_dashboard()
            return
        count = len(result.get("files_written", []))
        runtime = result.get("cl_runtime", "")
        self._queue_home_log(
            f"Agent handoff deployed ({count} file(s)). Mode: {result.get('agent_handoff_mode', 'unified')}"
            + (f", cl_runtime={runtime}." if runtime else ".")
        )
        repair = result.get("repair")
        if repair:
            self._queue_home_log(f"Repaired AGENTS.md — {repair.get('detail', 'updated')}.")
        rosetta = result.get("rosetta_repair")
        if rosetta:
            self._queue_home_log(f"  Rosetta navigation: {rosetta.get('detail')}")
            for rel in rosetta.get("patched") or []:
                self._queue_home_log(f"    patched: {rel}")
        for warning in result.get("warnings", []):
            self._queue_home_log(f"Warning: {warning}")
        for hint in result.get("hints", []):
            self._queue_home_log(f"Tip: {hint}")
        self._refresh_home_dashboard()

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
            self._emit_home_log(f"Opened in Explorer: {result.get('path')}")

    def _toggle_home_guide(self) -> None:
        self._home_guide_expanded = not self._home_guide_expanded
        if self._home_guide_expanded:
            self._home_guide_body.pack(fill="x", padx=0, pady=0)
            self._home_guide_toggle_btn.configure(text="▼")
            self._home_guide_summary.configure(
                text="Plain-English guide — what this tool is and how to use it. Scroll to read.",
            )
        else:
            self._home_guide_body.pack_forget()
            self._home_guide_toggle_btn.configure(text="▶")
            self._home_guide_summary.configure(
                text="Collapsed — expand to read the Hive Planner guide.",
            )

    def _build_home_guide_card(self, parent: tk.Frame) -> None:
        guide_card = card(parent)
        header = tk.Frame(guide_card, bg=COLORS["card"])
        header.pack(fill="x", padx=12, pady=(12, 6))

        self._home_guide_toggle_btn = tk.Button(
            header,
            text="▼" if self._home_guide_expanded else "▶",
            command=self._toggle_home_guide,
            font=FONT,
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            activebackground=COLORS["border"],
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            width=2,
        )
        self._home_guide_toggle_btn.pack(side="left", padx=(0, 8))
        attach_hover_tooltip(
            self._home_guide_toggle_btn,
            "Expand or collapse the Hive Planner guide.",
        )

        title_block = tk.Frame(header, bg=COLORS["card"])
        title_block.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_block,
            text="How to use Hive Planner",
            font=FONT_BOLD,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            anchor="w",
        ).pack(fill="x")
        self._home_guide_summary = tk.Label(
            title_block,
            text=(
                "Plain-English guide — what this tool is and how to use it. Scroll to read."
                if self._home_guide_expanded
                else "Collapsed — expand to read the Hive Planner guide."
            ),
            wraplength=700,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            anchor="w",
        )
        self._home_guide_summary.pack(fill="x", pady=(2, 0))

        self._home_guide_body = tk.Frame(guide_card, bg=COLORS["card"])
        if self._home_guide_expanded:
            self._home_guide_body.pack(fill="x")

        self.home_guide = scrolledtext.ScrolledText(
            self._home_guide_body,
            height=12,
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

        guide_actions = tk.Frame(self._home_guide_body, bg=COLORS["card"])
        guide_actions.pack(fill="x", padx=12, pady=(0, 12))
        secondary_button(
            guide_actions,
            "Open guide in Explorer",
            self._on_open_user_guide,
            tooltip="Open the user guide folder in Windows File Explorer.",
        )
        secondary_button(
            guide_actions,
            "Run setup wizard",
            self._on_reset_onboarding,
            tooltip="Walk through first-time setup again. Your linked projects stay as they are.",
        )

    def _toggle_agent_prompt_templates(self) -> None:
        self._agent_prompt_expanded = not self._agent_prompt_expanded
        if self._agent_prompt_expanded:
            self._agent_prompt_body.pack(fill="x", padx=0, pady=0)
            self._agent_prompt_toggle_btn.configure(text="▼")
            self._agent_prompt_summary.configure(
                text="Copy-paste prompts into Cursor — Rosetta, specs, sources, and cartridges.",
            )
        else:
            self._agent_prompt_body.pack_forget()
            self._agent_prompt_toggle_btn.configure(text="▶")
            self._agent_prompt_summary.configure(
                text="Collapsed — expand to browse and copy agent prompts.",
            )

    def _build_agent_prompt_templates_card(self, parent: tk.Frame) -> None:
        templates = default_agent_prompt_templates()
        titles = [template.title for template in templates]
        saved_title = self._agent_prompt_saved_title
        initial_title = (
            saved_title
            if saved_title in titles
            else (titles[0] if titles else "")
        )
        initial_template = get_agent_prompt_template_by_title(initial_title)

        prompt_card = card(parent)
        header = tk.Frame(prompt_card, bg=COLORS["card"])
        header.pack(fill="x", padx=12, pady=(12, 6))

        self._agent_prompt_toggle_btn = tk.Button(
            header,
            text="▼" if self._agent_prompt_expanded else "▶",
            command=self._toggle_agent_prompt_templates,
            font=FONT,
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            activebackground=COLORS["border"],
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            width=2,
        )
        self._agent_prompt_toggle_btn.pack(side="left", padx=(0, 8))
        attach_hover_tooltip(
            self._agent_prompt_toggle_btn,
            "Expand or collapse agent prompt templates.",
        )

        title_block = tk.Frame(header, bg=COLORS["card"])
        title_block.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_block,
            text="Agent prompt templates",
            font=FONT_BOLD,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            anchor="w",
        ).pack(fill="x")
        self._agent_prompt_summary = tk.Label(
            title_block,
            text=(
                "Copy-paste prompts into Cursor — Rosetta, specs, sources, and cartridges."
                if self._agent_prompt_expanded
                else "Collapsed — expand to browse and copy agent prompts."
            ),
            wraplength=700,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            anchor="w",
        )
        self._agent_prompt_summary.pack(fill="x", pady=(2, 0))

        self._agent_prompt_body = tk.Frame(prompt_card, bg=COLORS["card"])
        if self._agent_prompt_expanded:
            self._agent_prompt_body.pack(fill="x")

        picker_row = tk.Frame(self._agent_prompt_body, bg=COLORS["card"])
        picker_row.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(
            picker_row,
            text="Template",
            bg=COLORS["card"],
            fg=COLORS["fg"],
            font=FONT,
        ).pack(side="left", padx=(0, 8))
        self._agent_prompt_var = tk.StringVar(value=initial_title)
        self._agent_prompt_combo = ttk.Combobox(
            picker_row,
            textvariable=self._agent_prompt_var,
            values=titles,
            state="readonly",
            width=52,
        )
        self._agent_prompt_combo.pack(side="left", fill="x", expand=True)
        attach_combobox_tooltip(
            self._agent_prompt_combo,
            "Pick a scenario — session start, implement task, Load Sources, memory promotion, etc.",
        )

        self._agent_prompt_desc = tk.Label(
            self._agent_prompt_body,
            text=initial_template.description if initial_template else "",
            wraplength=760,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
        )
        self._agent_prompt_desc.pack(anchor="w", padx=12, pady=(0, 6))

        self._agent_prompt_preview = scrolledtext.ScrolledText(
            self._agent_prompt_body,
            height=7,
            font=("Consolas", 9),
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
            wrap="word",
        )
        self._agent_prompt_preview.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        bind_mousewheel(self._agent_prompt_preview)

        prompt_actions = tk.Frame(self._agent_prompt_body, bg=COLORS["card"])
        prompt_actions.pack(fill="x", padx=12, pady=(0, 12))
        primary_button(
            prompt_actions,
            "Copy prompt",
            self._on_copy_agent_prompt,
            tooltip="Copy the selected prompt to the clipboard — paste into Cursor chat.",
        )
        secondary_button(
            prompt_actions,
            "Copy all templates",
            self._on_copy_all_agent_prompts,
            tooltip="Copy every template as markdown for docs or sharing.",
        )

        if initial_template:
            self._show_agent_prompt_template(initial_template)
        self._agent_prompt_combo.bind("<<ComboboxSelected>>", self._on_agent_prompt_selected)

    def _toggle_rosetta_eject(self) -> None:
        self._rosetta_eject_expanded = not self._rosetta_eject_expanded
        if self._rosetta_eject_expanded:
            self._rosetta_eject_body.pack(fill="x", padx=0, pady=0)
            self._rosetta_eject_toggle_btn.configure(text="▼")
            self._rosetta_eject_summary.configure(
                text="Portable planning pack for Gemini, Perplexity, or ChatGPT — teaches hook tagging and Rosetta legend output.",
            )
            self._refresh_rosetta_eject_preview()
        else:
            self._rosetta_eject_body.pack_forget()
            self._rosetta_eject_toggle_btn.configure(text="▶")
            self._rosetta_eject_summary.configure(
                text="Collapsed — expand to export a Rosetta cartridge for external planning AIs.",
            )

    def _rosetta_eject_scope_key(self) -> str:
        from hive_planner.launcher.config import normalize_project_path

        if not self.config.active_project:
            return ""
        return normalize_project_path(self.config.active_project)

    def _saved_rosetta_eject_project_name(self) -> str | None:
        key = self._rosetta_eject_scope_key()
        if key:
            saved = (self._rosetta_eject_project_names.get(key) or "").strip()
            return saved or None
        saved = (self._rosetta_eject_project_names.get("__default__") or "").strip()
        return saved or None

    def _sync_rosetta_eject_for_active(self) -> None:
        """Retarget Rosetta name/preview when the active linked project changes (soft refresh)."""
        if not hasattr(self, "_rosetta_eject_name_var"):
            return
        scope = self._rosetta_eject_scope_key()
        if getattr(self, "_rosetta_eject_synced_scope", None) == scope:
            return
        from hive_planner.rosetta_eject import infer_project_name

        try:
            saved = self._saved_rosetta_eject_project_name()
            default_name = saved if saved else infer_project_name(self._active_linked_root())
            self._rosetta_eject_name_var.set(default_name)
            self._rosetta_eject_synced_scope = scope
            if getattr(self, "_rosetta_eject_expanded", False):
                self._refresh_rosetta_eject_preview()
        except tk.TclError:
            return

    def _rosetta_eject_project_name(self) -> str:
        from hive_planner.rosetta_eject import infer_project_name

        if hasattr(self, "_rosetta_eject_name_var"):
            name = self._rosetta_eject_name_var.get().strip()
            if name:
                return name
        saved = self._saved_rosetta_eject_project_name()
        if saved:
            return saved
        root = self._active_linked_root()
        return infer_project_name(root)

    def _save_rosetta_eject_project_name(self) -> None:
        if not hasattr(self, "_rosetta_eject_name_var"):
            return
        name = self._rosetta_eject_name_var.get().strip()
        key = self._rosetta_eject_scope_key() or "__default__"
        if name:
            self._rosetta_eject_project_names[key] = name
        else:
            self._rosetta_eject_project_names.pop(key, None)

    def _refresh_rosetta_eject_preview(self) -> None:
        if not hasattr(self, "_rosetta_eject_preview"):
            return
        from hive_planner.rosetta_eject import build_session_start_prompt

        text = build_session_start_prompt(project_name=self._rosetta_eject_project_name())
        self._rosetta_eject_preview.configure(state="normal")
        self._rosetta_eject_preview.delete("1.0", "end")
        self._rosetta_eject_preview.insert("1.0", text)
        self._rosetta_eject_preview.configure(state="disabled")

    def _build_rosetta_eject_card(self, parent: tk.Frame) -> None:
        from hive_planner.rosetta_eject import (
            CONTRACT_FILENAME,
            ROSETTA_CARTRIDGE_BLURB,
            ROSETTA_EJECT_TOOLTIP,
            infer_project_name,
        )

        eject_card = card(parent)
        header = tk.Frame(eject_card, bg=COLORS["card"])
        header.pack(fill="x", padx=12, pady=(12, 6))

        self._rosetta_eject_toggle_btn = tk.Button(
            header,
            text="▼" if self._rosetta_eject_expanded else "▶",
            command=self._toggle_rosetta_eject,
            font=FONT,
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            activebackground=COLORS["border"],
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            width=2,
        )
        self._rosetta_eject_toggle_btn.pack(side="left", padx=(0, 8))
        attach_hover_tooltip(
            self._rosetta_eject_toggle_btn,
            ROSETTA_EJECT_TOOLTIP,
        )

        title_block = tk.Frame(header, bg=COLORS["card"])
        title_block.pack(side="left", fill="x", expand=True)
        title_label = tk.Label(
            title_block,
            text="Rosetta cartridge eject",
            font=FONT_BOLD,
            bg=COLORS["card"],
            fg=COLORS["fg"],
            anchor="w",
        )
        title_label.pack(fill="x")
        attach_hover_tooltip(title_label, ROSETTA_EJECT_TOOLTIP)
        self._rosetta_eject_summary = tk.Label(
            title_block,
            text=(
                "Portable planning pack for Gemini, Perplexity, or ChatGPT — teaches hook tagging and Rosetta legend output."
                if self._rosetta_eject_expanded
                else "Collapsed — expand to export a Rosetta cartridge for external planning AIs."
            ),
            wraplength=700,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            anchor="w",
        )
        self._rosetta_eject_summary.pack(fill="x", pady=(2, 0))

        self._rosetta_eject_body = tk.Frame(eject_card, bg=COLORS["card"])
        if self._rosetta_eject_expanded:
            self._rosetta_eject_body.pack(fill="x")

        intro = tk.Label(
            self._rosetta_eject_body,
            text=ROSETTA_CARTRIDGE_BLURB,
            wraplength=700,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            anchor="w",
        )
        intro.pack(anchor="w", padx=12, pady=(0, 4))
        steps = tk.Label(
            self._rosetta_eject_body,
            text=(
                f"1. Copy or export {CONTRACT_FILENAME} and upload it to your planning AI.\n"
                "2. Paste the session prompt below as your first message.\n"
                "3. Save the produced Planning Rosetta Stone to docs/planning-rosetta-stone.md."
            ),
            wraplength=700,
            justify="left",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=FONT_SUBTITLE,
            anchor="w",
        )
        steps.pack(anchor="w", padx=12, pady=(0, 8))

        name_row = tk.Frame(self._rosetta_eject_body, bg=COLORS["card"])
        name_row.pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(name_row, text="Project name", font=FONT, bg=COLORS["card"], fg=COLORS["fg"]).pack(side="left")
        saved_name = self._saved_rosetta_eject_project_name()
        default_name = saved_name if saved_name else infer_project_name(self._active_linked_root())
        self._rosetta_eject_name_var = tk.StringVar(value=default_name)
        self._rosetta_eject_synced_scope = self._rosetta_eject_scope_key()
        name_entry = tk.Entry(
            name_row,
            textvariable=self._rosetta_eject_name_var,
            font=FONT,
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
        )
        name_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        name_entry.bind("<KeyRelease>", self._on_rosetta_eject_name_changed)

        self._rosetta_eject_preview = scrolledtext.ScrolledText(
            self._rosetta_eject_body,
            height=8,
            font=FONT,
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
            wrap="word",
        )
        self._rosetta_eject_preview.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        bind_mousewheel(self._rosetta_eject_preview)
        self._refresh_rosetta_eject_preview()

        eject_actions = tk.Frame(self._rosetta_eject_body, bg=COLORS["card"])
        eject_actions.pack(fill="x", padx=12, pady=(0, 12))
        secondary_button(
            eject_actions,
            "Copy session prompt",
            self._on_copy_rosetta_session_prompt,
            tooltip="Paste after uploading the contract — tells the AI to tag hooks and deliver a Rosetta Stone legend.",
        )
        secondary_button(
            eject_actions,
            "Copy contract",
            self._on_copy_rosetta_contract,
            tooltip="The cartridge core — upload this markdown file to Gemini, Perplexity, or ChatGPT.",
        )
        secondary_button(
            eject_actions,
            "Export to folder…",
            self._on_export_rosetta_cartridge,
            tooltip="Save the full Rosetta cartridge (contract, session prompt, README) to a folder for upload.",
        )

    def _on_rosetta_eject_name_changed(self, _event=None) -> None:
        self._save_rosetta_eject_project_name()
        self._refresh_rosetta_eject_preview()

    def _on_copy_rosetta_session_prompt(self) -> None:
        from hive_planner.rosetta_eject import build_session_start_prompt

        self._save_rosetta_eject_project_name()
        text = build_session_start_prompt(project_name=self._rosetta_eject_project_name())
        self._copy_text_to_clipboard(text)
        self._emit_home_log("Copied Rosetta session-start prompt to clipboard.")
        messagebox.showinfo(
            "Copied",
            "Session prompt copied — upload the contract to your planning AI, then paste this prompt.",
            parent=self.root,
        )

    def _on_copy_rosetta_contract(self) -> None:
        from hive_planner.rosetta_eject import RosettaEjectError, load_session_contract_text

        root = self._active_linked_root()
        try:
            text = load_session_contract_text(repo_root=root)
        except RosettaEjectError as exc:
            messagebox.showerror("Rosetta eject", str(exc), parent=self.root)
            return
        self._copy_text_to_clipboard(text)
        self._emit_home_log("Copied Rosetta Planning Session Contract to clipboard.")
        messagebox.showinfo(
            "Copied",
            "Rosetta Planning Session Contract copied — upload this file to Perplexity, Gemini, ChatGPT, or Claude.",
            parent=self.root,
        )

    def _on_export_rosetta_cartridge(self) -> None:
        from hive_planner.rosetta_eject import RosettaEjectError, eject_rosetta_cartridge

        self._save_rosetta_eject_project_name()
        initial = self._active_linked_root() or Path.home()
        folder = filedialog.askdirectory(
            title="Export Rosetta cartridge to folder",
            initialdir=str(initial),
        )
        if not folder:
            return
        root = self._active_linked_root()
        try:
            result = eject_rosetta_cartridge(
                Path(folder),
                repo_root=root,
                project_name=self._rosetta_eject_project_name(),
            )
        except RosettaEjectError as exc:
            messagebox.showerror("Rosetta eject", str(exc), parent=self.root)
            return
        self._emit_home_log(f"Rosetta cartridge ejected to {result.output_dir}")
        for rel in result.files_written:
            self._emit_home_log(f"  {rel}")
        messagebox.showinfo(
            "Rosetta eject",
            f"Exported to:\n{result.output_dir}\n\nUpload {result.contract_path.name} to your planning AI, "
            f"then paste {result.prompt_path.name}.",
            parent=self.root,
        )

    def _agent_prompt_template_by_title(self, title: str):
        return get_agent_prompt_template_by_title(title)

    def _show_agent_prompt_template(self, template) -> None:
        if template is None:
            self._agent_prompt_desc.configure(text="")
            self._agent_prompt_preview.configure(state="normal")
            self._agent_prompt_preview.delete("1.0", "end")
            self._agent_prompt_preview.configure(state="disabled")
            return
        self._agent_prompt_desc.configure(text=template.description)
        self._agent_prompt_preview.configure(state="normal")
        self._agent_prompt_preview.delete("1.0", "end")
        self._agent_prompt_preview.insert("1.0", template.prompt)
        self._agent_prompt_preview.configure(state="disabled")

    def _on_agent_prompt_selected(self, _event=None) -> None:
        title = self._agent_prompt_var.get()
        self._agent_prompt_saved_title = title
        self._show_agent_prompt_template(self._agent_prompt_template_by_title(title))

    def _selected_agent_prompt_title(self) -> str:
        if hasattr(self, "_agent_prompt_var"):
            try:
                title = self._agent_prompt_var.get().strip()
            except tk.TclError:
                title = ""
            if title:
                return title
        return (self._agent_prompt_saved_title or "").strip()

    def _copy_text_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def _on_copy_agent_prompt(self) -> None:
        title = self._selected_agent_prompt_title()
        template = self._agent_prompt_template_by_title(title)
        if template is None:
            messagebox.showwarning(
                "Agent prompts",
                "Select a template from the list before copying.",
                parent=self.root,
            )
            return
        self._copy_text_to_clipboard(template.prompt)
        self._emit_home_log(f"Copied agent prompt: {template.title}")
        messagebox.showinfo(
            "Copied",
            f"Prompt copied — paste into Cursor chat.\n\n{template.title}",
            parent=self.root,
        )

    def _on_copy_all_agent_prompts(self) -> None:
        from hive_planner.launcher.agent_prompt_templates import format_agent_prompt_templates_markdown

        text = format_agent_prompt_templates_markdown()
        self._copy_text_to_clipboard(text)
        count = len(default_agent_prompt_templates())
        self._emit_home_log(f"Copied all {count} agent prompt templates (markdown)")
        messagebox.showinfo(
            "Copied",
            f"All {count} templates copied as markdown.",
            parent=self.root,
        )

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

    def _show_workspace_picker(self, *, open_after_link: bool = False) -> None:
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

        def finish_link(path: Path) -> None:
            linked = self._link_workspace(path)
            if linked and open_after_link:
                self._on_open_cursor()

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
            finish_link(Path(workspace.path))

        def browse_folder() -> None:
            dialog.destroy()
            path = filedialog.askdirectory(title="Choose Cursor workspace folder")
            if path:
                finish_link(Path(path))

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
        # Keep in-memory Settings (python/cursor paths, etc.) — do not load_config().
        bootstrap_target = pick_hive_bootstrap_target(hive_folder) or hive_folder
        state = summarize_bootstrap_state(bootstrap_target)
        already_known = any(
            normalize_project_path(entry) == normalize_project_path(target)
            for entry in self.config.recent_projects
        )

        needs_setup = notify and (
            state.is_empty
            or state.needs_handoff_repair
            or (not state.hive_ready and (state.has_partial_hive or not already_known))
            or (state.hive_ready and not already_known)
        )
        if needs_setup:
            choice = self._prompt_link_bootstrap_setup(
                bootstrap_target,
                state,
                workspace_label=workspace.name,
            )
            if choice is None:
                return False
            if choice.action == "link_only":
                self.config.add_recent_project(target)
                save_config(self.config)
                _, repair = prepare_linked_project_root(target, repair_agents=True)
                self._queue_handoff_repair_warning(state)
                if notify:
                    messagebox.showinfo(
                        "Workspace linked",
                        f"{workspace.name}\n\nLinked without changing Hive planning files.",
                    )
                self._refresh_home_dashboard(reload_config=False)
                return True
            return self._bootstrap_and_activate(
                bootstrap_target,
                notify=notify,
                link_path=target,
                profile=choice.profile,
                agent_handoff=choice.agent_handoff,
                cl_runtime=choice.cl_runtime,
                setup_action=choice.action,
            )

        self.config.add_recent_project(target)
        save_config(self.config)
        _, repair = prepare_linked_project_root(target, repair_agents=True)
        self._queue_handoff_repair_warning(state)
        if notify:
            if state.hive_ready and bootstrap_target.is_dir():
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
        self._refresh_home_dashboard(reload_config=False)
        return True

    def _on_link_workspace(self) -> None:
        self._show_workspace_picker()

    def _prompt_link_bootstrap_setup(
        self,
        bootstrap_target: Path,
        state: BootstrapState,
        *,
        workspace_label: str,
    ) -> LinkBootstrapChoice | None:
        from hive_planner.agent_handoff import normalize_agent_handoff_mode
        from hive_planner.cl_runtime import resolve_cl_runtime

        cfg = load_config()
        dialog = tk.Toplevel(self.root)
        if state.hive_ready and state.needs_handoff_repair:
            dialog.title("Repair Hive handoff")
        elif state.hive_ready:
            dialog.title("Hive project found")
        elif state.is_empty:
            dialog.title("Set up this folder?")
        else:
            dialog.title("Add Hive planning files?")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.geometry("560x520")

        profile_var = tk.StringVar(value=cfg.default_profile)
        handoff_var = tk.StringVar(value=cfg.default_agent_handoff)
        try:
            default_runtime = resolve_cl_runtime(bootstrap_target)
        except OSError:
            default_runtime = "cursor"
        cl_runtime_var = tk.StringVar(value=default_runtime)

        if state.hive_ready and state.needs_handoff_repair and not state.has_partial_hive:
            default_action = "add_missing"
        elif state.has_existing_hive_files and state.allows_add_missing:
            default_action = "add_missing"
        elif state.has_existing_hive_files:
            default_action = "link_only"
        elif state.is_empty:
            default_action = "create"
        else:
            default_action = "add_missing"
        action_var = tk.StringVar(value=default_action)

        result: list[LinkBootstrapChoice | None] = [None]

        tk.Label(
            dialog,
            text=workspace_label,
            font=FONT_TITLE,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        ).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(
            dialog,
            text=f"Hive files target:\n{bootstrap_target}",
            justify="left",
            wraplength=520,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        if state.hive_ready and state.needs_handoff_repair:
            missing_preview = ", ".join(state.handoff_missing[:4])
            if len(state.handoff_missing) > 4:
                missing_preview += f", +{len(state.handoff_missing) - 4} more"
            tk.Label(
                dialog,
                text=f"Unified handoff incomplete — missing: {missing_preview}",
                justify="left",
                wraplength=520,
                bg=COLORS["bg"],
                fg=COLORS["muted"],
                font=FONT,
            ).pack(anchor="w", padx=16, pady=(0, 8))

        body = tk.Frame(dialog, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=16)

        profile_row = tk.Frame(body, bg=COLORS["bg"])
        profile_row.pack(fill="x", pady=4)
        tk.Label(profile_row, text="Profile", width=14, anchor="w", bg=COLORS["bg"], fg=COLORS["fg"], font=FONT).pack(
            side="left"
        )
        ttk.Combobox(
            profile_row,
            textvariable=profile_var,
            values=["full", "minimal"],
            state="readonly",
            width=30,
        ).pack(side="left", fill="x", expand=True)

        handoff_row = tk.Frame(body, bg=COLORS["bg"])
        handoff_row.pack(fill="x", pady=4)
        tk.Label(
            handoff_row,
            text="Agent handoff",
            width=14,
            anchor="w",
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            font=FONT,
        ).pack(side="left")
        ttk.Combobox(
            handoff_row,
            textvariable=handoff_var,
            values=["unified", "off"],
            state="readonly",
            width=30,
        ).pack(side="left", fill="x", expand=True)

        cl_row = tk.Frame(body, bg=COLORS["bg"])
        cl_row.pack(fill="x", pady=4)
        tk.Label(cl_row, text="CL runtime", width=14, anchor="w", bg=COLORS["bg"], fg=COLORS["fg"], font=FONT).pack(
            side="left"
        )
        ttk.Combobox(
            cl_row,
            textvariable=cl_runtime_var,
            values=["cursor", "headless"],
            state="readonly",
            width=30,
        ).pack(side="left", fill="x", expand=True)

        if state.has_existing_hive_files:
            tk.Label(
                body,
                text="Existing Hive files detected:",
                bg=COLORS["bg"],
                fg=COLORS["fg"],
                font=FONT_BOLD,
            ).pack(anchor="w", pady=(12, 4))
            for value, label in (
                ("link_only", "Link only — add workspace to list without changing files"),
                (
                    "add_missing",
                    "Add missing files only — keep existing Hive files; fill gaps",
                ),
                (
                    "overwrite",
                    "Overwrite bootstrap files — replace START_HERE, AGENTS, rosetta, and profile metadata",
                ),
            ):
                if value == "add_missing" and not state.allows_add_missing:
                    continue
                tk.Radiobutton(
                    body,
                    text=label,
                    variable=action_var,
                    value=value,
                    bg=COLORS["bg"],
                    fg=COLORS["fg"],
                    activebackground=COLORS["bg"],
                    activeforeground=COLORS["fg"],
                    selectcolor=COLORS["card"],
                    anchor="w",
                    justify="left",
                    font=FONT,
                    wraplength=500,
                ).pack(anchor="w", pady=2)
            if action_var.get() == "add_missing" and not state.allows_add_missing:
                action_var.set("link_only")
        else:
            tk.Label(
                body,
                text="Setup choice:",
                bg=COLORS["bg"],
                fg=COLORS["fg"],
                font=FONT_BOLD,
            ).pack(anchor="w", pady=(12, 4))
            for value, label in (
                ("create", "Create Hive planning files in this folder"),
                ("link_only", "Link without Hive files — add workspace to list only"),
            ):
                tk.Radiobutton(
                    body,
                    text=label,
                    variable=action_var,
                    value=value,
                    bg=COLORS["bg"],
                    fg=COLORS["fg"],
                    activebackground=COLORS["bg"],
                    activeforeground=COLORS["fg"],
                    selectcolor=COLORS["card"],
                    anchor="w",
                    justify="left",
                    font=FONT,
                    wraplength=500,
                ).pack(anchor="w", pady=2)

        actions = tk.Frame(dialog, bg=COLORS["bg"])
        actions.pack(fill="x", padx=16, pady=(8, 16))

        def _confirm() -> None:
            action = action_var.get()
            if action == "overwrite" and not messagebox.askyesno(
                "Overwrite Hive files?",
                "This will overwrite core bootstrap files (START_HERE.md, AGENTS.md, "
                "docs/planning-rosetta-stone.md, and profile metadata).\n\n"
                "Other project files are kept. Continue?",
            ):
                return
            result[0] = LinkBootstrapChoice(
                action=action,  # type: ignore[arg-type]
                profile=profile_var.get().strip() or cfg.default_profile,
                agent_handoff=normalize_agent_handoff_mode(handoff_var.get(), default=cfg.default_agent_handoff),
                cl_runtime=cl_runtime_var.get().strip() or "cursor",
            )
            dialog.destroy()

        def _cancel() -> None:
            result[0] = None
            dialog.destroy()

        primary_button(actions, "Continue", _confirm)
        secondary_button(actions, "Cancel", _cancel)
        dialog.protocol("WM_DELETE_WINDOW", _cancel)
        dialog.wait_window()
        return result[0]

    def _bootstrap_and_activate(
        self,
        path: Path,
        *,
        notify: bool = True,
        force: bool = False,
        link_path: Path | None = None,
        profile: str | None = None,
        agent_handoff: str | None = None,
        cl_runtime: str | None = None,
        setup_action: str | None = None,
    ) -> bool:
        from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, normalize_agent_handoff_mode

        cfg = load_config()
        # Prefer the live in-memory config (preserves unsaved Settings). Tests and
        # cold paths may not have set self.config yet — fall back to the disk load.
        if getattr(self, "config", None) is None:
            self.config = cfg
        bootstrap_target = pick_hive_bootstrap_target(path) or path
        state = summarize_bootstrap_state(bootstrap_target)
        resolved_profile = (profile or cfg.default_profile).strip() or cfg.default_profile
        resolved_handoff = normalize_agent_handoff_mode(
            agent_handoff or cfg.default_agent_handoff,
            default=cfg.default_agent_handoff,
        )
        resolved_cl_runtime = (cl_runtime or "cursor").strip() or "cursor"

        action = setup_action
        if action is None and state.has_existing_hive_files:
            choice = self._prompt_link_bootstrap_setup(
                bootstrap_target,
                state,
                workspace_label=bootstrap_target.name,
            )
            if choice is None:
                return False
            action = choice.action
            resolved_profile = choice.profile
            resolved_handoff = choice.agent_handoff
            resolved_cl_runtime = choice.cl_runtime

        if action == "link_only":
            self.config.add_recent_project(link_path or path)
            save_config(self.config)
            prepare_linked_project_root(link_path or path, repair_agents=True)
            self._queue_handoff_repair_warning(state)
            self._refresh_home_dashboard(reload_config=False)
            return True

        init_force = force
        if action == "overwrite":
            init_force = True
        elif action == "add_missing":
            init_force = False
        elif action == "create":
            init_force = not state.is_empty and not state.has_partial_hive
        elif state.has_existing_hive_files and not init_force:
            init_force = False

        result = run_project_init(
            cfg,
            target=bootstrap_target,
            name=bootstrap_target.name,
            profile=resolved_profile,
            git_init=False,
            force=init_force,
            agent_handoff=resolved_handoff,
            cl_runtime=resolved_cl_runtime if resolved_handoff == AGENT_HANDOFF_UNIFIED else None,
        )
        if not result.get("ok"):
            detail = result.get("error", "Could not create Hive project.")
            if result.get("files_written"):
                detail = (
                    f"{detail}\n\nPartial bootstrap — {len(result['files_written'])} file(s) written to:\n"
                    f"{result.get('target', bootstrap_target)}"
                )
            messagebox.showerror("Setup failed", detail)
            self._queue_home_log(detail)
            if result.get("files_written"):
                self.config.add_recent_project(link_path or path)
                save_config(self.config)
                prepare_linked_project_root(link_path or path, repair_agents=True)
            self._refresh_home_dashboard(reload_config=False)
            return False
        self.config.add_recent_project(link_path or path)
        save_config(self.config)
        prepare_linked_project_root(link_path or path, repair_agents=True)
        if notify:
            messagebox.showinfo(
                "Hive project ready",
                f"Created planning files in:\n{bootstrap_target}\n\n"
                f"Profile: {resolved_profile}\nHandoff: {resolved_handoff}",
            )
        self._refresh_home_dashboard(reload_config=False)
        return True

    def _projects_tab_selected(self) -> bool:
        notebook = getattr(self, "notebook", None)
        if notebook is None:
            return False
        try:
            if not notebook.winfo_exists():
                return False
            return str(notebook.tab(notebook.select(), "text")).strip().lower() == "projects"
        except tk.TclError:
            return False

    def _resolve_open_cursor_target(self) -> str | None:
        """Pick which linked path Open in Cursor should launch.

        On the Projects tab, prefer a valid list selection (highlighted row). Elsewhere
        (Home), prefer active_project so the dashboard's Active project is what opens.
        Fall back to the first recent link that still exists on disk.
        """
        from hive_planner.launcher.config import first_existing_recent_project

        if self._projects_tab_selected():
            selected: Path | None = None
            if hasattr(self, "recent_list") and hasattr(self, "_recent_project_paths"):
                try:
                    selected = self._selected_recent_path()
                except (IndexError, tk.TclError, AttributeError):
                    selected = None
            if selected is not None:
                selected_s = normalize_project_path(selected)
                if selected_s and _linked_path_exists(selected_s):
                    return selected_s

        active = normalize_project_path(self.config.active_project) if self.config.active_project else ""
        if active and _linked_path_exists(active):
            return active

        fallback = first_existing_recent_project(self.config)
        return fallback or None

    def _on_open_cursor(self) -> None:
        root = self._resolve_open_cursor_target()
        if not root:
            if messagebox.askyesno(
                "No linked workspace",
                "Link a Cursor workspace first?\n\n"
                "Pick one from Cursor's recent list, or browse to your repo folder.",
            ):
                self._show_workspace_picker(open_after_link=True)
            return
        # Keep Home/dashboard in sync when opening a list selection that was not active yet.
        if normalize_project_path(self.config.active_project or "") != normalize_project_path(root):
            # Do not load_config() here — that would discard unsaved Settings tab edits.
            self.config.add_recent_project(Path(root))
            save_config(self.config)
            if self._dashboard_alive():
                # Refresh header/status/CI/Rosetta/Output for the newly active project.
                self._soft_refresh_dashboard(reload_config=False)
            else:
                # Dashboard not built yet — still retarget scoped in-memory state.
                self._sync_home_log_for_active()
                self._sync_pending_memory_for_active()
                self._sync_ci_report_for_active()
                if hasattr(self, "recent_list"):
                    self._populate_recent_list(prefer_path=root)
        result = open_in_cursor(Path(root), config=self.config)
        if not result.get("ok"):
            messagebox.showerror("Open in Cursor", result.get("error", "Failed to launch Cursor"))
            return
        if hasattr(self, "home_log"):
            name = _linked_display_name(root)
            hive_note = "hive ready" if result.get("hive_ready") else "cursor workspace"
            self._emit_home_log(f"Opened in Cursor: {name} ({hive_note})")

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
            self._queue_home_log(detail)
            for warning in result.get("warnings", []):
                self._queue_home_log(f"Warning: {warning}")
            handoff = result.get("handoff") or {}
            for rel in handoff.get("missing") or []:
                self._queue_home_log(f"  missing: {rel}")
            if result.get("target") and result.get("files_written"):
                prepare_linked_project_root(Path(result["target"]), repair_agents=True)
            self._refresh_home_dashboard()
            return
        self.config = load_config()
        self.config.add_recent_project(Path(result["target"]))
        save_config(self.config)
        prepare_linked_project_root(Path(result["target"]), repair_agents=True)
        messagebox.showinfo("Created", f"Project ready at:\n{result['target']}")
        self._clear_new_project_form()
        self._refresh_home_dashboard()

    def _clear_new_project_form(self) -> None:
        """Blank create fields after success; keep profile/handoff defaults."""
        try:
            if hasattr(self, "new_name"):
                self.new_name.set("")
            if hasattr(self, "new_target"):
                self.new_target.set("")
            if hasattr(self, "new_git"):
                self.new_git.set(True)
            if hasattr(self, "new_profile"):
                self.new_profile.set(self.config.default_profile)
            if hasattr(self, "new_agent_handoff"):
                self.new_agent_handoff.set(self.config.default_agent_handoff)
            if hasattr(self, "new_cl_runtime"):
                self.new_cl_runtime.set("cursor")
        except tk.TclError:
            return

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
        self._refresh_home_dashboard()

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
        self._refresh_home_dashboard()

    def _on_save_settings(self) -> None:
        if not self.setup.portable_mode:
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
        self._sync_new_project_defaults()
        self._refresh_home_dashboard()
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
