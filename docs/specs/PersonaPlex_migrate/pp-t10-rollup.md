# PP-T10 rollup (PP11 / SC-PP6)

**Date:** 2026-11-23  
Parent checkbox after children T10a–e.

| Child | CodeSpec | Artifact |
|---|---|---|
| PP-T10a | `3850293` | QLinear G7; `q8-quantize-diff-pp-t10a.md` |
| PP-T10b | `1f91442` | `scripts/personaplex_q8_local.py` contracts; live 16.7 GB export not run |
| PP-T10c | `e536bb2` | `get_moshi_lm` int8 skip + fp16 remaining; CUDA QLinear matmul |
| PP-T10d | `481ae4d` | Graphs + live sum argument; `pp-t10d-graphs-record.md`; 7B 12.5 Hz not measured |
| PP-T10e | `5917fba` | `scripts/personaplex_sc_pp6_judge.py`; SC-PP6 **fail closed** (`pp-t10e-sc-pp6-record.md`) |

**SC-PP6:** not passed. Judge exists; four-way WAV/transcripts do not. Blocks PP-T11 / PP13.

**Not this parent:** Hive step-in (PP-T8), live Opus (PP-T9), cutover (PP-T11).
