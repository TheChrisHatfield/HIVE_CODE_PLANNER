=== PASTE INTO HAIKU ===

Voice_Bot **closeout C3 — extension → bridge spoken submit**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`. Extension: `node --test` in `extensions/hive-voice-bot`.

**Prerequisite:** C1 gate; bridge `POST /v1/submit/spoken` exists (`voice_bridge.py`).

**This chat — one micro-task: C3**  
Wire the **editor adapter** to call spoken submit (file path or bytes schema already on bridge):

1. Read `extensions/hive-voice-bot/src/bridge-client.js` and `voice_bridge.py` spoken route schema.
2. Add client method + optional command `hive.voiceBot.submitSpoken` (WAV path relative to workspace or documented bytes flow).
3. Test in `test/bridge-client.test.js` (mock fetch); follow existing submit tests.
4. `npm test` in extension folder only (four test files).
5. Note in `tasks.md` validation log: live mic capture still operator (Cursor/OS), not implemented in extension unless explicit scope.

**Do not:** claim S1 spoken deploy; enable `audio_enabled` globally; live record mic in test.

**First action:** Grep `submit/spoken` in bridge Python and extension client.

Open next: **C4** live evidence rows (operator) or **F3** if prioritizing agent lane.

=== END PASTE ===
