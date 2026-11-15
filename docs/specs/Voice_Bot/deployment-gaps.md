# Voice_Bot deployment gaps (A–F)

**Date:** 2026-11-12
**Scope:** docs-only scoping pass. No product code changed in this step.
**Source of truth:** [spec.md](./spec.md) § Deployment readiness, R-rows cited below.
**Baseline (2026-11-12, after U10):** `py -3.11 -m pytest tests -k "voice or acp"` 386 passed, 2 skipped (see [acceptance-crosswalk.md](./acceptance-crosswalk.md) L5); unguarded-write tests 9 (`tests/test_voice_bot_unguarded_write.py`); extension 58/58; `spec-drift-check --feature Voice_Bot` ok.

## Verdict by lane

| Lane | Verdict | Why |
|---|---|---|
| Read-only typed preview | READY | G1 labeled ACP, G2 pass, G4 fixture/bridge covered. |
| Full `agent` edit mode | NOT READY for production use (U3, 2026-11-12) | R33 latch on this host, G6 pass, and R35 register row `pass` (`live-write` session `51b937ee`, nonce hash `afc93b69b236ec1a`, CLI `2026.11.05-86047df`). U1 closed the `unguarded_write` blocker on the production path (`_finish`, tests in `tests/test_voice_bot_unguarded_write.py`). U6 (2026-11-12) closed both former residual gaps in code: no-diff writes count as write events, and each approval covers one write. Tests: `tests/test_voice_bot_unguarded_write.py` (9 pass). U10 adds shell-write detection for `execute` calls (see the U10 status line). Lane verdict stays NOT READY until the operator reviews. R35 is probe evidence, not production permission safety. U11b brokered writes are shipped (see Status update). Per-host sign-off: [operator-production-checklist.md](./operator-production-checklist.md). |
| Speech I/O | NOT (typed only; phased plan decided T041) | `hybrid_speech_path()` = `typed_instruction` unless config `stt_provider` names a pinned provider (default null). Phase S0 is the default host state. Phase S1 (Windows Whisper-class STT, T042) has code slices 1–4 and the R13 test, but no live spoken claim. See [spec.md](./spec.md) § Speech I/O rollout. |
| Deploy pack | READY (T045) | `voice-bot pack` writes a VSIX and `install-voice-bot.ps1`; `INSTALL.md` lists the script as step 1, then pip and offline steps. Tests: `tests/test_voice_bot_self_contained.py`. |

**Per-host latch rule (F1, 2026-11-12):** `edits_enabled` in `.hive/voice-bot/config.json` defaults to absent/`false`. Only the operator may set it to `true`, and only on the host where they are running it, after G6 pass and the F2 checklist. No bootstrap, pack, or install script sets it to `true`. The U11b-era `edits_enabled: true` on this host is an operator authorization for this host only, and it does not make the full-agent lane READY for production use.

## Gap table

| ID | Spec row / gate | Current code or test pointer | Gap statement | Proposed task | Order | Notes |
|---|---|---|---|---|---|---|
| **A** Speech I/O | R10, R32, G3, R13, § Speech I/O rollout; T033, T034 | `voice_bot.py` `hybrid_speech_path()`, `speech_adapter(config)` (reads `audio_enabled`), `stt_provider` config, `voice_stt.py` `FasterWhisperAdapter`, `voice_task.py` `submit_spoken`, `PipecatVoiceAdapter`, `TypedInstructionAdapter`; `tests/test_voice_bot_speak.py`, `test_voice_stt_runtime.py`, `test_voice_bot_interrupt.py` (R13), `test_voice_bot_gates.py` | **Decided (T041):** the G3 end state for now is typed (labeled hybrid, phase S0). Spoken mic is open and is not claimed. T042 slices 1–4 and the R13 interruption test are in code. Criterion 4 gate update is done (C1, 2026-11-12). Still missing: live mic capture and live `audio: true` and audio-on interruption rows. | **T041 done** (spec decision). **T042** is partial: code done, live evidence open. | 2 | Gap stays open until live audio rows exist (see spec § Speech I/O rollout) and a G3 change is recorded in the register. **R13 scaffold (Option A, documented, no code change):** speech interruption maps to `interrupt_playback`, which stops playback only and never calls cancel (`voice_task.py` ~L1993). Playback interrupt (`POST /v1/playback/interrupt`) is a separate route from task cancel (`POST /v1/cancel`). `tests/test_voice_bot_interrupt.py` (15 passed) includes `test_r13_playback_interrupt_with_audio_on_leaves_running_task_unchanged`. Pipecat is installed, but `cancel_on_interruption=False` on `VoiceAdapter` and `PipecatVoiceAdapter` is metadata only: no Hive source calls Pipecat `register_function` or sets `tool_options`. R13 is satisfied by the interrupt path, not by Pipecat wiring. Revisit only if the operator picks Option B (Pipecat tool wiring). |
| **B** G4 live `show_diff` | R4, R2, T014; G4 | `extensions/hive-voice-bot` navigate/show_diff; `voice_bridge.py` GET/POST `/v1/editor`; EDH fixture `test/edh` **Closed (T043, 2026-11-12).** Added the documented route `POST /v1/editor/show_diff` (spec R18 route list). The EDH run queues `show_diff` for a completed task through the bridge, and the extension opens it as a visible diff editor and acks it. Evidence: G4 row in `evidence-register.md` (EDH 18/18, VS Code 1.146.0). | **Done.** Tests: `test_show_diff_over_http_queues_the_editor_action_for_a_completed_task`; live `run-edh.ps1`. | 4 | Live proof needs a host with VS Code EDH; rerun `run-edh.ps1` on other hosts. |
| **C** R24 RSS at runtime | R24, T018, T040, T044 | `VoiceTaskRunner._check_r24_rss` (runs on `task.started`); `default_rss_mb` reader; `test_voice_bot_resources.py` | **Closed (T044, 2026-11-12).** RSS is enforced at runtime against `agent_children_rss_target_mb` and `voice_service_rss_target_mb`, logging `r24.over_budget` with `kind=rss` and `scope`, once per scope per task. The 650 MB target is still tight; one live run hit 770 MB, so the target itself is unchanged. | **Done.** Fake-reader tests (7) pass. | 3 | A live over-budget row on a real run is a product decision, not a gap. |
| **D** Deploy ergonomics | R30, SC-014, § Pack for other machines; `test_voice_bot_self_contained.py` | `voice_bot.py` ~L765 `_voice_pack_install_md`; `.hive/voice-bot/deploy-pack/INSTALL.md` | **Closed (T045).** The pack ships a VSIX and `install-voice-bot.ps1`. `INSTALL.md` makes the script step 1 and keeps the pip and offline steps. | **T045 done.** Self-contained tests pass (13). | 5 | If the extension source is missing at pack time, the pack has no VSIX and says so in `INSTALL.md`. |
| **E** Full-agent live write | R33, R35, G6, § live-permission | `voice-bot live-write` (T047); R35 row in `evidence-register.md`; proof JSON `.hive/voice-bot/live-write-run.json`; `.hive/voice-bot/live-write-check.txt` | **Closed (2026-11-12).** Re-run passed: session `51b937ee-4fb4-46a7-b10e-9b487d74ee7f`, `r35: pass`, nonce match, nonce hash `afc93b69b236ec1a`. The earlier 02:21 run (session `3c573c26`) left no nonce hash in any artifact, so it is cited only in `tasks.md`. | **Done.** R35 row is `pass`. Any future live-write run needs a new dated row. | 1 | Ran under the operator's authorization on this host (`edits_enabled: true`). |
| **F** Docs hygiene | Acceptance crosswalk (Acceptance 1–22) | `docs/specs/Voice_Bot/acceptance-crosswalk.md` L5 | **Closed (U4b, 2026-11-12).** Crosswalk L5 now says 386 passed, 2 skipped, dated 2026-11-12. | **T048 done.** | 0 | No open work. |

## Dependency order

1. **E spec (T046)**: defines the write-proof rule that full-agent READY depends on.
2. **A decision (T041)**: spec wording before any speech code.
3. **C (T044)**: runtime RSS, no live host needed.
4. **D (T045)**: pack and install story.
5. **B (T043)**: live EDH, needs a host.
6. **E probe (T047)**: needs the spec from step 1 and a logged-in agent.
7. **F (T048)**: may run any time. It is independent.

## Status update (2026-11-12, T041 pass)

- T046 (R35 spec) and T047 (`live-write` code) are landed. T041 (speech decision) is landed in `spec.md` § Speech I/O rollout.
- E closed 2026-11-12: R35 register row `pass` (see `evidence-register.md`), from a re-run whose payload is saved in `.hive/voice-bot/live-write-run.json`.
- T5-rss (2026-11-12): Operator policy: keep `agent_children_rss_target_mb` at 650 MB, and treat a single live `r24.over_budget` (`kind=rss`) row as a review item, not a reason to change the target, unless repeated runs on the same host exceed it.
- Still open: A (T042 S1: code slices 1–4 and R13 test done; live audio evidence open). Closed after E: C (T044 RSS), B (T043 live `show_diff`).
- D closed by T045 (deploy pack VSIX and install script; deploy lane READY).
- U3 (2026-11-12): full-agent verdict narrowed to NOT READY for production use. U1 is in code and tested.
- U11a (2026-11-12, broker strategy + failing test; no product code changed):
  - Root cause: production `_ensure_session` (`voice_task.py` ~L610) sends `clientCapabilities.fs.writeTextFile: false`. The agent then writes on its own with no `session/request_permission` and no `fs/write_text_file` request (R35 `live-write-run.json` shows `permissions: []` with the file on disk). `_has_unguarded_write` runs only in `_finish`, so the disk is already changed when it fails.
  - Evidence the fix direction is right: the R34 G6 probe initializes with `writeTextFile: true` and observes gated methods (`ACP_G6_INITIALIZE`, `voice_bot.py` ~L1777). `_handle_server_request` (`voice_task.py` ~L678) handles only `session/request_permission` and `fs/read`; `fs/write_text_file` falls through to an unsupported-method error.
  - Strategy (not yet built, U11b): when mode is `agent` and `edits_enabled()`, advertise `writeTextFile: true` and handle `fs/write_text_file` by opening the same approval broker (`_on_permission` path) and writing only after an allow, with R23 path checks and the R22 stale check at that moment. Other modes and other hosts keep `false`.
  - Failing test: `tests/test_voice_bot_write_gate.py` (integrated, via `runner.submit` and the fake ACP child). It asserts an approval is pending before the file exists, and that a deny leaves no file. Fails today with "file exists already=True". The fixture gained `FS_WRITE_REQUEST:<path>`, which self-writes when `writeTextFile` is false and sends `fs/write_text_file` when true.
  - Neighbor tests (`test_voice_bot_unguarded_write.py`, `test_voice_bot_permissions.py`, `test_voice_bot_nn_cascade.py`) still pass: 29 passed.
  - Full-agent verdict stays NOT READY. No `edits_enabled` change on any host.
  - U11b (2026-11-12): brokered provider writes. Agent mode with `edits_enabled()` advertises `clientCapabilities.fs.writeTextFile: true`; other modes stay `false`. `fs/write_text_file` opens the same approval broker (`_open_approval`), and bytes are written in `_resolve_approval` only after an allow, with the R22 stale check run first and the R23 check run again at write time. `.hive/` is refused for provider writes. Deny or stale returns a JSON-RPC error and leaves no file. Green: `test_voice_bot_write_gate.py` 3 passed; `pytest tests -k "voice or acp"` 389 passed, 2 skipped, 0 failed. Full-agent verdict stays NOT READY until the operator reviews. No `edits_enabled` change on any host.
- U7 (2026-11-12, doc only): STT install story. `pip install -e ".[voice]"` pulls the pinned `faster-whisper==1.2.1` and `ctranslate2==4.9.0` (`pyproject.toml`). `ensure-runtime` installs only `VOICE_STACK_PYPI` (`moshi`, `pipecat-ai`), so it does not install or check STT. The pack's `--download-wheels` also fetches only those two, so the offline `--find-links wheels -e ".[voice]"` step will not get the STT pins. Speech stays `typed_instruction` (R10, R32). The generated `INSTALL.md` (`_voice_pack_install_md` in `src/hive_planner/voice_bot.py`) does not yet say this; that wording change is code and is not made here.
- U6 (2026-11-12): both residual permission gaps are closed in code (no-diff writes count as write events; each approval covers one write). Tests: `tests/test_voice_bot_unguarded_write.py`. The lane verdict stays NOT READY until the operator reviews. Keep `edits_enabled` as set by the operator unless they say otherwise.
- U10 (2026-11-12): `execute` tool calls whose command writes files (redirects `>`/`>>`, `tee`, `sed -i`, `mv`, `cp`, `rm`, `mkdir`, PowerShell write cmdlets) now count as write events in `voice_task.py` (`WRITE_COMMAND_RE`, `_is_write_call`). Test: `test_execute_shell_write_without_permission_fails_unguarded` in `tests/test_voice_bot_unguarded_write.py` (9 pass). Residual (T3-u10-doc, 2026-11-12, doc only, regex unchanged):
- **Caught** (`execute` only): `>` and `>>` redirects (not `2>&1` or `>&`), `tee`, `sed -i`, `mv`, `cp`, `rm`, `mkdir`, `del`, `move`, `copy`, `ren`, and the PowerShell cmdlets `Set-Content`, `Add-Content`, `Out-File`, `Remove-Item`, `Move-Item`, `Copy-Item`, `New-Item`.
- **Not caught:** interpreter writes (`python -c "open(...).write(...)"`, `node -e "...writeFileSync..."`), aliases such as `sc`, `touch`, `git checkout -- <file>`, and package installs that write files (`npm install`). Those stay unguarded until a real ACP sample shows the exact command text.
- **False positives** (checked with a probe on 2026-11-12): the bare word `rm` anywhere in the command (`grep -r rm src`) and `->` inside quoted text (`echo "a -> b"`) are counted as writes. These fail closed, so they need a permission but do not allow an unapproved write.
- Probe: 19 sample commands run through `WRITE_COMMAND_RE.search`; results match the lists above.

## Polish decision: gap A (Path A, 2026-11-12)

For the preview ship, gap A is deferred. The default speech path stays phase S0 (`typed_instruction`, `stt_provider` null, `audio_enabled` false). T042 stays partial with its checkbox open, because its live mic and audio evidence rows are not recorded. The G3 wording stays "labeled typed hybrid". No G3 claim is made, no faster-whisper install is added to any host, and no live mic run is done. Gap A reopens only when a T042 live audio row and the S1 criterion 4 gate update exist.

## F4 closeout: production safety residuals (2026-11-13, doc only)

Path A: no interpreter-write repro exists (`tests/fixtures/acp_turn_server.py` has no marker for it), so `_is_write_call` and `WRITE_COMMAND_RE` are unchanged. The U10 "Not caught" list above is the final residual list for interpreter writes:

| Residual | Example | Status | Operator handling |
|---|---|---|---|
| Interpreter file write (Python) | `python -c "open('x','w').write('y')"` | Not caught. No write event, so no unguarded-write failure. | Treat full-agent edits as unverified for this path. Do not rely on the write gate for it. |
| Interpreter file write (Node) | `node -e "require('fs').writeFileSync('x','y')"` | Not caught. | Same as above. |
| Aliases and VCS/package writes | `touch`, `sc`, `git checkout -- <file>`, `npm install` | Not caught. | Same as above. |
| False positives (fail closed) | bare `rm` in `grep -r rm src`; `->` in quoted text | Counted as writes. Needs a permission, but it never allows an unapproved write. | Accepted. |

Cross-links to F3 residuals (task-record evidence, see the R35 section of [evidence-register.md](./evidence-register.md)):

- **Positional secrets not masked:** closed (bug-hunt 2026-11-13). `redact_command()` now also masks the space-form short flag `-p <value>` (for example `-p hunter2` becomes `-p <redacted>`). Test: `test_redact_command_masks_short_p_flag_value`. Attached forms such as `-phunter2` are still not masked.
- **`raw_events` may hold unredacted commands:** closed (bug-hunt 2026-11-13). Each raw ACP payload now passes through `redact_raw_payload()` (same secret masks as `redact_command`, no truncation) before it is retained. Test: `test_raw_events_are_redacted_before_they_persist`. Raw logs may still hold non-credential text, so do not share them outside the host.

Neither residual changes the lane verdicts. Full-agent stays NOT READY for production use until an operator signs the row in [evidence-register.md](./evidence-register.md) § Operator full-agent production approval, and only on the host where they sign.

## G7 live stack checklist (OD-1, 2026-11-14, doc only)

Gate G7 stays **blocked** in `evidence-register.md`. This checklist records what a live run needs. It makes no pass claim. Only `moshi-probe --record` after a real handshake and one audio round trip may set G7 `pass` (T055).

**Server ownership (OD-1):** spec R37 (revised 2026-11-14) says Hive starts a loopback `moshi.server` as a child when `moshi_autostart` is true (default), and never starts a remote URL. T049 still reads "operator-run server." Resolved 2026-11-14: operator chose "Hive owns the server." T049 now matches R37. On a live host, `moshi_autostart` true starts a loopback child; set it false only to run the server by hand.

**Checklist (Runpod-side stack, from the 2026-11-14 handoff; not yet verified in repo):**

1. **Ref encoder:** LISTEN on port `8001`. Observed about 23.5 GB VRAM on the pod.
2. **vLLM:** `/v1` on port `8002`, served with a dummy API key. Qwen2.5-3B was the model. Install in `/tmp/vllm-venv` (vLLM 0.33.0). PATH must include `/tmp/vllm-venv/bin`. The first start failed because `ninja` was not on PATH.
3. **Moshi server env (verified 2026-11-14 on the pod, installed `moshi` 0.2.13 under `/usr/local/lib/python3.12`):** the server needs `REFERENCE_ENCODER_URL=http://localhost:8001` (it exits without it), and it needs `LLM_BASE_URL=http://localhost:8002/v1`, `LLM_API_KEY=dummy`, and `LLM_MODEL_NAME=Qwen/Qwen2.5-3B-Instruct` (it exits with `KeyError: LLM_BASE_URL` without the first). `LLM_BASE_URL` is read at startup, so vLLM must be listening first. The earlier note that the server reads no env vars was wrong for the installed package. The fork's local `server.py` may differ; the pod's installed copy is the one that ran.
4. **Launch (verified flags):** `python3 -m moshi.server --host 127.0.0.1 --port 8998 --device cuda --moshi-weight /runpod-volume/moshika-rag-q8/model.q8.safetensors --config /runpod-volume/moshika-rag-q8/config.json`. The flag is `--config`, not `--config-path`. The q8 Moshi weight loaded (`moshi loaded`). Mimi and the text tokenizer are not on the volume and come from the default HF repo `kyutai/moshiko-pytorch-bf16` (the volume's `llama-3.2` `tokenizer.json` is not the SentencePiece file the loader needs). The run then failed at the RAG LLM step, not at the model.
5. **VRAM / OOM on a single A40:** the encoder (about 23.5 GB) and the Moshi model share one GPU. Check `nvidia-smi` before the Moshi launch. If it runs out of memory, stop the encoder or move one service to another pod. Do not run vLLM and Moshi at the same time on a single A40 unless memory has been checked. **Observed 2026-11-14:** encoder about 23 GB plus vLLM (0.2 share) about 9 GB left about 0.3 GB free; Moshi then died with `torch.OutOfMemoryError` while allocating its KV cache (needed about 12.4 GB). With the stock server, all three are needed at startup, so single-A40 G7 does not fit.
6. **Exec path:** SSH is refused on this pod. Run every command through Runpod MCP `exec-pod`. Do not rely on SSH.
7. **Probe:** `py -3.11 -m hive_planner voice-bot moshi-probe --feature Voice_Bot` reads `moshi_url` (default `ws://127.0.0.1:8998/api/chat`). Run it without `--record` first. Add `--record` only after a real handshake and round trip.
8. **Concurrency lock:** the server takes one global lock per connection (`handle_chat`, `async with self.lock`). A second client during a live call (the spoken-submit gate or a probe) gets `moshi_unreachable` even when the server is up. Stop the call before probing.

### Session 9 pod-only deltas (G7-q8 stack, 2026-11-14, pod `t13xqwp4ilb953`)

These edits were made on the pod only. None is in the repo. Re-apply them if the pod disk is wiped. Each one is a deviation from the runbooks above.

- **vLLM memory:** start vLLM on :8002 with `--gpu-memory-utilization 0.3`. At 0.2 the KV cache failed to allocate next to the encoder.
- **Extra deps:** `/tmp/vllm-venv` needed packages beyond the handoff list. They include `openai`, `transformers==4.55.3`, `websockets`, `sphn`, `httpx`, `fastapi`, `uvicorn`, `scipy`, and `accelerate`. Scan the RAG imports for any others.
- **xformers pin:** install `xformers==0.0.33.post2` with `uv pip install --no-deps`. Version 0.0.36 breaks torch 2.9.1.
- **`arc_encoder.py` (moshi-rag-src):** set `use_fast=True`. Set the tokenizer default to `unsloth/Llama-3.2-3B-Instruct`, because the gated `meta-llama/...` repo fails without access.
- **Cold handshake:** the first `moshi-probe` after boot returned `moshi_unreachable` while STT was still building. Run `/workspace/warm_ws.py` on the pod first. The handshake then returned in about 1.1 s.
- **Probe result (no `--record`):** `g7: pass`, `handshake_ms 1468.0`, `reason handshake_and_round_trip`. This is live evidence only. It is not yet a recorded register row.

### G7 hardware split (decision table, doc only, 2026-11-14)

Single-A40 G7 is ruled out. Items 5 and 8 above record the observed OOM. The options below are for an operator choice. None is run or verified yet.

| Option | Layout | Status | Notes |
|---|---|---|---|
| A. One A40, all three | Encoder (about 23.5 GB) + vLLM (0.2 share, about 9 GB) + Moshi on one GPU | **Not viable** | Observed 2026-11-14: about 0.3 GB free before Moshi, Moshi OOM on KV cache (needs about 12.4 GB). |
| B. One A40, encoder + vLLM only | Pod A runs encoder and vLLM; Moshi not started there | Partial | Proves the two services start. Does not prove G7. |
| C. Two pods, Moshi alone on pod M | Pod M = Moshi only. Pod E = encoder + vLLM. Moshi reaches them through `REFERENCE_ENCODER_URL` and `LLM_BASE_URL` set on pod M at startup. | **Candidate** | Needs a probe path to pod M (`moshi_url` default is loopback; R37 says Hive never starts a remote URL, so the probe host choice is open). Both pods must sit in the same data center as network volume `irfh4yaasw` (EU-SE-1). |
| D. Two pods, vLLM alone on pod V | Pod V = vLLM. Pod R = encoder + Moshi. | Candidate | Same network and data-center constraints as C. Moshi and encoder still share one GPU, so check `nvidia-smi` first. |

**Recommendation for the next decision:** option C. It keeps the Moshi KV cache alone on its GPU. Confirm the probe route before any pod is created.

**Operator cost:** not verified in this chat. Quote the hourly price from a live read (`get-gpu-type` or `list-gpu-types`) before creating any pod. Do not reuse an old number. Each extra pod adds its own hourly rate. Terminate pods when the probe is done.

**Reference data (do not re-download):**
- Pod backups on the local disk: `D:\DRIVE_DOWNLOADS\POD_BACKUPS\prqibnk6q5vpqe` (workspace and root, with `local-sha256.txt`) and `D:\DRIVE_DOWNLOADS\POD_BACKUPS\xj0sjbqjsrd6ym`. Both pods were terminated after download.
- Network volume `irfh4yaasw` (80 GB, EU-SE-1) holds `moshika-rag-q8/` and the ARC tokenizer. It is staged, not proven. See `G7-q8` in [evidence-register.md](./evidence-register.md).

## Out of scope

- Native Composer chat submit (G1 fail, labeled ACP only, non-goal).
- Re-proving T001–T040.

## Deploy hygiene log

- deploy hygiene D1 (2026-11-12): root .gitignore ignores voice-bot bridge-token, bridge.json, runner.lock, state.json, evidence/, config.json, live-write files, and fixture runtime secrets. Validated with git check-ignore -v: all runtime paths match; deploy-pack files not ignored. Note: extensions/hive-voice-bot/test/edh/fixture/.hive/voice-bot/config.json is already tracked in git (no edits_enabled key); ignore rules do not untrack it, so untrack only if operator asks. No commit.

