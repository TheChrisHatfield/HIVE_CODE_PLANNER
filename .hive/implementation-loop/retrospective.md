# Implementation loop retrospective

Run this when the coordinator counts five or more completed features since the last retrospective line.

## Steps

1. Read `.hive/implementation-loop/retrospective.log`. Count only lines that match `YYYY-MM-DD | completed=N | ...`.
2. Review task notes, result files, and commits since the last line.
3. Keep lessons that recur. Drop notes that apply to one task only.
4. Write proposals to `docs/proposals/implementation-loop-candidates.md` with `# operational` and `# behavioral` sections.
5. Do not edit `AGENTS.md` directly. The human approves each item.
   - Operational items go through `agents-propose` / `agents-apply`.
   - Behavioral items are applied by editing the owning `spec.md`.
   - Role notes are edited into `.hive/implementation-loop/roles/` after approval.
