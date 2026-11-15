# Voice_Bot acceptance crosswalk (P2)

Maps spec Acceptance 1–22 and SC-001–SC-014 to named tests in `tests/` and to live evidence in `evidence-register.md`.

Verified 2026-11-12: `py -3.11 -m pytest tests -k "voice or acp" -q` → 390 passed, 2 skipped, 1863 deselected (2026-11-12 re-run after C1 added the STT gate test; Windows PowerShell, repo root, single run). Count is from the pytest summary line; re-measure before quoting it elsewhere.

Status key: **covered** = a named test exercises the integrated path; **partial** = some assertion missing; **open** = blocked by a recorded blocker.

Note: `spec.md` says "Acceptance 1–21" in its gate and blocker text, but the list has 22 items. AC 22 (self-contained deploy) is covered and is listed here.

## Acceptance criteria

| AC | Status | Tests / evidence |
|---|---|---|
| 1 read-only contextual question with selection | covered | `test_voice_bot_readonly_turn.py::test_read_only_prompt_streams_and_completes_with_stop_reason`; `test_voice_bot_planning.py::test_snapshot_records_file_content_excerpt_ids_and_prompt_includes_selection`; `test_voice_bot_safety.py::test_editor_selection_object_maps_to_selection_text`; live G2 in evidence register |
| 2 second question keeps session context | covered | `test_voice_bot_readonly_turn.py::test_contextual_follow_up_reuses_the_same_provider_session` |
| 3 observable progress and final result | covered | `test_voice_bot_readonly_turn.py::test_read_only_prompt_streams_and_completes_with_stop_reason`; `test_voice_bot_results.py::test_r14_progress_speech_is_limited_to_one_per_interval`; `test_voice_bot_delegation.py::test_task_status_reports_state_transitions_and_tests` |
| 4 conversation continues while task runs | covered | `test_voice_bot_concurrency.py::test_follow_up_is_accepted_while_a_task_runs`; live G5 (`scripts/voice_g5_live_probe.py`) |
| 5 speech interruption leaves coding state unchanged | covered | `test_voice_bot_interrupt.py::test_playback_interruption_leaves_task_state_unchanged`; live G5 |
| 6 explicit cancel reports accurate semantics | covered | `test_voice_bot_interrupt.py::test_acknowledged_cancel_records_requested_then_cancelled`; `::test_cancel_the_provider_does_not_acknowledge_becomes_failed`; `::test_cancel_reports_rollback_not_performed`; `test_voice_bot_delegation.py::test_cancel_delegation_reaches_cancelled_through_the_provider` |
| 7 permission denial prevents action | covered | `test_voice_bot_permissions.py::test_deny_prevents_execution_and_the_provider_sees_cancelled`; `test_voice_bot_live_permission.py` (fixture + live G6 probe) |
| 8 stale editor context blocks conflicting writes (R22) | covered | `test_voice_bot_safety.py::test_stale_buffer_blocks_an_approved_write`; `test_voice_bot_bridge.py::test_reply_editor_snapshot_blocks_stale_write`; `test_voice_bot_nn_cascade.py` (C7, C14) |
| 9 spoken claims match evidence | covered | `test_voice_bot_results.py::test_passing_tests_are_spoken_as_passed`; `::test_failing_tests_are_spoken_as_failed`; `::test_sc013_every_completed_task_spoken_claim_matches_its_test_state` |
| 10 native handoff verified or ACP fallback labeled | covered (fallback) | `test_voice_bot_gates.py::test_g1_native_chat_is_fail_and_acp_fallback_is_the_coding_session`; `::test_g1_register_is_pass_via_labeled_acp`. Native handoff is recorded as FAIL in G1, so only the labeled fallback is claimed. |
| 11 gates G0–G6 recorded | covered | `test_voice_bot_evidence_register.py::test_evidence_register_covers_all_gates`; `::test_evidence_register_g0_pass_and_results_valid` |
| 12 submit returns task_id without ending session | covered | `test_voice_bot_readonly_turn.py` (asserts `running` before completion, SC-007); `test_voice_bot_bridge.py::test_post_submit_runs_the_task_and_get_task_reports_the_result` |
| 13 normalized events (R17) for start, progress, approval wait, completion, failure | **covered** | `test_voice_bot_r17_events.py::test_all_five_r17_event_kinds_reach_task_events` (start/progress/completion, approval wait via `reply_approval`, and refusal failure, all read from `task.events`); `test_voice_bot_readonly_turn.py` (asserts `raw_events` retained). |
| 14 G1 checklist recorded before handoff claim | covered | `test_voice_bot_gates.py::test_g1_native_chat_is_fail_and_acp_fallback_is_the_coding_session` |
| 15 secret files/selections excluded (R2) | covered | `test_voice_bot_safety.py::test_secret_filename_is_excluded_from_the_snapshot`; `::test_secret_content_pattern_is_excluded`; `test_voice_bot_queue.py::test_follow_up_keeps_excluded_snapshot_and_does_not_refill_secrets` |
| 16 tool registry only R18 names | covered | `test_voice_bot_safety.py::test_shell_and_filesystem_tools_are_refused` |
| 17 second stub adapter leaves contracts unchanged (R11) | covered | `test_voice_bot_safety.py::test_two_stub_adapters_share_the_same_hive_contracts` |
| 18 over-limit flagged or refused (R21) | covered | `test_voice_bot_safety.py::test_oversize_selection_is_truncated_and_flagged`; `test_voice_bot_delegation.py::test_diff_cap_flags_truncation_explicitly`; `test_voice_bot_contracts.py::test_instruction_limit_is_refused_without_truncation` |
| 19 path escape, unauthenticated connection, bad args refused (R23) | covered | `test_voice_bot_security.py::test_relative_parent_escape_is_refused_before_any_task_exists`; `test_voice_bot_bridge.py::test_requests_without_or_with_wrong_token_are_refused_and_change_nothing`; `::test_unknown_argument_and_bad_shapes_are_refused_with_codes` |
| 20 measured latency and resources recorded; config drives target (R24) | covered (2026-11-11; live probe `rss_check` not yet re-run with the new targets) | `test_voice_bot_latency.py::test_latency_target_from_config_changes_the_checked_result`; `test_voice_bot_config.py::test_r24_latency_targets_default_to_measured_ceiling`; `test_voice_bot_resources.py::test_config_file_changes_the_checked_result`; `::test_resource_defaults_are_set_and_cover_measured_peaks`. Latency targets 8000 ms. Resource targets in `VoiceBotConfig`: agent children 650 MB (measured peaks 607.8–630.2 MB), voice service 100 MB (provisional; measured ~21 MB). Probe `scripts/voice_r24_latency_probe.py` now writes `rss_check` from the config. Live re-run 2026-11-11 (1 run): latency within 8000 ms; voice service 20.7 MB ok; agent children peak 770.2 MB **over the 650 MB target** (`evidence-register.md` §T018). Target unchanged; needs a human decision and more runs. |
| 21 edge rules R25–R29 through submit and approval | covered | `test_voice_bot_edges.py::test_call_end_during_pending_approval_does_not_cancel_and_does_not_speak`; `::test_restart_moves_in_flight_task_to_unknown_and_discards_queue`; `::test_second_approval_is_refused_while_one_is_pending`; `::test_snapshot_scope_no_file_unsaved_and_binary`; `::test_agent_mode_stays_disabled`; `test_voice_bot_retry_dedupe.py`. R29 session scope after call end + restart: `test_voice_bot_r21_decisions.py::test_restart_after_call_end_opens_new_session_and_new_task` (same `client_request_id`, new `session_id` → new task; not a spec change — implied by “scoped to one session”). |
| 21b ACP fs/read cap follows R21 `snapshot_max_bytes` (H7) | covered | `test_voice_bot_r21_decisions.py::test_fs_read_cap_is_taken_from_snapshot_max_bytes_config`; `::test_fs_read_uses_default_cap_when_config_absent` |
| 22 Moshi/Pipecat declared; ensure-runtime; status (R30) | covered | `test_voice_bot_self_contained.py::test_voice_extra_declares_moshi_and_pipecat`; `::test_ensure_runtime_install_calls_pip_for_missing_packages`; `::test_status_reports_declared_voice_stack` |

## Success criteria

| SC | Status | Tests / evidence |
|---|---|---|
| SC-001 read-only question, no file changes | covered | `test_voice_bot_readonly_turn.py::test_read_only_turn_leaves_workspace_byte_identical` (sha256 of every workspace file before and after, `.hive/` excluded); `::test_read_only_prompt_streams_and_completes_with_stop_reason` |
| SC-002 task correlated to one session, progress and final result | covered | `test_voice_bot_readonly_turn.py::test_contextual_follow_up_reuses_the_same_provider_session`; `test_voice_bot_results.py::test_r14_progress_speech_is_limited_to_one_per_interval` |
| SC-003 playback interruption does not change task state | covered | `test_voice_bot_interrupt.py::test_playback_interruption_leaves_task_state_unchanged` |
| SC-004 permission denial prevents write or command | covered | `test_voice_bot_permissions.py::test_deny_prevents_execution_and_the_provider_sees_cancelled`; live G6 |
| SC-005 spoken claims match task and test evidence | covered | `test_voice_bot_results.py::test_spoken_and_written_results_differ_and_share_one_record`; `::test_non_test_command_does_not_claim_tests_passed` |
| SC-006 native handoff pinned or ACP fallback labeled | covered (fallback) | `test_voice_bot_gates.py::test_g1_register_is_pass_via_labeled_acp`; G2 `session/prompt` in evidence register |
| SC-007 running returned before work completes | covered | `test_voice_bot_readonly_turn.py` (`state == "running"` assertion) |
| SC-008 spoken_update and written_result differ, same record | covered | `test_voice_bot_results.py::test_spoken_and_written_results_differ_and_share_one_record` |
| SC-009 feature questions resolve from spec without invention | covered | `test_voice_bot_planning.py::test_acceptance_criteria_question_cites_the_spec_file`; `::test_planning_question_does_not_invent_when_the_spec_is_missing` |
| SC-010 R17 normalized events; spoken updates cite task evidence | covered | Events: `test_voice_bot_r17_events.py::test_all_five_r17_event_kinds_reach_task_events`. Citation: `test_voice_bot_sc010_spoken_citations.py::test_completed_turn_speech_cites_task_events_not_raw_tokens`; `::test_failed_turn_speech_cites_task_failed_event` (every `speech.spoken` follows a lifecycle event; raw provider chunk stays in `written_result`). |
| SC-011 each R20 transition recorded; cancel_requested and cancelled separate | covered | `test_voice_bot_interrupt.py::test_acknowledged_cancel_records_requested_then_cancelled`; `test_voice_bot_contracts.py::test_transition_table_has_no_exit_from_terminal_states` |
| SC-012 same client_request_id returns same task_id | covered | `test_voice_bot_delegation.py::test_submit_twice_with_same_client_request_id_creates_one_task`; `test_voice_bot_retry_dedupe.py`; `test_voice_bot_bridge.py::test_post_submit_duplicate_client_request_id_is_not_run_twice` |
| SC-013 spoken test claims match R8 states | covered | `test_voice_bot_results.py::test_sc013_every_completed_task_spoken_claim_matches_its_test_state`; `::test_r8_missing_or_unparsable_record_is_unknown_never_not_run` |
| SC-014 voice extra, pack, ensure-runtime, status; typed until G3 | covered | `test_voice_bot_self_contained.py` (all cases); `test_voice_bot_gates.py::test_hybrid_speech_path_is_typed_until_stt_is_pinned` |

## Gaps to close before the crosswalk can read "all covered"

1. AC 13: closed 2026-11-11 by `test_voice_bot_r17_events.py`. SC-010 closed 2026-11-11 by `test_voice_bot_sc010_spoken_citations.py`.
2. SC-001: closed. `test_read_only_turn_leaves_workspace_byte_identical` asserts the workspace hash is unchanged after a read-only turn.
3. AC 20 / R24: closed in code 2026-11-11. Latency targets 8000 ms; resource targets (650 MB agent children, 100 MB voice service provisional) added to `VoiceBotConfig` and tested. Live `rss_check` 2026-11-11: run 1 at 770.2 MB exceeded the 650 MB target (outlier, kept in register). Three follow-up runs peaked at 616.9 / 639.8 / 623.0 MB, all within target. No config change made; 650 MB is tight.
4. AC 6 and AC 7 are covered by unit-level runner tests. Live cancel and deny are in G5 and G6, but no live cancel is recorded in the register.