# PP-T11 — SC-PP8 cutover

**Date:** 2026-11-23

| Item | Result |
|---|---|
| Default `speech_child` | **`moshi_q8`** (fail closed) |
| Gates SC-PP2/3/6/7/11 + PP-T9 | not all true |
| Encoder remains | yes (`encoder_autostart` default unchanged) |
| moshika-rag speech weights required | **no** |
| SC-PP9 / SC-PP10 | not required for this default |
| SC-PP8 | **fail closed** |

Do not treat this file as an SC-PP8 pass. Flipping `pp-t11-cutover-gates.json` to all true is what allows `personaplex` as the Voice_Bot default.
