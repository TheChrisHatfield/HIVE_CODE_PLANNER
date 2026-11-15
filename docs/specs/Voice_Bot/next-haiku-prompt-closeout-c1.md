=== PASTE INTO HAIKU ===

Voice_Bot **closeout C1 — T042 criterion 4 (STT pin gate, no live mic claim)**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**Verdict:** read-only=READY. speech/S1=**NOT** (gap A open). full-agent=**NOT READY for production use** (operator review; per-host latch). Deploy pack=READY.

**Done (do not re-prove):** U11b write broker green (`test_voice_bot_write_gate.py` 3 pass); unguarded 9 pass; T033-S1 criteria 1–3 in `evidence-register.md`; `POST /v1/submit/spoken`, `FasterWhisperAdapter`, `stt_provider` config read site; `pytest tests -k "voice or acp"` **389 passed**, 2 skipped (2026-11-12).

**This chat — one micro-task only: C1**  
Close **spec § Speech I/O rollout / T042 criterion 4** in **code + register + gates**, without turning on spoken G3 on the host:

1. Read `evidence-register.md` § T033-S1 and `spec.md` § Speech I/O rollout (STT pin criteria 1–4).
2. Add or complete the **T033 pin row** for criterion 4: record that `stt_provider` in config may only be set to the pinned provider id after tests pass; date the row.
3. Update `tests/test_voice_bot_gates.py`: replace any stale `STT_PROVIDER is None` constant assertion with config-driven `hybrid_speech_path(load_voice_bot_config(...))` when `stt_provider` is the pinned id (use temp config or monkeypatch; **do not** commit `.hive/voice-bot/config.json` with `stt_provider` set on the dev host unless operator asks).
4. Ensure `hybrid_speech_path` does not claim Whisper when `stt_provider` is null (default S0).
5. Run: `pytest tests/test_voice_bot_gates.py tests/test_voice_stt.py tests/test_voice_stt_runtime.py -q`, then `pytest tests -k "voice or acp" -q`.
6. Update `tasks.md` T042 one line (criterion 4 partial→done for **gate** only; live mic still open).
7. Update `deployment-gaps.md` gap A: criterion 4 met; live rows still open (C3/C4).

**Do not:** claim G3 spoken pass; set `audio_enabled: true`; run live microphone; flip `edits_enabled`; full `spec.md` load.

**First action:** Grep `hybrid_speech_path`, `stt_provider`, `T033` in `src/hive_planner/voice_bot.py` and `tests/test_voice_bot_gates.py`; read register § T033.

Do First action only; emit the Continue block at end of turn. If budget low, stop after tests green.

Every turn MUST end with:

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: read-only=READY speech/S1=<NOT|partial> full-agent=NOT READY for production use
G0–G6: G3 wording unchanged until live rows
Done this chat: <1–3 bullets>
Open next: C2 — U7 STT in pack INSTALL.md (_voice_pack_install_md)
Do not redo: U11b; 389 voice+acp unless regress
Files changed: <paths>
Blocked: live mic
First action: read voice_bot.py pack generator for ensure-runtime wheel list
```

=== END PASTE ===
