# Source

Application code for Hive Code Planner.

## CLI

```powershell
cd d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER
py -3.11 -m pip install -e ".[dev,pdf,docx]"
py -3.11 -m hive_planner ingest
py -3.11 -m hive_planner emit --feature cartridge-compiler-v2
py -3.11 -m hive_planner emit --feature my-feature --promote
py -3.11 -m hive_planner cartridge-promote --feature my-feature
py -3.11 -m hive_planner impact --feature change-impact-v1 --files src/hive_planner/impact.py
py -3.11 -m hive_planner status
py -3.11 -m pytest
```

Package: `src/hive_planner/`  
Specs: `docs/specs/cartridge-compiler-v2/`, `docs/specs/change-impact-v1/`  
Impact maps: `docs/change-impact/`
