# Impact packet — Voice_Bot 10-loop code-review cascade (2026-11-11, pass 5)

**Primary:** `extensions/hive-voice-bot/src/core.js` (`sameFsPath`, `matchOpenFsPath`), `extensions/hive-voice-bot/src/extension.js` (live write-approval document lookup)

**Tests:** `extensions/hive-voice-bot/test/review-fixes.test.js`

**Spec:** R22 (live buffer must be the bound snapshot file). On Windows, `path.normalize` equality is case-sensitive, so an open bound file was treated as missing (version 0 dummy) and every `write_or_command` approval looked stale.

**Secondary:** `src/hive_planner/voice_task.py` unchanged; `_live_file_mismatch` already casefolds. No spec text change.

**Downstream:** Host write-approval snapshots on Windows now keep the real document version/dirty when drive or folder letters differ. Closed files still fail closed (dummy version 0).
