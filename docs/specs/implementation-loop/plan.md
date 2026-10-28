# Plan: implementation-loop

**Hook:** `spec.flow`, `workflow.tools`, `integration.cl_spec`, `integration.wiring_audit`  
**Spec:** [spec.md](./spec.md)  
**Status:** implemented

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before editing this plan.

- **Spec:** [`spec.md`](./spec.md)
- **Delta micro:** [`implementation-loop.md`](../../delta/20_micro/implementation-loop.md)
- **Hooks:** `spec.flow`, `workflow.tools`, `integration.cl_spec`, `change.validation`

## Layer mapping

| Layer | Mapping |
|-------|---------|
| Holistic | Agents implement an approved spec. This feature does not replace Spec Kit or Cursor. |
| Macro | New opt-in step after `tasks.md` exists: Agent loader installs the loop; compiler and cartridge stay unchanged. |
| Micro | `implementation_loop.py` renders prompts, installs them, reports readiness, and enforces coordinator gates including Python `check`. Cursor still runs coder and reviewer. |

## Approach

Mirror bug hunt: the durable behavior lives in Python-rendered markdown, and the CLI, Home, and an explicit init flag all call one install function. Readiness is a real function the status command runs, so a chat cannot treat a missing spec as a successful start.

Pack templates live in `src/hive_planner/implementation_loop.py` (or a package directory of the same name if the role texts are long). They are Hive texts adapted from agentic-loops, with the MIT notice copied to `.hive/implementation-loop/NOTICE` on install. Do not vendor `.github/copilot-instructions.md` or the persona files.

The 4-pack command tells the agent to launch coder and reviewer as separate Cursor agent passes. Python writes the handoff, runs `check`, counts round trips, accepts `result.md`, and commits. The 1-pack command tells the agent to implement and review in its own passes, call Python `check` for the checker result, then call the same Python `commit` gate.

Command discovery at install scans, in order, `pyproject.toml`, `Makefile` / `Justfile` / `Taskfile`, `package.json` scripts, then `.github/workflows`. It fills only commands it can point at an existing script and does not overwrite a value already found. Hive defaults apply when `pyproject` exposes pytest and `hive_planner ci-check` is importable from the target. `push` is `true` only when `git remote` shows `origin`.

State and command files are created once. Later installs must not reset round trips or human-filled commands.

## File targets

| File | Change |
|------|--------|
| `src/hive_planner/implementation_loop.py` | Render, install, readiness, trigger matcher, command discovery, coordinator gates |
| `src/hive_planner/cli.py` | `implementation-loop install`, `status`, `start`, `handoff`, `check`, `accept`, `commit` |
| `src/hive_planner/bootstrap.py` | Optional `--implementation-loop-pack` |
| `src/hive_planner/launcher/service.py` | Home wrappers for install plus status/start/handoff/check/accept/commit |
| `src/hive_planner/launcher/app.py` | Home **Loop controls**; Controls **Run** for install plus status/start/handoff/check/accept/commit |
| `src/hive_planner/launcher/agent_prompt_templates.py` | **Start the implementation loop** copy-prompt |
| `tests/test_implementation_loop.py` | Install, status, trigger, preservation |
| `tests/test_launcher.py` | Home install peek and coordinator wrappers |
| `docs/delta/10_macro.md` | Workflow step after tasks exist |
| `docs/change-impact/project-map.md` | Row added when the module exists |
| `docs/change-impact/test-map.md` | Row added when the test exists |

## Wiring

```text
Chat phrase ("implementation loop" / "code spec") or Home Enable / Install CodeSpec / Loop buttons
  -> install_implementation_loop (once)
  -> .cursor/rules + command
  -> agent reads command, or Home calls the same Python gates
  -> implementation-loop start --feature <id>
  -> implementation-loop handoff --role <role>
  -> implementation-loop check (checker infrastructure)
  -> role pass appends result.md
  -> implementation-loop accept --role <role>
  -> implementation-loop commit
  -> five completes: proposals file -> human -> agents-propose or spec edit
```

Status must fail closed. A pass without `result.md` stays incomplete. Install success means the files exist, not that a feature was implemented.

## Validation

```powershell
py -3.11 -m pytest tests/test_implementation_loop.py tests/test_implementation_loop_coordinator.py tests/test_launcher.py -k "implementation_loop or test_check_" -v
py -3.11 -m hive_planner spec-drift-check --feature implementation-loop
```

Wiring audit for the implementation task: trace CLI and Home to `install_implementation_loop`, trace Home Loop buttons to the same coordinator functions as the CLI, trace the start rule to the command, and trace the command to `implementation-loop status`. Helper-only string tests are not enough; status must run against a temp repo fixture.

## Risks

- An always-on rule that starts on a vague "implement" phrase would hijack ordinary coding. The matcher stays on the phrases in R8.
- Two loops (bug hunt and this one) can both be installed. Their phrases do not overlap. The implementation command tells the agent to finish or pause a bug hunt already in progress before starting.
- Push and pull-request steps fail in a repo with no remote. R5 makes that a local commit plus a report, not a failed feature.
- Retrospective edits to `AGENTS.md` would bypass Continual Learning. The role text sends operational bullets through `agents-propose`.
