<!--
meta:hook_id: voice.experience
meta:status: draft
-->

# Feature Micro Brief: Voice_Bot

**Hook:** `workflow.blueprint_first`, `voice.experience`, `integration.strategy`, `agent.handoff`, `agent.sessions`, `agent.events`, `agent.permissions`, `voice.interruption`, `voice.results`, `editor.context`, `cursor.native_chat`, `cursor.acp`, `security.boundaries`, `resource.constraints`, `research.capabilities`, `change.validation`  
**Holistic link:** [Holistic Context](../00_holistic.md)  
**Macro link:** [Macro Architecture](../10_macro.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before using this feature brief.

- **Spec:** [`docs/specs/Voice_Bot/spec.md`](../../specs/Voice_Bot/spec.md)
- **Plan:** [`docs/specs/Voice_Bot/plan.md`](../../specs/Voice_Bot/plan.md)
- **Tasks:** [`docs/specs/Voice_Bot/tasks.md`](../../specs/Voice_Bot/tasks.md)
- **Primary hooks:** `voice.experience`, `integration.strategy`, `cursor.native_chat`

## Feature name

Voice_Bot — a HIVE Code Planner feature that adds a conversational voice interface to HIVE's planning, context, and coding handoff workflow.

## Goal

HIVE shall provide a continuous spoken conversation that can load the active cartridge, understand editor context, delegate bounded coding work through an adapter, remain available while work runs, and report only evidence-backed progress and results.

## Scope

| In scope | Out of scope |
|---|---|
| HIVE-owned voice session, transcript, and task state | Replacing Cursor's native voice provider without a supported API |
| Cartridge-aware context loading and traceability | Making a specific voice model a HIVE architectural dependency |
| Editor context snapshots | Treating an ACP session as the already-open native Agent chat |
| Narrow coding-task delegation | Unrestricted shell access from the voice layer |
| Progress, approval, result, and cancellation events | Claiming success from a completed turn alone |
| Native-chat capability investigation | Production edits before permission and stale-buffer checks pass |

## Proposed boundary

```text
Voice service
  -> tool-capable controller
  -> Cursor extension (editor context and approvals)
  -> preferred: verified native Agent handoff
  -> fallback: explicitly owned persistent ACP session
  -> shared task evidence
  -> written result + grounded spoken summary
```

## Inputs and outputs

Inputs include finalized user speech, workspace identity, active file, selection, document version, dirty state, diagnostics, and explicit approval.

Outputs include transcript events, task identifiers, progress and permission events, diffs, test evidence, written results, and short spoken updates.

## Acceptance criteria

- A voice session can start, continue, and end without silently cancelling unrelated coding work.
- “Explain this” uses the captured selection and workspace context.
- Coding work remains separate from ordinary conversation while the task runs.
- Speech interruption stops playback without cancelling coding.
- Coding cancellation is explicit and does not imply rollback.
- Permission requests are correlated to the exact task and action.
- Stale or dirty editor context is detected before conflicting writes.
- Spoken completion claims match recorded task and test evidence.
- Spoken test claims match the R8 test-state mapping (`passed`, `failed`, `not_run`, `unknown`) for every completed task (SC-013; tests belong to T011).
- Secret-bearing files or selections are excluded from the snapshot and marked `excluded: secret` (R2; tests belong to T014).
- The voice controller tool registry exposes only the R18 tool names; a probe for any shell or filesystem tool fails (R18; tests belong to T014).
- Replacing the voice adapter with a second stub adapter leaves session, task, permission, and evidence contracts unchanged (R11; tests belong to T014).
- An over-limit instruction, snapshot, or diff is rejected or flagged `truncated`, and a test asserts the flag (R21; tests belong to T014).
- Native-chat handoff is either demonstrated on a pinned version or clearly reported unavailable.
- The ACP fallback remains visibly separate from Cursor’s native chat.

## Edge cases

- Call end during a pending approval: the task continues, the approval times out per R6, and no speech follows (R25; tests in T020).
- Restart: `submitted`, `running`, `awaiting_approval`, and `cancel_requested` become `unknown` (`hive_restarted`); pending approvals become `timed_out`; `queued` and `held` entries are discarded unless the session resumes within 300 seconds (R26).
- One pending approval per session; a second request is refused with `approval_already_pending` (R27).
- Snapshot scope: no active file gives `file: null`; unsaved and binary files are excluded (R28).
- Dedupe scope is per session; a retry after restart returns the existing task, including `unknown` (R29).
- Limits and timeouts come from the `voice_bot` config object (T001a), not from handlers (R21).

- Duplicate or retried tool calls must not create duplicate coding tasks.
- Follow-ups are queued until concurrent steering is verified.
- Disconnects, timeouts, and shutdowns preserve task state and avoid duplicate work.
- Tests not run must never be reported as passed.
- Unanswered approvals must not unblock execution.
- External coding results must not be narrated by Moshi until result grounding is demonstrated.

## Validation

Use the decision gates in `planning.rosetta`: native handoff, coding transport, voice grounding, editor integrity, concurrent conversation, and safe execution. Begin with a read-only task, then contextual follow-up, then interruption and failure paths before enabling edits.

Record gate results in `docs/specs/Voice_Bot/evidence-register.md`. Re-run `ingest --embed`, `emit --feature Voice_Bot`, and optional `translate --no-promote` when tertiary sources change; merge improvements into spec before `cartridge-promote`.
