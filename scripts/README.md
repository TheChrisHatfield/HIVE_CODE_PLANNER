# HIVE Planner — user guide

Open this from the **Home** tab. The first time, read it from the top.

---

## What Hive Planner does

**HIVE** is the **Hierarchical, Inference, Versatile Engine** Code Planner.

Prompting alone does not give an agentic coding agent enough context for successful software work. Spec-Driven Development closes that gap by giving you a reviewable baseline *before* an agent starts to code. Hive Code Planner is the next step: it helps you ideate and cross-correlate source documents, then hands that context to the agent.

Specification still depends on the context the agent has when it writes. Hive supplies that context with three feeds:

- **Project memory.** Continual memory records how this project specifies and builds software. The agent reads that record when it writes the next specification.
- **Source documents.** You can add text files and PDFs. Hive indexes the text, runs OCR on scanned pages, and uses embedding search to return the passages that match the current question.
- **Long ideation.** You can develop an idea in another system. That text is often too long for an agent to load in one pass. The Planning Rosetta Stone indexes it by concept so the agent opens the section that matches the question.

Hive then passes the context to **Spec Kit**. Spec Kit writes the specification, the plan, and the tasks. The coding agent implements the tasks.

This window is the desktop control panel for that workflow. It runs on your PC (no browser). Use it to link or create a project, open it in Cursor, run a health check, enable loops (**CodeSpec**, bug hunt, agnostic loop), and let an agent call Hive over MCP. The buttons call the same commands as `py -3.11 -m hive_planner ...`.

---

## Start here

| You want to… | Do this |
|--------------|---------|
| Create a new project with the Hive folders | **Projects → Create project** |
| Use a repo you already have | **Projects → Add link…**, then **Set as active** |
| See whether the project is ready to hand off | **Home → Run health check** |
| Fix Python or a failed install | **Settings → Scan for Python**, then **Install / update Hive** |

---

## How to open the app

Double-click `scripts\HivePlanner.lnk` (the hive icon).

| File | What it does |
|------|----------------|
| `HivePlanner.lnk` | Opens the app with the hive icon |
| `HivePlanner.bat` | Opens the same app with a normal Windows icon |
| `HivePlanner.vbs` | Hidden launcher used by the files above |
| `RebuildPortable.bat` | Rebuilds the portable app into `dist\HivePlannerPortable` (takes several minutes) |

Right-click `HivePlanner.lnk` → **Pin to Start** or **Pin to taskbar**.

Optional desktop shortcut:

```powershell
cd path\to\HIVE_CODE_PLANNER\scripts
powershell -ExecutionPolicy Bypass -File .\CreateHivePlannerShortcut.ps1 -Desktop
```

---

## First time you open it

A four-step setup wizard runs once.

1. **Welcome.** Click **Get started**.
2. **Setup.** The app looks for Python (3.10 or newer), a Hive install, and Git. Git is optional. If Python is missing, click **Scan for Python**, pick one, then **Use selected**. If Hive is missing, click **Install / update** (needs the network once). Then **Continue**.
3. **Paths.** **Hive planner root** is the folder where this Hive Planner repo lives. **Python command** is usually `py -3.11`. Use **Scan…** if you are not sure. Then **Continue**.
4. **Ready.** Click **Open dashboard**.

You get four tabs: **Home**, **Controls**, **Projects**, **Settings**.

Choices are saved in `%APPDATA%\HivePlanner\config.json`. You do not need to edit that file.

To see the wizard again: **Settings → Reset onboarding**, or **Home → Run setup wizard**.

---

## Home

Home acts on the **active project** (the folder selected on **Projects**). If none is selected, go to **Projects** first.

Buttons sit in titled groups. **Arrange groups** (or **Settings → Arrange Home groups**) lets you rename a heading and move groups or buttons. **Reset groups** restores the default layout.

| Button | What it does |
|--------|----------------|
| **Run health check** | Checks planning files, specs, maps, and vendor overlays on the active project. Read **Output** at the bottom if a step fails. |
| **Open in Cursor** | Opens the active project in Cursor. |
| **Sync impact maps** | Refreshes the files that list which source files and tests a planning change touches. |
| **Deploy agent handoff** | Copies Spec Kit and Continual Learning into the project (`.hive/spec-kit/`, `.cursor/plugins/hive-continual-learning/`, `.hive/upstream-pins.json`). Run it again after you update Hive Planner. |
| **Load cartridge…** | Add reference docs, turn a research note into a draft cartridge, or import a cartridge folder. |
| **Load Sources…** | Copy `.txt` and `.pdf` files into the project so agents can search them. Image-only PDFs are read with Tesseract when it is installed. |
| **Open in Explorer** | Opens the project folder in File Explorer. |
| **Loop controls** | Opens the **Controls** tab. |
| **CodeSpec** | Opens **Controls** and scrolls to a CodeSpec block. If the tab only has other loops, it adds a CodeSpec block. |
| **Verify vendor pins** | Checks that the Spec Kit and Continual Learning copies match the versions Hive expects. |
| **Scan legacy deployment** | Looks for an older marketplace install of Continual Learning. |
| **Agent prompt templates** | Prompts you can paste into Cursor chat. |
| **Rosetta cartridge eject** | Exports a planning pack you can upload to Gemini, Perplexity, or ChatGPT. |
| **Check wiring audit** / **Record wiring audit…** | Record that you ran the project’s checks before memory is written into `AGENTS.md`. |
| **Promote memory…** | Applies approved notes into `AGENTS.md`. |

**Output** on Home shows what the last button did.

---

## Controls

Controls runs on the active project. Each block is one loop.

1. Pick the **Loop**.
2. Pick the **Command**.
3. Click **Run** on that block.

**+** adds another block, so a bug hunt can sit next to CodeSpec. New blocks start **collapsed**. **▾** / **▸** hides or shows that block's fields; Loop, Command, and Run stay. **−** removes a block. The last block stays. The fields under the dropdowns change with the loop you picked.

| Loop | What it is for | Commands | Fields on that block |
|------|----------------|----------|----------------------|
| **Bug hunt** | Finds and fixes bugs in the project, then commits locally. Saying **bug hunt** in Cursor chat starts it after Enable. | Enable, Check install | Fix ceiling (1–200 committed fixes; default 50). Pause seconds (blank is 10; 0 skips the wait). The stop hook waits, then starts the next pass |
| **CodeSpec** | Codes the open tasks in a finished spec, one task at a time. It does not write the spec. | Enable, Check pack, Status, Start, Handoff, Check, Accept, Commit | Pack, feature id, allow dirty start, force feature, continue after cap. A step list shows the pack order and where it stopped. |
| **Agnostic loop** | Picks the next small slice of work and pauses for a review. This is not a bug hunt and it does not code a spec. | Enable, Check install, Rewards, Status, Arm, Begin, Review, Observe hit, Observe miss, Choose | Reward, cycles, review note, open counts, sims, horizon, seed, arm after choose |

The result for that block shows on the block. Home **Output** gets a copy.

**Home → Loop controls** opens this tab where you left it. **Home → CodeSpec** opens it on a CodeSpec block.

---

## Implementation loop

On the Controls tab this loop is named **CodeSpec**. Use it when the feature already has `spec.md`, `plan.md`, and `tasks.md`.

1. **Home → CodeSpec**, or **Home → Loop controls** and pick **CodeSpec**.
2. **Enable**, pick **1-pack** (one pass) or **4-pack** (coder, then check, then reviewer), then **Run**.
3. **Status**, then **Start**, then **Run**.
4. After the code change: **Check** (build, quick tests, wiring audit), then **Run**.
5. **Accept**, then **Commit**, after check and review passed.

You can also type **implementation loop** or **code spec** in Cursor chat on that project. **Install CodeSpec** on Controls installs on the Cursor window in front.

New projects do not install this loop unless you pass `--implementation-loop-pack`.

From this loop, do not merge, push to the main branch, force-push, or deploy.

Command, if you prefer a terminal:

```powershell
py -3.11 -m hive_planner implementation-loop
```

Subcommands: `status`, `start`, `handoff`, `check`, `accept`, `commit`.

---

## Agnostic loop

This loop chooses one kind of work, does one slice, then stops for a review. It is not a bug hunt and it is not CodeSpec.

1. **Home → Loop controls**.
2. On a block, pick **Agnostic loop**, then **Enable**, then **Run**. That copies the kit into the project.
3. **Arm** a reward (for example `inspect`) for a number of cycles. **Begin** opens one slice. **Review** saves your note and pauses. **Observe hit** or **Observe miss** records how that kind of work went. **Choose** picks the next reward.

To rename the kinds of work, replace `.hive/agnostic-loop/catalog.json` in the project.

In Cursor chat, say **agnostic loop** or **hive loop kit**.

New projects do not install this loop unless you pass `--agnostic-loop`.

```powershell
py -3.11 -m hive_planner agnostic-loop
```

The project can also run `py -3.11 scripts/agnostic_loop.py` with `arm`, `begin`, `review`, `observe`, `choose`, or `status`.

---

## Projects

**Use a repo you already have**

1. **Add link…**
2. Choose the folder. It should contain `START_HERE.md` or other Hive planning files.
3. **Set as active**.
4. **Open in Cursor** when you want to edit.

**Create a project**

1. Enter a name and a target folder. The folder must be outside the Hive Planner repo.
2. **Profile:** **full** adds more starter files. **minimal** adds fewer.
3. **Create project**.
4. Open the new folder in Cursor and start from `START_HERE.md`.

**Recent projects:** select one and click **Set as active**. Home then uses that folder.

---

## Settings

| Control | What it does |
|---------|----------------|
| **Hive planner root** | Folder where this Hive Planner repo lives |
| **Python command** | Command the app uses, usually `py -3.11` |
| **Scan…** | Lists Python installs on this PC |
| **Install / update Hive** | Reinstalls Hive after you pull new code |
| **Reset onboarding** | Shows the first-time wizard again |
| **Show console** | On Windows, shows a window with errors |
| **Agent MCP → Enable** | Lets any MCP agent call this Hive Planner. Writes `hive-planner` into that repo’s `.cursor/mcp.json` for Cursor. Copy launch command for any other agent. Reload MCP in that agent after you add it. |
| **Agent MCP → Disable** | Removes that connection and leaves other MCP servers as they are |
| **Copy launch command** | Copies `py -3.11 -m hive_planner mcp-serve` |

## Agent MCP

Settings **Agent MCP → Enable** lets any MCP agent call this Hive Planner. It writes `hive-planner` into that repo's `.cursor/mcp.json` for Cursor. Copy launch command for any other agent. Reload MCP in that agent after you add it.

CLI: `py -3.11 -m hive_planner mcp-serve` (portable: `HivePlanner.exe --hive-cli mcp-serve`).

---

## Three jobs people use this for

**Work on a project you already have**

1. Open Hive Planner.
2. **Projects → Add link…** and choose the repo.
3. **Open in Cursor**.
4. Before you hand it off: **Home → Run health check** and fix what **Output** lists.

**Start a new project**

1. **Projects**: name, folder, profile, **Create project**.
2. **Open in Cursor**.
3. Follow `START_HERE.md` in the new folder.

**Code a finished spec**

1. **Home → CodeSpec**.
2. **Enable** (1-pack or 4-pack), then **Run**.
3. **Status**, then **Start**, then **Run**.
4. **Check**, then **Run**.
5. **Accept**, then **Commit**, after check and review passed.
6. Or type **implementation loop** or **code spec** in Cursor chat, or press **Install CodeSpec**.

**Python or install failed**

1. **Settings → Scan for Python**, pick one, and save.
2. **Install / update Hive**.
3. **Home → Run health check** and read **Output**.

---

## Words on the screen

| Word | Meaning |
|------|---------|
| **Active project** | The folder Home and Controls use right now |
| **Health check** | The `ci-check` run: planning files, specs, maps, and vendor copies |
| **Profile (full / minimal)** | How many starter files a new project gets |
| **Impact maps** | Lists of source files and tests tied to planning docs |
| **CodeSpec** | The Controls name for coding a finished spec. In chat, say **implementation loop** or **code spec** |
| **Check** (on a CodeSpec block) | Runs build, quick tests, and the wiring audit for the current task |
| **Handoff** (on a CodeSpec block) | Writes instructions for the step the block is on and records the round trip |
| **Unified handoff** | Spec Kit and Continual Learning installed together in the project |
| **Vendor overlays** | `.hive/spec-kit/`, `.cursor/plugins/hive-continual-learning/`, and `.hive/upstream-pins.json` |
| **unified-verify** | Command that checks those copies against the expected versions |
| **vendor-sync** | Command for people who maintain the Hive Planner repo itself, not for a normal project |

---

## Troubleshooting

| What you see | What to do |
|--------------|------------|
| The app does not start | Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/), then **Settings → Scan for Python** |
| “No project selected” | **Projects → Add link…**, or pick a recent project and **Set as active** |
| Health check fails | Read **Output** on Home, fix the folder, and run it again |
| pip or the wrong Python | **Settings → Scan for Python**, save, then **Install / update Hive** |
| A console window flashes | Normal on Windows during some checks. The app tries to hide it. |
| The shortcut icon looks old | Run `CreateHivePlannerShortcut.ps1` again, or press F5 in Explorer |

---

## Unified vendor path (Spec Kit + Continual Learning)

**Deploy agent handoff** copies Hive’s Spec Kit templates and Continual Learning plugin into your project. You do not install them from the Cursor marketplace for Hive work.

| File or folder | What it is |
|----------------|------------|
| `.hive/upstream-pins.json` | The versions Hive expects |
| `.hive/spec-kit/` | Spec Kit templates, including the wiring-audit steps |
| `.cursor/plugins/hive-continual-learning/` | Continual Learning plugin |

| You want to… | Do this |
|--------------|---------|
| Install or refresh those files | **Home → Deploy agent handoff** |
| Check them | **Home → Verify vendor pins**, or `py -3.11 -m hive_planner unified-verify` |
| Find an old marketplace copy | **Home → Scan legacy deployment** |
| Move an old marketplace plugin to Hive’s copy | **Home → Migrate marketplace CL…**, or `py -3.11 -m hive_planner cl-migrate` |

Health check includes this. If the `unified-vendor` step fails, deploy again.

Before notes are written into `AGENTS.md`:

1. Finish the wiring-audit checklist in `tasks.md`.
2. **Home → Record wiring audit…** and enter the command you ran, for example `pytest -q`.
3. **Home → Check wiring audit**.
4. **Home → Promote memory…**.

```powershell
py -3.11 -m hive_planner unified-verify
py -3.11 -m hive_planner wiring-audit record --evidence "pytest -q"
py -3.11 -m hive_planner wiring-audit check
```

People who edit this Hive Planner repo (where `vendor/manifest.json` lives) also use:

```powershell
py -3.11 -m hive_planner vendor-sync --check
py -3.11 -m hive_planner vendor-sync --apply
py -3.11 -m hive_planner unified-verify
```

`vendor-sync --check` checks the pin list. `vendor-sync --apply` downloads the pinned upstream files. Details: `docs/unified-handoff-upstream-forks.md`.

---

## Command line

From a terminal in a project folder, or in this repo for `init`:

```powershell
py -3.11 -m hive_planner init --target C:\path\to\new-app --profile full
py -3.11 -m hive_planner ci-check
```

For day-to-day work, the buttons above are enough.

More detail: `README.md` and `START_HERE.md` in the repo root.
