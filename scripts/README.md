# Hive Planner — user guide (plain English)

Read this top to bottom the first time you use the app. You can come back to it anytime from the **Home** tab in the desktop app.

---

## What is Hive Planner?

Hive Planner is a **small desktop app on your PC**. It helps you work on **Cursor coding projects** that use a consistent planning folder layout (Hive / Delta / spec files).

You do **not** need a web browser. Everything runs locally on your machine.

**Think of it as a control panel** for planning work in Cursor:

- Set up Python and the Hive tools once
- **Link** a project folder you already have, or **create** a new one
- **Open** that folder in Cursor with one click
- **Run a health check** before you hand work off to someone else (or to an AI agent)
- **Sync impact maps** so planning docs stay aligned with code changes

You can still use the command line if you prefer — the app is just a friendlier front-end for the same ideas.

---

## Who is this for?

| You want to… | Hive Planner helps by… |
|--------------|------------------------|
| Start a new Cursor project with the right folders | **Projects → Create project** |
| Use Hive on a repo you already have | **Projects → Open project…** |
| Check “is my project OK?” before a handoff | **Home → Run health check** |
| Fix Python or install issues | **Settings → Scan for Python**, then **Install / update Hive** |

You do **not** need to memorize commands like `ci-check` or `hive_planner init` — the buttons run them for you.

---

## How to open the app

**Easiest (green hive icon):** double-click `scripts\HivePlanner.lnk`

| File | Notes |
|------|--------|
| `HivePlanner.lnk` | Recommended — shows the custom icon |
| `HivePlanner.bat` | Same app, generic Windows icon |
| `HivePlanner.vbs` | Hidden launcher (used by the files above) |

**Tip:** Right-click `HivePlanner.lnk` → **Pin to Start** or **Pin to taskbar**.

**Desktop shortcut (optional):**

```powershell
cd path\to\HIVE_CODE_PLANNER\scripts
powershell -ExecutionPolicy Bypass -File .\CreateHivePlannerShortcut.ps1 -Desktop
```

---

## Your first session (walkthrough)

When you open Hive Planner for the first time, a **short setup wizard** appears. Here is what each step means:

### Step 1 — Welcome

Explains what the app does. Click **Get started**.

### Step 2 — Setup

The app checks your computer:

| Check | What it means |
|-------|----------------|
| **Python** | Hive needs Python 3.10 or newer |
| **Hive installed** | The planning tools must be installed once |
| **Git** | Optional, but useful for version control |

**If Python is missing or wrong:** click **Scan for Python**, pick a version from the list, then **Use selected**.

**If Hive is not installed:** click **Install / update** (needs internet once).

Click **Continue** when the checks look OK.

### Step 3 — Paths

Two paths matter:

| Setting | Usually… |
|---------|----------|
| **Hive planner root** | The folder where you downloaded this Hive Planner repo |
| **Python command** | Something like `py -3.11` — use **Scan…** if unsure |

Click **Continue** when done.

### Step 4 — Ready

Click **Open dashboard**. You land on the main window with three tabs: **Home**, **Projects**, **Settings**.

Your choices are saved automatically in `%APPDATA%\HivePlanner\config.json`. You rarely need to open that file.

**Want the wizard again?** Go to **Settings → Reset onboarding**, or use **Run setup wizard** on Home.

---

## The three tabs (what each one is for)

### Home — day-to-day actions on your active project

The **active project** is the folder Hive Planner is “pointing at” right now. Home shows its status and lets you run common tasks.

| Button | Plain English |
|--------|----------------|
| **Run health check** | Runs a bundle of checks (`ci-check`) on the active project. Green / passing means planning files, specs, and maps look aligned. |
| **Open in Cursor** | Opens the active project folder in the Cursor editor |
| **Sync impact maps** | Updates planning “impact map” files after you change code |
| **Open in Explorer** | Opens the project folder in Windows File Explorer |

The **Output** area at the bottom shows what just ran — read it if something fails.

**No project selected?** Go to **Projects** first (see below).

---

### Projects — link or create a Cursor repo

**Already have a Hive/Cursor repo?**

1. Click **Open project…**
2. Choose the folder (it should contain `START_HERE.md` or Hive planning files)
3. Click **Open in Cursor** when you want to edit code

**Starting something new?**

1. Fill in **Project name** and **Target folder**
2. Pick a **Profile**: **full** = more starter files, **minimal** = lighter setup
3. Click **Create project**
4. Open the new folder in Cursor and start planning

**Recent projects**

- Pick one in the list → **Set as active** to switch which repo Home uses

Each project remembers its profile (**full** or **minimal**) for labels and checks.

---

### Settings — paths, Python, and maintenance

| Control | What it does |
|---------|----------------|
| **Hive planner root** | Where this Hive Planner tool lives on disk |
| **Python command** | How the app runs pip and checks (e.g. `py -3.11`) |
| **Scan…** | Finds Python installs on your PC |
| **Install / update Hive** | Reinstall after you pull new code from git |
| **Reset onboarding** | Shows the first-time wizard again |
| **Show console** (Windows) | Optional debug window for errors |

---

## Three common workflows

### “I want to plan in Cursor on a project I already have”

1. Open Hive Planner
2. **Projects → Open project…** → choose your repo folder
3. **Open in Cursor**
4. Work in Cursor as usual
5. Before a big handoff: **Home → Run health check** and fix anything the log mentions

### “I’m starting a brand-new project”

1. **Projects** → name + folder + profile → **Create project**
2. **Open in Cursor**
3. Use `START_HERE.md` in the new folder as your entry point for planning

### “Something is broken (Python / install / health check)”

1. **Settings → Scan for Python** → pick one → save
2. **Install / update Hive**
3. **Home → Run health check** again and read the Output log

---

## Words you might see

| Term | Simple meaning |
|------|----------------|
| **Active project** | The repo folder Hive Planner is working with right now |
| **Health check / ci-check** | Automated sanity checks on planning files and project layout |
| **Profile (full / minimal)** | How much starter structure a new project gets |
| **Impact maps** | Files that track which code areas planning docs refer to |
| **Handoff** | When you finish a chunk of work and pass it to another person or agent |

---

## Troubleshooting

| Problem | Try this |
|---------|----------|
| App won’t start | Install Python 3.10+ from [python.org](https://www.python.org/downloads/); use **Scan for Python** in the app |
| “No project selected” | **Projects → Open project…** or pick a recent project → **Set as active** |
| Health check fails | Read the steps in the **Output** log on Home; fix the project folder; run again |
| Wrong Python / pip errors | **Settings → Scan for Python** → save → **Install / update Hive** |
| Console windows flash briefly | Normal during some checks on Windows; the app tries to hide them |
| Old shortcut icon | Rerun `CreateHivePlannerShortcut.ps1` or refresh Explorer (F5) |

---

## Optional: command line

Developers can run the same tools from a terminal inside the Hive Planner repo:

```powershell
py -3.11 -m hive_planner init --target C:\path\to\new-app --profile full
py -3.11 -m hive_planner ci-check
```

For everyday use, the desktop app and this guide are enough.

---

## More technical docs

- Repo overview: `README.md` (in the repo root)
- Agent / planning depth: `START_HERE.md`
