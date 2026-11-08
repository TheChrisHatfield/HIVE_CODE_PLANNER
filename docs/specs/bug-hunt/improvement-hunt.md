# Improvement-driven bug hunt

**Hook:** `change.bugfix_mode`  
**Status:** active for the prediction bug-hunt copies. Not a change to the installed hunt prompt.

## What

Each repo is improved from a gap already found by reading that repo. The installed prompt and both Hive rank logs are not edited. Scanner-hit rows are not targets: a file is not chosen because its rank row is a scanner hit. The six detector signals are not targets.

## Genuine improvement

An improvement qualifies when all of these hold:

- A caller already hits the behavior. The change makes that behavior correct.
- The change is not written so that a bug will appear.
- The pre-existing gap is not reported again as the finding.
- Only a defect in the new lines can count.

## Exclusion list

The sixteen classes are:

- lock-order concurrency
- handler touching a missing object
- partial write before error
- skipped collective
- reward jumping at zero
- stop trusting a tool exit code
- wheel delta truncated
- public divisor of zero
- rank cached for the life of the process
- merge reporting success after the write was lost
- spring step divided by a zero timestep
- substring stealing a route
- backbone name still building a ResNet
- warmup starting at learning rate zero
- masked loss divided by a zero weight sum
- a full queue drops the new item after the old one was taken

The same failure mode is the same class at every site. A zero feather, a zero vertex degree, and a zero weight sum are a public divisor of zero. When the new code's bug is one of the sixteen, keep the improvement and do not count the bug. A bug counts only when its class is absent from this list.

## Per-repo improvements

| Repo | Gap already in the code | Improvement |
|---|---|---|
| spec-kit | A template body can keep the literal `{SCRIPT}` when the requested script type was not in the frontmatter, and that text is what gets installed | Refuse the template before any file is written |
| BLIP | `pre_question` deletes punctuation that `pre_caption` turns into a space, so two words become one token | Delete punctuation the same way the caption cleaner does: replace it with a space |
| continuous-thought-machines | `get_solution` steps to `(-1, -1)` when no neighbor is open, and that index is the last cell | Stop and return the path gathered so far |
| continuous-thought-machines | `MaskVelocityWrapper` says it resets on done and `step` never does | Reset when the episode ends, then return the fresh observation |
| moshi | The first audio frame is supposed to be ignored, and `lm_gen.step` still runs on it | Skip that frame in the language model as well as the codec |
| unity-mcp | An unfocused editor overwrites `observed_at_unix_ms` on a snapshot that was not rebuilt | Leave the timestamp at the time the snapshot was actually built |

These repos were read and have no gap that qualifies, so they get no invented improvement: huggingface_guess, the assets repo, COLEMAN, STABLE_FLOW, libigl, Michelangelo, robust-weight-transfer, LEITNER, ANDROID_MOVIE_APP, UNITY_CHAIN_TOON_SHADER, unity-agent-plugin, UnityChan, Hive Code Dev 1, moshi-finetune, GEN_PBR, zed, and BLUETTOOTH_SURROUND.

The Forge hires crop and the unity-mcp port check are off this table. Those files' rank rows are scanner hits, and a scanner-hit row is not a reason to choose a file.

## First implementation

spec-kit `IntegrationBase.process_template`. After the scripts block is removed, a remaining `{SCRIPT}` raises `ValueError` and names the script type. Callers write the file only after this returns, so the refusal does not leave a half-written command. The new check has no bug outside the sixteen.

## Second implementation

BLIP `pre_question`. Punctuation in the same class `pre_caption` already uses is replaced with a space, repeated whitespace is collapsed, and the ends are stripped. `What?Next` becomes two tokens. VQA calls this function in `data/vqa_dataset.py`.
