# Hive Planner — portable edition

Copy the entire **HivePlannerPortable** folder to a USB drive or any path. No Python install required.

## First run

On first launch, **HivePlanner.exe** automatically deploys vendored **Spec Kit** and **Continual Learning** overlays into the app folder:

- `.hive/spec-kit/` — Spec Kit templates and workflow
- `.cursor/plugins/hive-continual-learning/` — Continual Learning plugin (Cursor)
- `.hive/upstream-pins.json` — pin snapshot

The setup wizard shows **Spec Kit + CL** status. Use **Verify install** to repair if files are missing.

When you **Deploy agent handoff** on a linked project, the same unified bundle is copied into that project.

## Run

| File | Purpose |
|------|---------|
| `HivePlanner.exe` | Desktop app (no console window) |
| `HivePlanner-cli.bat` | Command-line interface |
| `config/` | Created on first run — settings and linked projects |

Double-click **HivePlanner.exe** to open the dashboard.

## CLI examples

From this folder:

```bat
HivePlanner-cli.bat init --target D:\projects\my-app --name "My App" --agent-handoff unified
HivePlanner-cli.bat ci-check --root D:\projects\my-app
HivePlanner-cli.bat unified-verify --root D:\projects\my-app
```

Or:

```bat
HivePlanner.exe --hive-cli ci-check --root D:\projects\my-app
```

## Notes

- Settings live in `config\config.json` next to the exe (not `%APPDATA%`).
- Git is optional but recommended for project bootstrap with `--git-init`.
- PDF ingest and Load Sources (pymupdf) are bundled for `.txt` and `.pdf` reference files.
- DOCX/HTML/PPTX ingest and embedding features are not bundled; use a dev install for those extras.
- Health check in the portable app skips pytest (no test suite bundled).

## Windows Defender / SmartScreen

Unsigned portable builds may be flagged until reputation builds. This distribution is built **without UPX packing** and includes Windows **version metadata** plus `BUILD-SHA256.txt` for verification.

If blocked: see **DEFENDER.md** in this folder (allow on device, folder exclusion, or report false positive to Microsoft). For production deploy, sign the exe with an Authenticode certificate during build (`-Sign` in `scripts\build_portable.ps1`).

## Build (developers)

From the Hive Code Planner source checkout:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_portable.ps1
```

Output: `dist\HivePlannerPortable\`
