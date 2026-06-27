<!-- DRAFT: review before promoting -->

# Micro Brief: cartridge-translator-v1 (draft)

- **Hook:** `context.document_sourcing`, `compiler.pipeline`, `context.metadata`
- Cartridge Compiler v3 — add HTML, CSV, and PPTX ingestion to the existing normalizer pipeline.
- **Files:** `src/hive_planner/normalizers/*`, `normalizer.py`, `config.py`, `chunker.py`, `pyproject.toml`, tests
- [x] HTML, CSV, PPTX discovered and normalized when deps available - [x] Missing optional dep → warning for that format only; other formats unaffected - [x] Empty HTML → skip with warning (S4A-B1) - [x] Corrupt file or missing dep → skip,...
- ```powershell py -3.11 -m pip install -e ".[dev,pdf,docx,html,pptx]" py -3.11 -m pytest -v py -3.11 -m hive_planner ingest py -3.11 -m hive_planner emit --feature cartridge-compiler-v3 ```
