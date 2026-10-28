# Impact: Hive Planner MCP (agent control)

**Date:** 2026-10-27  
**Hook:** `workflow.tools`, `change.validation`  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` R6

## Primary

- `src/hive_planner/mcp_server.py` — stdio JSON-RPC MCP (`mcp-serve`)
- `src/hive_planner/cli.py` — `mcp-serve` dispatches before repo-root resolve (no stdout except protocol)
- `src/hive_planner/launcher/mcp_servers.py` — `hive-planner` name, launch argv, enable/disable
- `src/hive_planner/launcher/service.py` — `peek_hive_planner_mcp` / `run_set_hive_planner_mcp`
- `src/hive_planner/launcher/app.py` — Settings Agent MCP Enable / Disable / Copy

## Secondary

- Active project `.cursor/mcp.json` (written on Enable; other servers kept)
- `scripts/README.md`, `user_guide.py`, `AGENTS.md`, desktop spec/delta

## Tests

- `tests/test_mcp_server.py`

## Out of scope

Merge/deploy/push tools; editing arbitrary third-party MCP servers in Settings.
