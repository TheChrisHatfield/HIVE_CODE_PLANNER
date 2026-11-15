# Voice_Bot — Gap-fill proposal (Haiku sequence 4)

**Status:** proposal (2026-11-11). Executes after [gap-evaluation-plan.md](./gap-evaluation-plan.md) rows exist.  
**Handoff:** [haiku-100k-handoff.md](./haiku-100k-handoff.md) § Prompt points here for micro-task order.  
**User OK scope:** `spec.md` (named patches below), `tasks.md` (T029+), `plan.md` (one pointer), bridge header in code, tests. Never set `edits_enabled: true` in config without explicit human OK (R33).

## How this prop runs in Haiku

1. One **micro-task** per Haiku turn (`T029` … `T040`); read only the row for that task plus target file slices.
2. **Order:** spec patch for R1 **before** T030 code; P0 wiring before P1 adapters; live probes last.
3. Each turn: implement or spec-patch → `py -3.11 -m pytest <named tests> -q` → update `gap-evaluation-plan.md` row `Done when` → `tasks.md` checkbox when green → **CONTINUE Voice_Bot** last.
4. Baseline regression only if the change touches bridge, runner, or extension: `pytest tests -k "voice or acp"` and `npm test` under `extensions/hive-voice-bot`.

## Spec patches (apply when prop row says “spec first”)

### Patch A — R1 session `interrupted` (unblocks P0-2, P0-3)

**Where:** `spec.md` § R1 — HIVE-owned session lifecycle (after the first sentence).

**Proposed addition:**

> Session state transitions (voice layer only; task states follow R20): `active` → `interrupted` when playback is stopped via `interrupt_playback` (R7). `interrupted` → `active` on the next `submit` or `queue_follow_up` in the same session. `interrupted` → `ended` on `end_call`. Playback interruption and call end are not task transitions (R20).

**Acceptance:** `interrupt_playback` sets session `interrupted`; task state unchanged; next submit restores `active`.

### Patch B — Bridge surface for T010 tools (unblocks P0-3, P1-4)

**Where:** `spec.md` R3 or bridge contract table (if present); else bridge module docstring only for T031/T035.

**Proposed HTTP routes (127.0.0.1, same token as T017):**

| Method | Path | Runner call |
|---|---|---|
| POST | `/v1/playback/interrupt` | `interrupt_playback()` |
| POST | `/v1/call/end` | `end_call()` |
| POST | `/v1/cancel` | `cancel_coding_task(task_id, …)` |
| POST | `/v1/queue` | `queue_follow_up(…)` |
| GET | `/v1/diff?workspace=&task_id=` | `task_diff(task_id)` |
| POST | `/v1/reconnect` | `reconnect_task(task_id)` |

All POST bodies: `workspace` required; R23 schema validation; unknown keys → 400.

### Patch C — R22 live buffer (unblocks P0-1)

**Where:** `plan.md` wiring chain or R22 cross-reference.

**Proposed sentence:**

> While the bridge is live, the runner's `set_live_buffer` lookup is installed from the extension poll path (document version + dirty per bound file) so `reply_approval` and `submit` can enforce R22 when `editor_snapshot` is omitted from the POST body.

## Task ledger (proposed T029–T040)

| Task | Gap | Spec first? | Primary files | Tests (add or extend) | Done when |
|---|---|---|---|---|---|
| T029 | P0-1 R22 | Patch C optional | `voice_bridge.py`, `extension.js` | `test_voice_bot_bridge.py` (no-snapshot stale 409); extension test sends version on submit/reply | Bridge installs lookup; stale path blocks without body snapshot |
| T030 | P0-2 R1/R7 | **Patch A required** | `voice_task.py` (`interrupt_playback`, `submit`, `queue_follow_up`) | `test_voice_bot_interrupt.py` | Session `interrupted` on interrupt; task unchanged; submit → `active` |
| T031 | P0-3 bridge routes | Patch B doc | `voice_bridge.py`, `extension.js` | `test_voice_bot_bridge.py`, extension command tests | `/v1/playback/interrupt` and `/v1/call/end` wired; token + schema |
| T032 | P0-4 task_diff | none (fixture latch) | `voice_task.py` | `test_voice_bot_delegation.py` or new diff fixture with mock evidence | Non-stub diff when write evidence exists; latch-off keeps no-evidence |
| T033 | P1-1 STT/Moshi | evidence only | `voice_bot.py`, `evidence-register.md` | `test_voice_bot_speak.py` or G3 note | Moshi STT pinned or explicit `unpinned` + hybrid path documented |
| T034 | P1-2 Pipecat audio | none | `voice_bot.py` `PipecatVoiceAdapter` | `test_voice_bot_speak.py` | `speak` produces adapter payload or documented no-audio default when import missing |
| T035 | P1-3 `transcript.final` | spec slice R14/R18 if needed | new thin `voice_controller.py` or runner hook | integration test: event after submit with `client_request_id` | Controller dispatches one bounded tool on `transcript.final`; no shell |
| T036 | P1-4 cancel/queue/diff/tools HTTP | Patch B | `voice_bridge.py` | `test_voice_bot_bridge.py`, `test_voice_bot_delegation.py` | T036 routes match Patch B; R18 registry tools reachable via HTTP |
| T037 | P2-1 multi-root | R28 slice | `extension.js` `core.js` | `core.test.js` | Workspace bind uses intended root, not always `folder[0]` |
| T038 | P2-2 EDH chain | none | `test/edh/smoke.js`, probe script | EDH 13/13 + one bridge submit with snapshot | Live path: extension → bridge → runner event in one recorded run |
| T039 | P2-3 `reconnect_task` | Patch B | `voice_bridge.py` | `test_voice_bot_edges.py` (R26) | `POST /v1/reconnect` returns reconnect result |
| T040 | P2-4 R24 runtime | none | `voice_bot.py` config read sites | `test_voice_bot_latency.py`, `test_voice_bot_resources.py` + optional probe | Over-budget submit/speak refused or logged per config (not only test asserts) |

## Sequencing (mandatory)

```
Patch A (spec) → T030 → T029 → T031 → T032
→ T036 (rest of HTTP) → T033–T035 (adapters)
→ T037–T040 (P2, live last)
```

T032 may run in parallel with T031 only if no file overlap in the same turn (Haiku rule: one micro-task per turn).

## Human gates (do not bypass)

| Gate | Blocks |
|---|---|
| R33 `edits_enabled: true` | Live agent writes, T032 live diff |
| Patch A not merged | T030 implementation (behavior undefined) |
| G2 login for live ACP | T038 full chain with real agent |

## Wiring audit checklist (every code turn)

Trace: extension command or HTTP → `voice_bridge` handler → `VoiceTaskRunner` method → `state.json` / event → test assertion. Flag **scaffold ≠ implementation** if route exists without runner call.

## Validation for this artifact

Docs-only creation. No pytest run for this file write.
