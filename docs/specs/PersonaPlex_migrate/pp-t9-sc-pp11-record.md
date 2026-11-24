# PP-T9 — SC-PP11 / PP-E1

**Date:** 2026-11-23

| Item | Result |
|---|---|
| Live `other_mimi` encode/decode in `opus_loop` | **skipped** (warmup may still call it) |
| STT in `opus_loop` | **not present** |
| PCM catch-up yield | `await asyncio.sleep(0)` after each frame |
| Live 12.5 Hz after `0x00` | **not measured** (no q8 live Hive talk) |
| SC-PP11 | **fail closed** |
| PP-E1 | **fail closed** (not Voice_Bot G7) |
| Blocks | PP-T11 / PP13 until a live step-rate row holds |

Do not treat this file as an SC-PP11 or PP-E1 pass.
