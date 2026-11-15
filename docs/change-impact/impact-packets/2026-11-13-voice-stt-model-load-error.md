# Impact packet: Voice_Bot STT model-load error (2026-11-13)

**Feature:** Voice_Bot
**Hooks:** `change.impact`, `change.validation`, `integration.wiring_audit`

## Change

| File | Change |
|---|---|
| `src/hive_planner/voice_stt.py` | `FasterWhisperAdapter.__init__` wraps the `WhisperModel(...)` call; any load failure raises `SttError("stt_unavailable")` |
| `tests/test_voice_stt.py` | `test_model_load_failure_is_stt_unavailable_not_raw` (fake `faster_whisper` module injected via `sys.modules`, so it runs without the package) |

## Defect

The constructor only converted `ImportError` into `SttError`. A present but unloadable `model.bin` (partial download, corrupt CTranslate2 file, `OSError`) escaped as a raw exception. The caller in `voice_task.py` (`submit_spoken` path, around line 1809) catches only `SttError`, so a raw exception would skip the `DelegationError` mapping and its spoken notice at that clause. I did not trace how the bridge handles an uncaught exception from that point.

## Wiring trace

`POST /v1/submit/spoken` → `submit_spoken` → `resolve_pinned_model_dir()` → `FasterWhisperAdapter(model_dir)` → (now) `SttError` → `DelegationError("stt_unavailable", spoken=...)`.

## Downstream impact

- Interface: none. The constructor still raises `SttError`; only the error code for load failures changes from raw to `stt_unavailable`.
- Callers: `voice_task.py` only. No config flag changed.
- Spec and R33 latch: unchanged.

## Validation

- `py -3.11 -m pytest tests/test_voice_stt.py tests/test_voice_stt_runtime.py -q`: 21 passed, 2 skipped
- `py -3.11 -m pytest tests -k "voice or acp" -q`: 547 passed, 3 skipped
- Not run: a confirmed failing run against the pre-fix code. The reasoning is that the raw `OSError` would propagate past `pytest.raises(SttError)`.
- Not run: a live model load on the host. The pinned model is present locally, but this test does not exercise it.
