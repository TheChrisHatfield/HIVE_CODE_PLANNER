# Plan: agnostic-loop

**Hook:** `workflow.tools`, `spec.flow`, `integration.wiring_audit`  
**Spec:** [spec.md](./spec.md)  
**Status:** implemented

<!-- ROSETTA-NAV -->

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before editing this plan.

## Layer mapping

| Layer | Mapping |
|-------|---------|
| Holistic | Pause-cycle chooser with replaceable reward tables |
| Macro | Opt-in full kit install + CLI; compiler/cartridge unchanged |
| Micro | Engine in `agnostic_loop.py`; install copies scripts, skill, catalog.json |

## Approach

Port `hive-loop-kit` into Hive Planner so **install copies the kit**, not only a Cursor command. Engine lives in `src/hive_planner/agnostic_loop.py` and is written to `scripts/agnostic_loop.py` on install. Keep Thompson, Monte Carlo rollouts, and UCT search. Reward tables are `.hive/agnostic-loop/catalog.json` with **generic** default names (`inspect`, `fill`, …). `scripts/trajectory_remap.py` remains an alias. Lay-footnote skill and `trajectory-loop.md` install with the kit.

Do not ship SeamFlow / UV / training / reconstruction tables. Do not bake Hive spec-gap rewards into the default catalog. Tick rules stay domain-neutral.

Mirror bug hunt for chat install and Home Enable. Do not auto-install on `init` (same opt-in idea as implementation-loop).

## File targets

| File | Change |
|------|--------|
| `src/hive_planner/agnostic_loop.py` | Engine, catalog, install, trigger |
| `src/hive_planner/cli.py` | `agnostic-loop` subcommands |
| `src/hive_planner/bootstrap.py` | Optional `--agnostic-loop` |
| `src/hive_planner/launcher/service.py` | Home install wrapper |
| `src/hive_planner/launcher/app.py` | Enable agnostic loop |
| `tests/test_agnostic_loop.py` | Catalog, cycle, choose, install, CLI |

## Validation

```powershell
py -3.11 -m pytest tests/test_agnostic_loop.py -v
py -3.11 -m hive_planner spec-drift-check --feature agnostic-loop
```
