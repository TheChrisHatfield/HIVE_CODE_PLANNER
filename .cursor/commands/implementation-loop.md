---
description: Run the implementation loop for a finished Hive spec
---

# Implementation loop (4-pack)

Roles: coordinator, coder, checker, reviewer

Read `.hive/implementation-loop/roles/coordinator.md` and follow it.

Call the Python coordinator gates. Do not `git commit`, edit `state.json` round trips, or write `handoff.md` by hand.

```text
py -3.11 -m hive_planner implementation-loop start --feature <id>
py -3.11 -m hive_planner implementation-loop handoff --role coder
py -3.11 -m hive_planner implementation-loop accept --role <role>
py -3.11 -m hive_planner implementation-loop commit
```

If this is a 4-pack, the coordinator delegates to coder, checker, and reviewer as separate subagent passes, then calls commit.

Do not merge, push to trunk, force-push, or deploy.
