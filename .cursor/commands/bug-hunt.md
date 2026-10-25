---
description: Continuous bug hunt (bug hunt, bug hun, bung hunt, do a bug hunt) — find, fix, self-review, commit locally, repeat.
---

Execute a continuous 50-iteration bug-hunting and wiring verification loop where you deep-dive into code logic and functional issues, automatically apply a fix, perform your own internal agent review of the patch, automatically commit the changes when that self-review passes, and repeat the process autonomously until the code is at a satisfactory quality level to stop — or until 50 reviewed fixes are committed.

You do not do one bug at a time and then wait. Pause only for that internal review, then continue the next iteration without waiting for the user. That is the intent of this script.

## Each iteration

1. Find one real functional or wiring bug: wrong result, a throw on a path the user can hit, a skipped link (UI or event never reaches the handler, or success is reported when a required step was skipped), or a dead setting. Skip style nits, drive-by refactors, and speculative guards that do not match a failure.
2. Apply the smallest fix that closes that failure. Follow this repo's theme, connectivity, and validation rules when the change touches them.
3. Self-review the patch before committing. The review passes only when all of these hold:
   - The change matches the failure you named.
   - A test or contract covers the fix when this repo has a harness for that layer.
   - Wiring audit: the chain from the user-visible action to the handler and the persisted or rendered result is actually called.
   - Only files for this fix are staged.
4. Commit locally with a message that says why. Do not push, open a pull request, or upload to a remote.
5. Start the next iteration immediately. Do not ask the user whether to continue.

## Stop

Stop after 50 committed fixes, or after two consecutive areas with no real bug. That empty-area stop is the satisfactory quality level — report the commits, what each one fixed, and any area you searched that had no bug. Do not invent work to fill the budget. Do not push.
