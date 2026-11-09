# Plan: Voice_Bot

**Hook:** `workflow.blueprint_first`, `voice.experience`, `integration.strategy`, `agent.handoff`, `agent.sessions`, `agent.events`, `agent.permissions`, `voice.interruption`, `voice.results`, `editor.context`, `cursor.native_chat`, `cursor.acp`, `security.boundaries`, `resource.constraints`, `research.capabilities`, `change.validation`  
**Spec:** [spec.md](./spec.md)  
**Delta:** [Voice_Bot.md](../../delta/20_micro/Voice_Bot.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing this plan.

- **Spec:** [`spec.md`](./spec.md)
- **Tasks:** [`tasks.md`](./tasks.md)
- **Delta micro:** [`Voice_Bot.md`](../../delta/20_micro/Voice_Bot.md)
- **Primary hooks:** same canonical set as the spec.md header (`workflow.blueprint_first`, `voice.experience`, `integration.strategy`, `agent.handoff`, `agent.sessions`, `agent.events`, `agent.permissions`, `voice.interruption`, `voice.results`, `editor.context`, `cursor.native_chat`, `cursor.acp`, `security.boundaries`, `resource.constraints`, `research.capabilities`, `change.validation`)

## Approach

HIVE Code Planner is the system of record. The cartridge compiler and Rosetta mapping provide the feature's planning context; HIVE session/task contracts provide orchestration; provider adapters connect voice, editor, and coding systems. No provider becomes the core architecture.

Build the smallest observable bridge first and keep provider-specific behavior behind adapters.

1. Record capability evidence for the installed Cursor, extension, Pipecat, and Moshi versions.
2. Prove a read-only persistent ACP session with streamed updates and a contextual follow-up.
3. Add a normalized task/event model and a narrow delegation interface.
4. Add the Cursor extension context snapshot and visible task/approval state.
5. Add permission handling, queued follow-ups, cancellation, and recovery.
6. Test voice transcription, tool selection, interruption, and result narration independently.
   - Before the contract and queue work (T005, T009), add the `voice_bot` config object (T001a) so every R21 limit and R24 budget is read from one place.
7. Run the native-chat checklist (R19, all four questions) in Phase 4 (T012), after the ACP read-only path in step 2 is proven, so the ACP fallback is the baseline it is compared against. Native handoff is selected only if all four are answered yes on a pinned version (R4); otherwise the ACP fallback stays the coding session. Build order does not decide the priority; evidence does.
8. Enable edits only after the read-only and safety gates pass.
9. Maintain [evidence-register.md](./evidence-register.md) as gates G0–G6 close.

## Cartridge pipeline (operational)

```powershell
py -3.11 -m hive_planner ingest --embed
py -3.11 -m hive_planner emit --feature Voice_Bot --force-delta --emit-rules-seeds
py -3.11 -m hive_planner translate --input "context-library/sources/imported/Mushi AI_Cursor a.md" --feature Voice_Bot --no-promote
py -3.11 -m hive_planner emit --feature Voice_Bot --force-delta
py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot
```

Use `translate` for classification mining; merge distilled bullets into spec manually. Re-emit before promote so draft specseed does not overwrite curated spec.

### Sourcing feedback loop (Rosetta)

1. **Ingest** refreshes embeddings so `emit` retrieval tracks new research.
2. **Emit** rewrites `cartridge/source-context.md` (top excerpts + hooks)—read this before spec edits.
3. **Translate --no-promote** classifies a chosen source into draft cartridge layers; inspect `translator-status.json` counts and rejections.
4. **Merge** build sequence, ownership, and transport boundaries into [spec.md](./spec.md) (see R16, *Build order*, *Runtime delegation sequence*).
5. **Drift-check** confirms spec handoff still matches `AGENTS.md` active lane.

Latest loop (2026-11-09): emit + translate on `Mushi AI_Cursor a.md`; spec updated from `source-context` excerpts (ACP bridge, extension limits, `voice.results`); G0–G6 unchanged in evidence register.

## Gap cascade (4 loops, 9-second pauses)

Process for closing spec gaps. Each loop is a neuron in a cascade: it takes the previous neuron's output as its only input, applies one transform, and emits one typed signal. Raw context does not skip forward.

| Neuron | Input signal | Transform | Output signal |
|---|---|---|---|
| L1 Probe | workspace artifacts: `spec.md`, `plan.md`, `tasks.md`, Delta micro brief, `evidence-register.md` | list candidate gaps as text; no edits | candidate gap list |
| L2 Check | candidate gap list | keep a gap only if it cites one R-row, task, gate, or SC and the artifacts disagree or are silent; drop the rest | confirmed gap list |
| L3 Patch | confirmed gap list | edit only the artifacts each confirmed gap names; add no requirement without an R-row or gate | patched artifact set |
| L4 Review | patched artifact set | cross-check against plan, tasks, and micro brief; run `emit --feature Voice_Bot --force-delta` then `spec-drift-check --feature Voice_Bot` | accepted set, or fail signal to L3 |

**Firing rule:** a neuron fires only when its input is non-empty. An empty confirmed-gap list at L2 ends the cascade with nothing patched.

**Feedback rule:** an L4 fail signal returns to L3 once. A second L4 failure is recorded as an open gap in the `tasks.md` validation log, not as closed.

**Pause rule:** a 9-second pause separates L1→L2, L2→L3, and L3→L4 (provisional, set by the owner). The pause is a cadence for reading each signal before the next neuron fires. It is not a product timeout and does not belong in the `voice_bot` config (R21 covers product limits only).

**Seeded gaps (2026-11-09 pass, applied):** R5/R26 session-end discard; R20/R26 restart reconnect; R6 `question` reply; R8 missing record maps to `unknown`; plan step for T001a before T005/T009; micro brief R25–R29; G6 gate on T015. L1 re-checks these on each run.

## Architecture

HIVE owns voice-session lifecycle, cartridge/context resolution, task identity, event normalization, permissions, and evidence. A voice adapter owns audio/transcription. A controller chooses bounded tools. A Cursor extension adapter owns editor state and visible approvals. A coding adapter owns either a verified native handoff or a separate ACP session. The HIVE task registry is the source of truth for progress and outcomes.

## Key contracts

- `ContextSnapshot`: workspace, file, selection, document version, dirty state, diagnostics, instruction.
- `Task`: task id, session id, context id, state (one of the R20 values), approval state, evidence, and outcome. `client_request_id` is the submit dedupe key (session id + client request id).
- `Event`: normalized transcript, progress, approval, completion, failure, interruption, or cancellation event.
- `SpokenUpdate`: short text derived only from recorded task evidence.

## HIVE integration layers

1. **Cartridge layer:** resolve active feature context through Rosetta hooks and preserve source traceability.
2. **Planning layer:** map spoken intent to HIVE feature/spec/task context without bypassing Spec Kit artifacts.
3. **Orchestration layer:** manage voice sessions, coding tasks, approvals, events, and recovery.
4. **Adapter layer:** connect selected voice, editor, and coding providers behind stable HIVE contracts.
5. **Evidence layer:** retain written results and produce grounded spoken summaries.

## Safety constraints

- Serialize coding turns per owned session until live steering is proven.
- Keep the protocol reader active while approvals are pending.
- Never auto-approve writes or commands.
- Bind all actions to workspace and task identifiers.
- Show diffs and detect stale buffers before writes.
- Validate paths against the bound workspace, authenticate local-service connections, and validate tool arguments before dispatch (R23, T017).
- Measure audio latency and resource use on the pinned runtime; do not assume targets (R24, T018).

## Validation strategy

Use integration tests or scripted capability checks for the ACP round trip, the R8 test-state mapping, speech cadence, the `unknown` disconnect path, approval-kind matching (write, plan, question), contextual follow-up, event routing, permission denial, cancellation, disconnect recovery, and evidence-backed spoken output. Keep native-chat and Moshi claims marked unresolved until reproduced on pinned versions. Restart, call-end, approval-concurrency, snapshot-scope, and dedupe-scope cases (R25–R29) run in `tests/test_voice_bot_edges.py` (T020).
