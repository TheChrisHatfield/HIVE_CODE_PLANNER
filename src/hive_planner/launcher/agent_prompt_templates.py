from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentPromptTemplate:
    """Copy-paste prompt for effective Cursor / agent sessions in a Hive project."""

    id: str
    title: str
    description: str
    prompt: str


def external_rosetta_session_prompt() -> str:
    from hive_planner.rosetta_eject import build_session_start_prompt

    return (
        build_session_start_prompt(project_name="<your project>").rstrip()
        + "\n\nAfter the session, save the produced Planning Rosetta Stone to docs/planning-rosetta-stone.md in the Hive repo."
    )


def default_agent_prompt_templates() -> tuple[AgentPromptTemplate, ...]:
    """Curated starter prompts aligned with START_HERE, Rosetta, Spec Kit, and sources."""
    return (
        AgentPromptTemplate(
            id="session.start",
            title="Start a coding session",
            description="Orient the agent with Rosetta, active spec/tasks, and truth layers before edits.",
            prompt="""Before making any code changes, load Hive planning context in this order:

1. @START_HERE.md
2. @docs/planning-rosetta-stone.md — search for Planning Rosetta Stone / hook planning.rosetta
3. @AGENTS.md
4. Active feature: @docs/specs/<feature>/spec.md, plan.md, tasks.md (use the project's active feature)
5. If present: active @docs/delta/20_micro/<feature>.md and change-impact packet in docs/change-impact/

Then:
- Identify the single active task you will implement
- Map it to one or more HOOK_ID values from the Rosetta Stone
- Confirm primary vs secondary vs tertiary context (spec/tasks = primary; AGENTS.md + rules = secondary; source-context / cartridges = tertiary only)
- Do not edit code until the active task and hooks are explicit

What is the active feature and task in this repo right now?""",
        ),
        AgentPromptTemplate(
            id="task.implement",
            title="Implement one spec task",
            description="Execute a bounded task from tasks.md with hook mapping and validation.",
            prompt="""Implement exactly one task from the active feature's tasks.md.

Workflow:
1. Read @docs/planning-rosetta-stone.md and map this task to HOOK_ID(s)
2. Read @docs/specs/<feature>/spec.md, plan.md, tasks.md — treat these as execution truth
3. Follow @.cursor/rules/task-execution.mdc and @.cursor/rules/validation.mdc
4. Respect invariants in @AGENTS.md and Delta docs

Task to implement: <paste task bullet from tasks.md>

Constraints:
- Minimal diff — only what this task requires
- Update spec/plan/tasks only when the task says to, not for drive-by refactors
- Run the validation command listed in the task (or pytest / project default) before finishing

When done, summarize: files changed, hooks used, checks run, and any follow-up tasks.""",
        ),
        AgentPromptTemplate(
            id="spec.clarify",
            title="Spec Kit — clarify before planning",
            description="Use when requirements are fuzzy; keeps Spec Kit artifacts as primary truth.",
            prompt="""We are in Spec Kit clarify phase for feature: <feature-name>

Load:
- @docs/planning-rosetta-stone.md (hook workflow.tools)
- @docs/specs/<feature>/spec.md
- @AGENTS.md and relevant Delta docs

Run /speckit.clarify (or the project's Spec Kit clarify command) to resolve ambiguities before planning.

Rules:
- Do not implement code yet
- Capture clarifications in spec.md under ## Clarifications
- Flag anything that belongs in AGENTS.md vs spec.md vs transient chat
- Reference HOOK_ID(s) for each open question

List the top ambiguities you find and the clarify questions you would ask.""",
        ),
        AgentPromptTemplate(
            id="change.impact",
            title="Review change impact before editing",
            description="Map a proposed change to modules, tests, and hooks before touching code.",
            prompt="""I plan to change: <describe change>

Before editing, run a change-impact review:

1. Load @docs/planning-rosetta-stone.md — hook change.impact
2. Load active spec/plan/tasks for the affected feature
3. Check docs/change-impact/ maps and impact packets if present
4. Identify: primary files, downstream callers, tests to update, and wiring-audit implications

Output:
- HOOK_ID(s) affected
- Files likely to change (primary / secondary)
- Tests or ci-check steps to run after
- Risks or unknowns

Do not write code until this review is written out.""",
        ),
        AgentPromptTemplate(
            id="sources.ground",
            title="Ground with Load Sources / cartridges",
            description="Pull tertiary context from uploaded documents without overriding spec truth.",
            prompt="""I need extra grounding from project sources (tertiary context only).

Load:
- @docs/planning-rosetta-stone.md — hooks context.cartridge and context.document_sourcing
- @source-context.md if present
- context-library manifest and indexed sources under context-library/ if present
- Any active cartridge under docs/cartridges/ or .hive/cartridges/ for this feature

Question / topic: <what you need grounded>

Rules:
- Primary truth remains active spec.md, plan.md, tasks.md and Delta micro brief
- Use source excerpts for reference, quotes, or missing detail — not to override the active task
- Cite which source file or cartridge section you used

Summarize relevant excerpts and how they inform (but do not replace) the active task.""",
        ),
        AgentPromptTemplate(
            id="sources.upload_followup",
            title="After Load Sources upload",
            description="Use right after Home → Load Sources to wire new files into agent context.",
            prompt="""I just uploaded source documents via Hive Planner Load Sources.

Please:
1. Read @source-context.md and context-library/manifest.json (if present)
2. Confirm which files were ingested and whether OCR was used for any PDFs
3. Explain how these sources relate to the active feature (tertiary context only)
4. Suggest where distilled facts should go: spec.md vs AGENTS.md vs stay in source-context

Do not treat uploaded notes as execution truth over the active spec/tasks.

Uploaded paths or topics: <list folders/files or describe intent>""",
        ),
        AgentPromptTemplate(
            id="handoff.health",
            title="Pre-handoff health check",
            description="Verify project readiness before giving work to an agent.",
            prompt="""Prepare this project for agent handoff.

Checklist (Hive Planner Home actions or CLI equivalents):
1. Run health check / ci-check — all steps green
2. unified-verify — vendor pins and overlays current (if unified handoff)
3. Wiring audit attestation recorded if promoting memory or completing integration tasks
4. Active spec/plan/tasks reflect current work; no stale task bullets

Load @START_HERE.md and confirm read order.

Report:
- Active feature and next task
- Any failing ci-check or wiring-audit items
- Whether Deploy agent handoff needs re-run

Do not start implementation until handoff blockers are listed.""",
        ),
        AgentPromptTemplate(
            id="memory.promote",
            title="Promote durable memory (Continual Learning)",
            description="Distill repeated truths into AGENTS.md after wiring audit gates.",
            prompt="""I have Continual Learning candidates to promote into durable repo memory.

Before proposing changes:
1. Confirm wiring audit is complete (tasks.md checklist + .hive/wiring-audit.json)
2. Load @AGENTS.md and active @docs/specs/<feature>/spec.md
3. Load @docs/planning-rosetta-stone.md — memory and workflow.tools hooks

Rules:
- Operational facts → AGENTS.md ## Durable Workspace Facts
- Behavioral / product requirements → spec.md (not AGENTS.md)
- Reject one-off session noise and code-fence examples
- Prefer Hive Planner Promote memory → autonomous apply (auto-split / route) flow
- Or: `py -3.11 -m hive_planner agents-propose --candidates <file> --apply`

Candidates file or bullets:
<paste docs/proposals/candidates-*.md content or bullet list>

Propose which bullets are accepted, rejected, and why — prefer CLI apply over hand-editing AGENTS.md.""",
        ),
        AgentPromptTemplate(
            id="research.ground_truth_mine",
            title="Runner ground truth on mine",
            description="Mine Rosetta stones, cartridges, and PDFs as a temporary ground-truth distribution.",
            prompt="""okay runner ground truth on mine

Start this repo's ground-truth mine now. Read @.cursor/commands/ground-truth-on-mine.md (or @scripts/ground-truth-on-mine.md if the command is missing) and execute it in this turn.

The stones, cartridges, and PDFs are a training distribution for this inference: a temporary ground truth, not a single required reading. Bootstrap from the project, pin the claim against those sources, and search where they disagree or stop. Do not explain how to invoke the command.

Question: <what to mine, or leave blank for the active feature's open unknowns>""",
        ),
        AgentPromptTemplate(
            id="change.bug_hunt",
            title="Start a bug hunt",
            description="Trigger the installed find / fix / self-review / local-commit loop from chat.",
            prompt="""bug hunt

Start the project's continuous bug-hunt loop now. Read @.cursor/commands/bug-hunt.md (or @scripts/bug-hunt.md if the command is missing) and do the first iteration in this turn, then end the turn.

One iteration is one inference pass. After the outcome row, write the continue file named in the script and end the turn. The stop hook waits the script's pause: a positive number of seconds is not skippable, and 0 means it does not wait. Then the hook starts the next inference pass. Do not ask whether to continue. Enable, the fix ceiling, and Pause seconds live on a Controls block (Home → Loop controls, Bug hunt). Leave Pause seconds blank for 10. Enter 0 to skip the wait. The fix ceiling field defaults to 50. Do not explain how to invoke the command.""",
        ),
        AgentPromptTemplate(
            id="change.implementation_loop",
            title="Start the implementation loop",
            description="Trigger the installed post-spec coding loop from chat (implementation loop or code spec), or use Controls Install CodeSpec / Run instead of typing.",
            prompt="""implementation loop

Start this project's implementation loop now. Read @.cursor/commands/implementation-loop.md (or @scripts/implementation-loop.md if the command is missing) and execute it in this turn.

Hive Planner calls this loop CodeSpec on the Controls tab. Home has a CodeSpec button and Loop controls. Each block has its own Run, including Enable and Check pack, then Status, Start, Handoff, Check, Accept, and Commit. Saying code spec in chat is the same start. Controls Install CodeSpec installs on the Cursor window in front. Chat and Controls are both valid. Do not explain how to invoke the command.""",
        ),
        AgentPromptTemplate(
            id="change.agnostic_loop",
            title="Start the agnostic loop",
            description="Trigger the pause-cycle kit chooser (hive-loop-kit), or Home → Loop controls (Agnostic loop Run).",
            prompt="""agnostic loop

Start this project's agnostic loop now. Read @.cursor/commands/agnostic-loop.md (or @scripts/agnostic-loop.md if the command is missing) and execute it in this turn.

This is not CodeSpec and not a bug hunt. Enable is Run on an Agnostic loop block. Home → Loop controls (Agnostic loop Enable) installs the same files. Do not explain how to invoke the command.""",
        ),
        AgentPromptTemplate(
            id="planning.external_rosetta",
            title="External planning — Rosetta session (Gemini / Perplexity)",
            description="Paste after uploading the ejected Rosetta contract in a non-Cursor planning AI.",
            prompt=external_rosetta_session_prompt(),
        ),
        AgentPromptTemplate(
            id="feature.scaffold",
            title="New feature — Delta + spec scaffold",
            description="Start a new feature with holistic/macro/micro framing before Spec Kit tasks.",
            prompt="""Scaffold a new feature using the Hive Delta model.

Feature: <feature-id-or-name>
Goal: <one paragraph>

Load:
- @docs/planning-rosetta-stone.md — hooks context.delta, workflow.tools
- @docs/delta/00_holistic.md and @docs/delta/10_macro.md
- Example pattern: @docs/specs/example-feature/ if present
- @starter-kit/README.md feature prompt template if helpful

Produce (do not implement code yet):
1. Holistic link — which mission / invariant this serves
2. Macro touchpoints — modules, interfaces, contracts
3. Micro scope — files, tests, edge cases
4. Draft spec.md sections: requirements, acceptance criteria, out of scope
5. Suggested HOOK_ID(s) for this feature

Use /speckit.specify or project Spec Kit workflow when ready to formalize.""",
        ),
    )


def get_agent_prompt_template(template_id: str) -> AgentPromptTemplate | None:
    for template in default_agent_prompt_templates():
        if template.id == template_id:
            return template
    return None


def get_agent_prompt_template_by_title(title: str) -> AgentPromptTemplate | None:
    stripped = title.strip()
    if not stripped:
        return None
    for template in default_agent_prompt_templates():
        if template.title == stripped:
            return template
    return None


def format_agent_prompt_templates_markdown() -> str:
    """Export all templates as a single markdown doc (for docs/ or project bootstrap)."""
    lines = [
        "# Agent prompt templates",
        "",
        "Copy-paste these into Cursor (or your agent) to use Hive planning, sources, and cartridges effectively.",
        "Load files via `@` references — do not paste large repo files inline.",
        "",
    ]
    for template in default_agent_prompt_templates():
        lines.extend(
            [
                f"## {template.title}",
                "",
                f"*{template.description}*",
                "",
                "```md",
                template.prompt.rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
