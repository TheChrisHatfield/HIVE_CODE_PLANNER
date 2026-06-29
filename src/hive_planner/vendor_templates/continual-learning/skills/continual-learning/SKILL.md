---
name: continual-learning
description: Orchestrate Hive continual learning — wiring audit gate, then delegate to `agents-memory-updater`.
disable-model-invocation: true
---

# Continual Learning (Hive)

Keep `AGENTS.md` current by delegating the memory update flow to one subagent, with Hive symbiotic gates.

**Contract:** [docs/cl-spec-integration.md](../../../../../../docs/cl-spec-integration.md)

## Trigger

Use when the user asks to mine prior chats, maintain `AGENTS.md`, or run the continual-learning loop.

## Pre-flight (CL-3 — required)

Before calling `agents-memory-updater`:

1. Confirm **Integration wiring audit** passed for changes in this session (`.cursor/rules/integration-wiring-audit.mdc`).
2. If the user has not validated integration wiring, stop and ask them to complete the audit checklist first.
3. Read `.cursor/plugins/hive-continual-learning/WORKFLOW.md`.

Do not bypass this gate. Do not edit `AGENTS.md` in the parent skill.

## Workflow

1. Verify wiring audit complete (user confirmation or checklist evidence in session).
2. Call `agents-memory-updater`.
3. Return the updater result.

## Guardrails

- Keep the parent skill orchestration-only.
- Do not mine transcripts or edit files in the parent flow.
- Do not bypass the subagent.
- Behavioral facts belong in Spec Kit `spec.md`, not `AGENTS.md`.
