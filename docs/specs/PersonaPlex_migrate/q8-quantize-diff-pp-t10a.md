# PP-T10a — QLinear diff vs moshi-rag `utils/quantize.py`

**Date:** 2026-11-23  
**Ground truth (read-only):** moshi-rag-src / `.hive/voice-bot/upstream-moshi-rag/moshi/moshi/utils/quantize.py`  
**Working copy:** `code-improvements/personaplex-migrate/moshi/moshi/utils/quantize.py`

Do not edit moshi-rag-src.

| Item | moshi-rag | PersonaPlex working copy |
|---|---|---|
| `assert linear.bias is None` | yes | yes |
| `int8_vectorwise_quant` on float16 | yes | yes |
| `has_fp16_weights = False` | yes | yes |
| `x.half()` in forward | yes | yes |
| **G7** `state.SCB = self.weight_scb.float()` | **no** (`self.weight_scb` only) | **yes** (Hive G7 lesson) |
| `replace_linear_with_qlinear` Linear → QLinear | yes | yes |
| Second pass `child.float()` on existing QLinear | yes | yes |
| `LMModel(..., quantize=)` then `replace_linear_with_qlinear(self)` | moshi-rag | yes |
| `StreamingTransformer` layer-by-layer `to(device)` then replace | moshi-rag | yes; `quantize` is an explicit arg, not leaked into `StreamingTransformerLayer` |
| Replace **before** `CUDAGraphed(forward_codes)` | serve: QLinear at `LMModel.__init__`; graphs in `LMGen._init_streaming_state` | same order (G97) |
| QLinear ctor on **meta** | avoid | `get_moshi_lm` uses real device when `quantize=True` (PP-T10c) |

Export (replace once after bf16) remains **PP-T10b**. Loader int8 skip remains **PP-T10c**.
