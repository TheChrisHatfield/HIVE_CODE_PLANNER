# Plan: project-bootstrap-v1

**Hook:** `workflow.project_bootstrap`  
**Spec:** [spec.md](./spec.md)

## Approach

Add `bootstrap.py` with template writers; copy rules from Hive `.cursor/rules/` or packaged `bootstrap_templates/`.

## Validation

```powershell
py -3.11 -m pytest tests/test_bootstrap.py -v
py -3.11 -m hive_planner init --target %TEMP%\hive-init-smoke --name smoke
```
