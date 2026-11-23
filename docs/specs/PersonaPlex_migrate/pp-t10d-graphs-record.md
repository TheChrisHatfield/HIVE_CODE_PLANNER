# PP-T10d — CUDA graphs + live streaming_sum

**Date:** 2026-11-23  
**Machine:** Tesla T10, CUDA available  
**q8 7B file:** not present (export still operator A40)

| Check | Result |
|---|---|
| `graphed_main(input_, streaming_sum)` | yes (G170) |
| `NO_CUDA_GRAPH=1` skips capture | yes (`cuda_graphs_enabled()` / `CUDAGraphed._graph is None`) |
| Graphs **on** + **updated** sum tensor | **PASS** — `CUDAGraphed(add_sum)` replay `copy_` sees the new sum (`tests/test_personaplex_pp_t10d.py`) |
| 12.5 Hz 7B `LMGen.step` | **not measured** (no `model.q8.safetensors`; 16.7 GB bf16 does not fit this 17 GB card) |
| Live default | **graphs on** (`NO_CUDA_GRAPH=0`). Do **not** force `NO_CUDA_GRAPH=1`; the sum is a graph argument, not a closed-over buffer. |
| Fallback | If a later 7B graphs+sum run fails, set child `NO_CUDA_GRAPH=1` and re-check 12.5 Hz (SC-PP11 / PP-T9). |

`step_meets_12_5_hz`: step ≤ 80 ms.
