# PP-T10e — SC-PP6 text-token judge

**Date:** 2026-11-23

| Item | Result |
|---|---|
| Judge | `scripts/personaplex_sc_pp6_judge.py` |
| Tests | `tests/test_personaplex_pp_t10e.py` |
| Same prompt/WAV run (bf16 vs q8, offline then live) | **not run** — no `model.q8.safetensors`; 16.7 GB bf16 does not fit this 17 GB card |
| SC-PP6 | **fail closed** (G12: a gap note is not a pass) |
| Blocks | PP-T11 / PP13 until a real four-way transcript record holds |

Do not treat this file as an SC-PP6 pass.
