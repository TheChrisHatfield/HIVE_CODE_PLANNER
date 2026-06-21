# Hive Code Planner

Local Git repository root for Hive Code Planner work.

This repo is used **locally only** (no remote required). All project files live under this directory and should be referenced from here.

## Repository root

```
d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER
```

## Layout

| Path | Purpose |
|------|---------|
| `docs/` | Architecture, decisions, and reference notes |
| `plans/` | Planning artifacts, specs, and task breakdowns |
| `src/` | Source code and scripts |
| `.cursor/` | Cursor IDE rules and project guidance |

## Local Git workflow

```powershell
cd d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER

# Check status
git status

# Stage and commit changes
git add .
git commit -m "Describe your change"

# View history
git log --oneline --graph --decorate
```

## Notes

- Treat this folder as the canonical project root.
- Do not scatter project files outside this directory unless explicitly required.
- Add a remote later with `git remote add origin <url>` if you want GitHub sync.
