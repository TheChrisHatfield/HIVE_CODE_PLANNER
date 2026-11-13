#!/usr/bin/env python3
"""Build the next paste-ready Claude Haiku prompt for Voice_Bot (haiku handoff).

Stdlib only. Reads the current § Prompt and a pasted Haiku Continue block, then writes
the next `=== PASTE INTO HAIKU ===` prompt.

- If ANTHROPIC_API_KEY is set (and --no-llm is not passed), Claude Haiku rewrites the prompt.
  Its output is accepted only if it still contains the Continue block fields.
- Otherwise (or if the model output is rejected), a deterministic template is used.

Usage:
  py -3.11 scripts/haiku_handoff.py --continue-file <path-to-pasted-continue.txt>
  py -3.11 scripts/haiku_handoff.py --continue-file <path> --no-llm
  py -3.11 scripts/haiku_handoff.py --continue-file <path> --no-update-handoff

Exit codes: 0 ok, 2 bad Continue input, 3 handoff file missing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs" / "specs" / "Voice_Bot" / "haiku-100k-handoff.md"
OUT = ROOT / "docs" / "specs" / "Voice_Bot" / "next-haiku-prompt.md"
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("HAIKU_MODEL", "claude-haiku-4-5")

REQUIRED_FIELDS = ("Last chat:", "Budget left:", "Verdict:", "Done this chat:", "Open next:", "First action:")
OPTIONAL_FIELDS = ("Do not redo:", "Files changed:", "Blocked:", "G0–G6:")
CONTINUE_RE = re.compile(r"CONTINUE Voice_Bot\n.*?First action:[^\n]*", re.S)

RULE_SUFFIX = (
    "Do First action only; emit the Continue block again at end of turn. "
    "Never start the next micro-task in the same turn. "
    "If this chat nears ~100k context, stop after the current micro-task and end with a filled "
    "Continue block so Cursor can generate the next paste."
)


def read_prompt_section(text: str) -> str:
    start = text.index("## § Prompt")
    body_start = text.index("\n", start) + 1
    end = text.index("### Last Continue", body_start)
    return text[body_start:end].strip()


def parse_continue(raw: str) -> dict[str, str]:
    matches = list(CONTINUE_RE.finditer(raw))
    if not matches:
        raise ValueError("no 'CONTINUE Voice_Bot' block found in the pasted text")
    # The filled block is at the end of Haiku's reply; an earlier hit is the
    # instruction template (placeholders) that the same paste often still contains.
    block = matches[-1].group(0)
    known = REQUIRED_FIELDS + OPTIONAL_FIELDS
    fields: dict[str, str] = {}
    current: str | None = None
    for line in block.splitlines()[1:]:
        matched_key = next((key for key in known if line.startswith(key)), None)
        if matched_key is not None:
            current = matched_key.rstrip(":")
            fields[current] = line[len(matched_key) :].strip()
            continue
        if current is None:
            continue
        extra = line.strip()
        if extra:
            fields[current] = f"{fields[current]} {extra}".strip()
    missing = [k.rstrip(":") for k in REQUIRED_FIELDS if k.rstrip(":") not in fields]
    if missing:
        raise ValueError(f"Continue block missing fields: {', '.join(missing)}")
    fields["_block"] = block
    return fields


def template_prompt(cont: dict[str, str]) -> str:
    do_not_redo = cont.get("Do not redo", "see prior Continue block.")
    shape = "\n".join(
        [
            "CONTINUE Voice_Bot",
            "Last chat: <date>",
            "Budget left: <low|unknown>",
            "Verdict: read-only=<READY|NOT> full-agent=<READY|NOT>",
            "G0–G6: <one-liners if changed>",
            "Done this chat: <1–3 bullets>",
            "Open next: <exactly one micro-task>",
            "Do not redo: <commands that passed>",
            "Files changed: <paths>",
            "Blocked: <or none>",
            "First action: <one line>",
        ]
    )
    sections = [
        "=== PASTE INTO HAIKU ===",
        f"Voice_Bot next micro-task (from chat ending {cont['Last chat']}). Repo: D:\\DRIVE_DOWNLOADS\\HIVE_CODE_PLANNER. Python: py -3.11.",
        f"Verdict carried over: {cont['Verdict']}",
        f"Done last chat: {cont['Done this chat']}",
        f"Do not redo: {do_not_redo}",
        f"This chat, one micro-task only: {cont['Open next']}",
        f"First action: {cont['First action']}",
        "Context: read only the sections named in Open next from docs/specs/Voice_Bot/{spec.md,tasks.md,"
        "evidence-register.md,deployment-gaps.md}. Do not load full spec.md or src/ trees.",
        RULE_SUFFIX,
        "Every turn MUST end with a filled block exactly in this shape:",
        "```",
        shape,
        "```",
        "=== END PASTE ===",
    ]
    return "\n\n".join(sections)


def llm_prompt(prev_prompt: str, cont: dict[str, str]) -> str | None:
    """Ask Claude Haiku to rewrite the prompt. Returns None on any failure (caller falls back)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    instruction = (
        "Rewrite the following Voice_Bot handoff into ONE compact paste-ready prompt for a new Claude Haiku chat. "
        "Under 350 words. Keep the repo path, py -3.11, the single micro-task, the do-not-redo list, and the "
        "rule: " + RULE_SUFFIX + " End with the Continue block template (fields: Last chat, Budget left, Verdict, "
        "G0–G6, Done this chat, Open next, Do not redo, Files changed, Blocked, First action). "
        "Wrap the output in === PASTE INTO HAIKU === and === END PASTE ==="
    )
    body = (
        f"{instruction}\n\n--- CURRENT PROMPT ---\n{prev_prompt}\n\n--- PASTED CONTINUE BLOCK ---\n{cont['_block']}"
    )
    payload = json.dumps(
        {"model": MODEL, "max_tokens": 1200, "messages": [{"role": "user", "content": body}]}
    ).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        print(f"[haiku_handoff] API call failed, using template: {exc}", file=sys.stderr)
        return None
    if "=== PASTE INTO HAIKU ===" not in text or "Open next:" not in text or "First action:" not in text:
        print("[haiku_handoff] model output rejected (missing required fields), using template", file=sys.stderr)
        return None
    return text.strip()


def update_handoff(text: str, new_prompt_body: str) -> str:
    start = text.index("## § Prompt")
    body_start = text.index("\n", start) + 1
    end = text.index("### Last Continue", body_start)
    paragraph = new_prompt_body.replace("=== PASTE INTO HAIKU ===", "").replace("=== END PASTE ===", "").strip()
    return text[:body_start] + "\n" + paragraph + "\n\n" + text[end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--continue-file", required=True, type=Path, help="file holding the pasted Haiku Continue block")
    parser.add_argument("--no-llm", action="store_true", help="never call the API; use the template")
    parser.add_argument("--no-update-handoff", action="store_true", help="do not rewrite § Prompt in the handoff file")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    if not HANDOFF.exists():
        print(f"handoff file missing: {HANDOFF}", file=sys.stderr)
        return 3
    try:
        cont = parse_continue(args.continue_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"bad Continue input: {exc}", file=sys.stderr)
        return 2

    handoff = HANDOFF.read_text(encoding="utf-8")
    prev = read_prompt_section(handoff)

    source = "template"
    prompt = None if args.no_llm else llm_prompt(prev, cont)
    if prompt is not None:
        source = "haiku"
    else:
        prompt = template_prompt(cont)

    OUT.write_text(prompt + "\n", encoding="utf-8")
    if not args.no_update_handoff:
        HANDOFF.write_text(update_handoff(handoff, prompt), encoding="utf-8")

    print(f"[haiku_handoff] source={source} wrote={OUT.relative_to(ROOT)}")
    print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
