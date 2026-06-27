# Plan: starter-kit-v2

**Hook:** `workflow.project_bootstrap`  
**Spec:** [spec.md](./spec.md)

## Approach

1. Extend `bootstrap.py` with `profile`, `git_init`, and template generators.
2. Add `--profile` and `--git-init` to CLI `init` command.
3. Keep v1 `minimal` profile as default for backward compatibility.
4. Document CI `HIVE_PLANNER_PATH` repository variable for bootstrapped repos.
