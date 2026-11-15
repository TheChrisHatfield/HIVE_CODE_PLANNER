# Voice_Bot operator production checklist (full `agent` lane)

**Scope:** one host per checklist. Full `agent` edit mode stays **NOT READY for production use** fleet-wide. Every other machine repeats this checklist on its own. Read-only typed preview is unaffected.

**Refs:** [spec.md](./spec.md) § Deployment readiness · [deployment-gaps.md](./deployment-gaps.md) § Verdict by lane · [evidence-register.md](./evidence-register.md) (G6, R33, R35)

## Required before enabling edits

- [ ] **G6 pass** on this host: `py -3.11 -m hive_planner voice-bot live-permission --record` writes `pass` in `evidence-register.md`.
- [ ] **`agent` CLI logged in** on this host. Pin the version in the host notes below (`agent --version`).
- [ ] **Write gate green** on this host: `py -3.11 -m pytest tests/test_voice_bot_write_gate.py tests/test_voice_bot_unguarded_write.py -q` (expect 12 passed).
- [ ] **U10 residual read and accepted** (`deployment-gaps.md` U10 line). Not caught: interpreter writes such as `python -c "..."` and `node -e "..."`, plus aliases, `git checkout -- <file>`, and `npm install`. Operator initials below mean this was read.

## Optional

- [ ] `py -3.11 -m hive_planner voice-bot live-write --feature Voice_Bot --timeout 180` records R35 `pass` with a new dated row. Archive the nonce hash only, never the raw nonce.

## Latch (only after every box above)

- [ ] Set `.hive/voice-bot/config.json` to `"edits_enabled": true`.
- [ ] **To disable:** set `"edits_enabled": false`, or remove the key. Default is off.
- [ ] Never set this from a bootstrap, pack, or install script.

## Runtime review

- [ ] Review `r24.over_budget` (`kind=rss`) in task logs. The agent-children target is **650 MB**; one live run hit 770 MB. A single row is a review item, not a reason to change the target. Repeated rows on this host are a reason to escalate.

## Host notes

- agent CLI version: ______________________
- Python: `py -3.11` ______________________

## Sign-off

- Date: ______________________
- Hostname: ______________________
- Operator initials: ______ (blank until the human fills it)
