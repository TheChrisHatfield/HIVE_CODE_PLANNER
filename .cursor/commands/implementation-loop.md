---
description: Run the implementation loop for a finished Hive spec
---

# Implementation loop (1-pack)

Roles: coordinator

Read `.hive/implementation-loop/roles/coordinator.md` and follow it.

Call the Python coordinator gates. Do not `git commit`, edit `state.json` round trips, or write `handoff.md` by hand.

```text
py -3.11 -m hive_planner implementation-loop start --feature <id>
py -3.11 -m hive_planner implementation-loop handoff --role coordinator
py -3.11 -m hive_planner implementation-loop check
py -3.11 -m hive_planner implementation-loop accept --role <role>
py -3.11 -m hive_planner implementation-loop commit
```

If this is a 1-pack, the coordinator performs implement, then Python check, then commit. Review and sign-off are not loop gates.

If a bug hunt is already in progress, finish or pause it before starting this loop.

On checker fail or stall the stop hook pings this chat. Continue the current task. Do not wait for the human to say continue.

Do not merge, push to trunk, force-push, or deploy.
