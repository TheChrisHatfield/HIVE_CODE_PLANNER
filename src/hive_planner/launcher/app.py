from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from hive_planner.launcher.config import LauncherConfig, load_config, save_config
from hive_planner.launcher.service import (
    get_setup_status,
    open_path_in_explorer,
    run_install,
    run_project_ci_check,
    run_project_init,
    run_project_map_sync,
    summarize_project,
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
)


class HivePlannerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = load_config()
        self.setup = get_setup_status(self.config)
        self._wizard_step = 0
        self._bg_generation = 0

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
                    return
                try:
                    on_done(result)
                except tk.TclError:
                    return

            self.root.after(0, finish)

        threading.Thread(target=runner, daemon=True).start()

    def _invalidate_bg_callbacks(self) -> None:
        self._bg_generation += 1

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
                text="• Bootstrap Hive projects with Delta + Spec Kit stubs\n"
                "• Run ci-check health gates before handoff\n"
                "• Sync impact maps and open projects in Explorer",
                justify="left",
                font=FONT,
                bg=COLORS["card"],
                fg=COLORS["muted"],
            ).pack(anchor="w", padx=12, pady=(0, 12))
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
            secondary_button(actions, "Install / update", self._on_install)
            primary_button(actions, "Continue →", lambda: self._advance_wizard(2))
        elif self._wizard_step == 2:
            paths_card = card(body)
            card_title(paths_card, "Paths")
            self._hive_root_var = tk.StringVar(value=str(self.config.normalized_hive_root()))
            self._python_var = tk.StringVar(value=self.config.python_executable)
            self._field(paths_card, "Hive planner root", self._hive_root_var, browse=True)
            self._field(paths_card, "Python command", self._python_var)
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
        proj = self.config.active_project or "(no project selected)"
        tk.Label(header, text=f"Active: {proj}", font=FONT_SUBTITLE, bg=COLORS["bg"], fg=COLORS["muted"]).pack(
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

    def _build_home_tab(self, parent: tk.Frame) -> None:
        stats = card(parent)
        card_title(stats, "Status")
        row = tk.Frame(stats, bg=COLORS["card"])
        row.pack(fill="x", padx=12, pady=(0, 12))
        for title, value in [
            ("Hive", self.setup.hive_version or "not installed"),
            ("Feature", self._active_feature_label()),
            ("Recent", str(len(self.config.recent_projects))),
        ]:
            cell = tk.Frame(row, bg=COLORS["secondary"], padx=12, pady=10)
            cell.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(cell, text=value, font=("Segoe UI", 14, "bold"), bg=COLORS["secondary"], fg=COLORS["primary"]).pack()
            tk.Label(cell, text=title, font=FONT_SUBTITLE, bg=COLORS["secondary"], fg=COLORS["muted"]).pack()

        actions = tk.Frame(parent, bg=COLORS["bg"])
        actions.pack(fill="x", padx=16, pady=8)
        primary_button(actions, "Run health check", self._on_ci_check)
        secondary_button(actions, "Sync impact maps", self._on_map_sync)
        secondary_button(actions, "Open in Explorer", self._on_explore)

        log_card = card(parent)
        card_title(log_card, "Output")
        self.home_log = scrolledtext.ScrolledText(
            log_card,
            height=14,
            font=("Consolas", 9),
            bg=COLORS["secondary"],
            fg=COLORS["fg"],
            relief="flat",
            wrap="word",
        )
        self.home_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.home_log.configure(state="disabled")

        check_card = card(parent)
        card_title(check_card, "Latest ci-check")
        self.ci_list = tk.Listbox(check_card, height=6, font=FONT, bg=COLORS["card"], fg=COLORS["fg"], relief="flat")
        self.ci_list.pack(fill="x", padx=12, pady=(0, 12))

    def _build_projects_tab(self, parent: tk.Frame) -> None:
        form = card(parent)
        card_title(form, "New project")
        self.new_name = tk.StringVar()
        self.new_target = tk.StringVar()
        self.new_profile = tk.StringVar(value=self.config.default_profile)
        self.new_git = tk.BooleanVar(value=True)
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
        card_title(recent_card, "Recent projects")
        self.recent_list = tk.Listbox(recent_card, height=8, font=FONT, bg=COLORS["card"], fg=COLORS["fg"], relief="flat")
        self.recent_list.pack(fill="x", padx=12, pady=(0, 8))
        for path in self.config.recent_projects:
            self.recent_list.insert("end", path)
        btn_row2 = tk.Frame(recent_card, bg=COLORS["card"])
        btn_row2.pack(fill="x", padx=12, pady=(0, 12))
        secondary_button(btn_row2, "Set as active", self._on_select_recent)

    def _build_settings_tab(self, parent: tk.Frame) -> None:
        form = card(parent)
        card_title(form, "Configuration")
        self.cfg_hive = tk.StringVar(value=str(self.config.normalized_hive_root()))
        self.cfg_python = tk.StringVar(value=self.config.python_executable)
        self.cfg_profile = tk.StringVar(value=self.config.default_profile)
        self._field(form, "Hive planner root", self.cfg_hive, browse=True)
        self._field(form, "Python command", self.cfg_python)
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

    def _field(self, parent, label: str, variable: tk.StringVar, *, browse: bool = False) -> None:
        row = tk.Frame(parent, bg=COLORS["card"])
        row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text=label, width=14, anchor="w", bg=COLORS["card"], fg=COLORS["fg"], font=FONT).pack(side="left")
        entry = tk.Entry(row, textvariable=variable, font=FONT, bg=COLORS["card"], fg=COLORS["fg"], relief="solid", bd=1)
        entry.pack(side="left", fill="x", expand=True)
        if browse:
            secondary_button(row, "Browse…", lambda: self._browse_into(variable))

    def _browse_into(self, variable: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Choose folder")
        if path:
            variable.set(path)

    def _active_feature_label(self) -> str:
        if not self.config.active_project:
            return "—"
        summary = summarize_project(Path(self.config.active_project))
        return summary.active_feature or "—"

    def _append_log(self, widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.configure(state="normal")
        widget.insert("end", text.rstrip() + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _on_install(self) -> None:
        self._run_bg(lambda: run_install(load_config()), self._install_done)

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
        self.setup = get_setup_status(load_config())
        if self.config.onboarding_complete:
            self._show_dashboard()
        else:
            self._show_onboarding()

    def _on_ci_check(self) -> None:
        root = self.config.active_project
        if not root:
            messagebox.showwarning("No project", "Select a recent project first (Projects tab).")
            return
        self._append_log(self.home_log, "Running ci-check…")
        self._run_bg(lambda: run_project_ci_check(Path(root)), self._ci_check_done)

    def _ci_check_done(self, report: dict) -> None:
        if self._is_bg_error(report):
            self._append_log(self.home_log, self._result_detail(report))
            return
        self.ci_list.delete(0, "end")
        for step in report.get("steps", []):
            mark = "✓" if step.get("ok") else "✗"
            self.ci_list.insert("end", f"{mark}  {step.get('name')}: {step.get('detail')}")
        summary = "All checks passed." if report.get("ok") else "Some checks failed."
        self._append_log(self.home_log, summary)

    def _on_map_sync(self) -> None:
        root = self.config.active_project
        if not root:
            messagebox.showwarning("No project", "Select a recent project first.")
            return
        self._append_log(self.home_log, "Syncing impact maps…")
        self._run_bg(lambda: run_project_map_sync(Path(root)), lambda r: self._append_log(self.home_log, str(r)))

    def _on_explore(self) -> None:
        root = self.config.active_project
        if not root:
            messagebox.showwarning("No project", "Select a recent project first.")
            return
        open_path_in_explorer(Path(root))

    def _on_create_project(self) -> None:
        target = self.new_target.get().strip()
        if not target:
            messagebox.showwarning("Missing path", "Choose a target folder.")
            return
        name = self.new_name.get().strip() or None
        profile = self.new_profile.get().strip() or "full"
        git_init = self.new_git.get()
        cfg = load_config()

        def work():
            return run_project_init(
                cfg,
                target=Path(target),
                name=name,
                profile=profile,
                git_init=git_init,
                force=False,
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
        selection = self.recent_list.curselection()
        if not selection:
            messagebox.showwarning("No selection", "Pick a recent project.")
            return
        path = self.recent_list.get(selection[0])
        self.config.add_recent_project(Path(path))
        save_config(self.config)
        messagebox.showinfo("Active project", path)
        self._show_dashboard()

    def _on_save_settings(self) -> None:
        self.config.hive_planner_root = self.cfg_hive.get().strip()
        self.config.python_executable = self.cfg_python.get().strip() or "py -3.11"
        self.config.default_profile = self.cfg_profile.get().strip() or "full"
        save_config(self.config)
        self.setup = get_setup_status(self.config)
        messagebox.showinfo("Saved", "Settings updated.")

    def _on_reset_onboarding(self) -> None:
        self.config.onboarding_complete = False
        save_config(self.config)
        self._wizard_step = 0
        self._show_onboarding()


def run_app() -> None:
    root = tk.Tk()
    HivePlannerApp(root)
    root.mainloop()
