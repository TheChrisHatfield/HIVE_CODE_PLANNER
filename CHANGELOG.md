# Changelog

All notable changes to **Hive Code Planner** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Package version lives in `pyproject.toml`; published tags and release bodies live on [GitHub Releases](https://github.com/TheChrisHatfield/HIVE_CODE_PLANNER/releases).

**Roadmap validation:** `py -3.11 -m hive_planner roadmap-status` checks that all 22 compiler-stage features have `spec.md`, Delta micro brief, and `tasks.md` (see `ROADMAP_FEATURES` in `src/hive_planner/roadmap_status.py`).

Authoritative stage tables: [`docs/delta/STAGE_ROADMAP.md`](docs/delta/STAGE_ROADMAP.md).

---

## [Unreleased]

Work on `main` after [v1.3.0](https://github.com/TheChrisHatfield/HIVE_CODE_PLANNER/releases/tag/v1.3.0) (~**480+** commits; not yet tagged). These lanes are active in-repo but not part of the v1.3.0 package tag: **Voice_Bot**, **bug-hunt**, **implementation-loop**, **agnostic-loop**, **controls-execute**, **Moshi_Tool_Lane**, and related desktop/launcher work.

### Voice_Bot and Moshi (conversation layer)

Voice_Bot is the hosted voice session: permissions, task bridge, evidence, and adapters. **Moshi** is the primary duplex speech layer inside Voice_Bot (not a separate product).

- **Runtime and bridge (T003–T028):** voice runtime bridge, runner lock, ACP task runner, contract adaptation; bridge retry returns `context_snapshot_id` on duplicate submit so `/v1/task` accepts retries (R29).
- **Runner surface (T004–T011, implementation-loop T023–T025):** read-only ACP runner, approvals queue, interrupt, and results wiring through the implementation loop.
- **Moshi live path (sessions 15c–15m, R37):** call-gate handover between panel and live call; shared q8 STT language model; faster STT shutdown; live utterances skip the Moshi listen gate when already on a live call; spoken **submit** starts task watch (T042); panel fixes for stop-during-gate, dropped-call state, and approval polling; operator notice when Moshi starts with `stt_provider` unset.
- **STT and mic:** `FasterWhisperAdapter` imported from `hive_planner.voice_stt` so live-mic recording can transcribe; WER/RTF benchmarks guard empty references and zero-length audio; `ensure-runtime` treats pip exit 0 as failure when `moshi` still cannot import.
- **Security / context:** `isInsideWorkspace` rejects in-root names starting with `..`; Voice_Bot follow-ups keep excluded snapshot context so dispatch cannot refill secrets from disk.
- **Artifacts:** specs, evidence register, Delta micro doc, cartridge packs, and a large `tests/test_voice_*` suite (bridge, lock, gates, latency, concurrency, live permission).

Validate (examples):

```text
py -3.11 -m hive_planner voice-bot status
py -3.11 -m pytest tests -q -k voice
```

### Bug hunt (prediction ranking and recovery)

- **Ranking robustness:** NaN-safe reads, integer digit strings, import-time side effects removed from 603-blend restore, 909-mix refit, GAN scoring/best-fold, weak-batch adds, and stratified fit helpers; seventh-signal guard uses word boundaries so filenames like `auto_hivectm_guard_e2e.py` are not false guarded negatives.
- **R10 — exploration and attribution:** bounded uncertainty coverage bonus; versioned attribution on queue rows; direct override with repository containment and symlink-aware source validation; Python/C# fixtures with grounded labels.
- **R11 — empty-search recovery:** bounded empty-result recovery state with confidence; recovery controller after normal empty threshold; prompt/hook wiring carries recovery metadata; malformed `continue.json` and legacy row fixtures covered in tests.
- **Hooks and transcripts:** empty hook payload when recovery is exhausted (Cursor does not start another pass); UTF-16 LE transcripts and hooks without BOM keep memory notices and hunt continuation correct on Windows.

Entry points:

```text
py -3.11 -m hive_planner bug-hunt install
py -3.11 -m hive_planner bug-hunt status
```

### Implementation loop and CodeSpec (desktop)

- **File-overlap gate (T030–T031)** and Voice_Bot task handoffs through the loop coordinator.
- **Start guard:** implementation-loop **start** fails when `tasks.md` cannot be read instead of reporting ready.
- **Home / Controls UI:** CodeSpec install no longer overwrites the first Controls block (Bug hunt vs Agnostic loop); Check pack listed in CodeSpec help when the Home guide lacks an Implementation loop section; multiple Controls blocks keep separate result lines.

```text
py -3.11 -m hive_planner implementation-loop status
```

### Agnostic loop

- Hit/miss recording rejects unrecognized hits; JSON `true` in state does not skip the first hook; UTF-16 LE state files remain readable.
- **Portable rebuild:** `scripts` one-click Windows `.bat` to rebuild the agnostic portable layout on any PC.

### Cartridge compiler, Delta, and MCP

- **Promote/emit:** shared `promote_cli_exit_code` so agent-handoff-off matches emit (exit 0); missing `memory.md` reported as skipped **(missing)** not **(not draft)**; non-object manifest replaced instead of crashing emit; junction folders skipped on import/adapt; draft promotion skips unreadable drafts; promote no longer writes fenced example bullets into memory candidates.
- **Scoring/index:** null chunk keywords coerced; frozen GAN scoring does not run on import.
- **MCP:** server stays up on non–UTF-8 bodies; project tools reject missing folders; UTF-8 BOM on `.cursor/mcp.json` rewrite failures reported instead of raising out of Settings; no-BOM UTF-16 configs described accurately.

### Integrations and launcher

- **GitHub:** per-source download staging; Bearer/token prefix stripped from pasted tokens; auth header not doubled.
- **Goose:** `{SCRIPT}` and argument placeholders resolved when registering YAML recipes.
- **Catalog:** fractional YAML priorities rejected; free-text search includes author; bundle search stays on the same catalog source as resolve; null Azure DevOps token treated as missing.
- **Graph/bundles:** single node with `edges` key parsed as node, not empty bundle.
- **Portable GUI:** startup dialog when portable bootstrap fails (windowed exe no longer silently drops stderr).
- **Plugins:** refuse deleting marketplace plugin with invalid `plugin.json`; UTF-16 LE manifests without BOM; C# field token scan so used PascalCase assignments are not `dead_setting`.
- **Bluetooth routing health:** count live speakers by device identity, not commas in Windows display names.
- **Probes:** G5 live probe does not start on import or exit early at 15s; R24 RSS judged against unrounded bytes.

### Windows encoding hardening (cross-cutting)

Many fixes target **UTF-16 LE** files saved without a BOM (common on Windows): hooks.json, `continue.json`, bug-hunt overlays, cartridge manifests and notes, Delta docs, CL stop-hook turn counts, MCP config, and agent transcripts. Read paths normalize or fail clearly; verify/deploy/bug-hunt install merge hooks instead of claiming missing `workspaceOpen`.

### Changed (summary)

- **bug-hunt** listed first in `AGENTS.md` active lanes so wiring audit and CodeSpec default to that feature when multiple lanes are open.
- **`hive-voice-bot` extension** tracked in-repo as baseline before bug-hunt fixes.

### Validation (Unreleased)

```text
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check
py -3.11 -m pytest tests -q
```

---

## [1.3.0] - 2026-10-21

First **GitHub release** tag. Bundles Stages **1–9** (versions 1.0.0–1.2.0 were developed in-repo before this publish).

### Added

- **Stage 9 — unified upstream deploy (`unified-handoff-v2`, `roadmap-complete-v4`):** vendored, pinned forks of [Spec Kit](https://github.com/github/spec-kit) and [Cursor Continual Learning](https://github.com/cursor/plugins/tree/main/continual-learning) with Hive symbiotic patches. `hive_planner init` / bootstrap writes **both** into a target project; IDE CL plugin and Hive CLI share one contract.
- **CLI:** `unified-verify`, upstream pin check/apply, vendor manifest verification against `.hive/upstream-pins.json`.
- **Docs:** operator guide [`docs/unified-handoff-upstream-forks.md`](docs/unified-handoff-upstream-forks.md); v1.3.0 called out in README, ARCHITECTURE, and AGENTS.

### Validation

- `roadmap-status` — **22/22** features (adds `unified-handoff-v2`, `roadmap-complete-v4`).
- Stage 9 closure: `ci-check`, `tests/test_unified_handoff.py`.

[Release notes on GitHub](https://github.com/TheChrisHatfield/HIVE_CODE_PLANNER/releases/tag/v1.3.0)

---

## [1.2.0] - 2026-06-26

### Added

- **Stage 8 — starter kit and hardening (`starter-kit-v2`, `roadmap-complete-v3`):**
  - `hive_planner init --profile full` scaffolds `pyproject.toml`, `src/` + `tests/`, `.gitignore`, and a GitHub Actions CI stub; optional `--git-init`.
  - Path and **active-feature** validation on bootstrap and launcher flows (invalid feature ids and unsafe init targets rejected).
  - Security/path validation hardening aligned with starter-kit v2 profile.

### Validation

- `roadmap-status` — **20/20** features.
- Stage 8 closure: **166** pytest, `ci-check` 5/5.

---

## [1.1.0] - 2026-06-26

### Added

- **Stage 7 — Continual Learning + spec integration (`cl-spec-integration-v1`, `agents-memory-ci-v2`, `cartridge-pack-v2`, `change-impact-v3`, `project-bootstrap-v1`, `roadmap-complete-v2`):**
  - **Memory v2:** `agents-lint`, proposal-only `agents-propose`, guarded `agents-apply`; behavioral vs operational bullet routing (spec vs `AGENTS.md`).
  - **Impact v3:** richer change-impact maps and sync without clobbering curated rows.
  - **Cartridge pack v2** and **project bootstrap:** `hive_planner init` targets a directory **outside** the Hive source tree; bootstrapped projects start with no active feature until set.
  - **Rule seeds** and Cursor rule/hook integration documented in Delta and specs.

### Validation

- `roadmap-status` — **18/18** features.
- Stage 7 closure: `ci-check` 5/5.

---

## [1.0.0] - Stages 1–6 (compiler roadmap)

Core **cartridge compiler** pipeline, change-impact tooling, embedding retrieval, Delta emit, git handoff CI, and cartridge pack emit. Marked complete in [`docs/delta/STAGE_ROADMAP.md`](docs/delta/STAGE_ROADMAP.md).

### Added (by stage)

| Stage | Feature id | What shipped (high level) |
|-------|------------|---------------------------|
| 1 | `cartridge-compiler-v1` | Cartridge compile pipeline v1 |
| 2 | `cartridge-compiler-v2` | Compiler v2 extensions |
| 3 | `change-impact-v1` | Change-impact maps and packets |
| 4A | `cartridge-compiler-v3` | Compiler v3 |
| 4B | `cartridge-translator-v1` | Format translation layer |
| 4C | `agents-memory-ci-v1` | AGENTS.md lint/propose; guarded apply path |
| 4D | `embedding-retrieval-v1` | Embedding search over source library |
| 5A | `cartridge-delta-emit-v1` | Sync Delta holistic/macro/micro into cartridge on emit (`--force-delta` for drafts) |
| 5B | `change-impact-v2` | `impact-sync-maps` merges discovered src/tests into maps |
| 5C | `git-handoff-ci-v1` | `ci-check` — pytest, agents-lint, spec artifacts, map drift, spec-drift |
| 6A | `cartridge-pack-v1` | Full pack emit: research-summary, memory, specseed, source-map |
| 6B | `roadmap-complete-v1` | Stage 1–6 closure artifacts and validation |

### Also in the 1.x line (operator-facing)

- Desktop **Hive Planner** launcher and portable build (`dist/HivePlannerPortable/`).
- **Bug hunt**, **implementation loop**, and **agnostic loop** install via CLI (`py -3.11 -m hive_planner … install`).
- **Hive Planner MCP** (`mcp-serve`) for Cursor Agent MCP wiring.
- **Planning Rosetta Stone** and Delta three-level context model for agent startup.

### Validation

- Post–v1.0.0 bug audit (2026-06-21): stage-by-stage; **103/103** pytest, `ci-check` 5/5.
- `roadmap-status` for Stages 1–6 features through `roadmap-complete-v1`.

---

## Version ↔ stage map (quick reference)

| Version | Stages | `roadmap-status` count |
|---------|--------|-------------------------|
| 1.0.0 | 1–6 | Through `roadmap-complete-v1` |
| 1.1.0 | 7 | 18/18 |
| 1.2.0 | 8 | 20/20 |
| 1.3.0 | 9 | 22/22 |
| Unreleased | — | 22/22 plus active feature lanes (Voice_Bot, etc.) |

---

## Contributing to this file

- **Released versions:** copy the GitHub Release body, then expand with spec/Delta acceptance criteria and validation commands.
- **Unreleased:** group commits by feature lane; prefer user-visible outcomes and CLI entry points over commit hashes.
- Do not duplicate vendored upstream changelogs under `vendor/` unless Hive patches materially change behavior.