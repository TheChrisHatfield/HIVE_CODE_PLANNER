"""Export Rosetta Stone planning session contract for external AI tools (Gemini, Perplexity, etc.)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CONTRACT_FILENAME = "ROSETTA-PLANNING-SESSION-CONTRACT.md"
PROMPT_FILENAME = "ROSETTA-SESSION-START-PROMPT.txt"
README_FILENAME = "README-ROSETTA-EJECT.txt"
EJECT_DIRNAME = "rosetta-eject"

ROSETTA_CARTRIDGE_BLURB = (
    "A Rosetta cartridge is a portable planning pack for external AIs — not your in-repo "
    "cartridge/ folder. Eject exports a session contract plus a paste-ready prompt so "
    "Gemini, Perplexity, or ChatGPT can scan planning chat, tag concepts with HOOK_ID "
    "markers, and produce a Planning Rosetta Stone legend to bring back into this repo."
)

ROSETTA_EJECT_TOOLTIP = (
    "Export a Rosetta cartridge — a portable planning pack that teaches Gemini, Perplexity, "
    "or ChatGPT how to tag chat output with hooks and build a Rosetta Stone legend inline."
)

SESSION_START_PROMPT_TEMPLATE = """I've uploaded the Rosetta Stone Planning Session Contract.

Follow it for ALL documents you produce in this session:
- HTML meta header on every file
- [HOOK:...] section headings on major concepts
- Inline `hook_id` references in body text
- [CTX:...] context members in long sections with Promote to paths
- <!-- ROSETTA-NAV --> on spec/plan/tasks/feature briefs
- Deliver a Planning Rosetta Stone index at the end

When scanning an existing chat or thread export, tag each major concept with hooks and
[CTX:...] members as you distill it — do not leave concepts untagged in prose-only form.

Project name: {project_name}
"""


class RosettaEjectError(Exception):
    """Rosetta cartridge eject failed."""


@dataclass
class RosettaEjectResult:
    output_dir: Path
    contract_path: Path
    prompt_path: Path
    readme_path: Path
    project_name: str
    contract_source: Path
    files_written: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "output_dir": str(self.output_dir),
            "contract_path": str(self.contract_path),
            "prompt_path": str(self.prompt_path),
            "readme_path": str(self.readme_path),
            "project_name": self.project_name,
            "contract_source": str(self.contract_source),
            "files_written": list(self.files_written),
        }


def _packaged_contract_path() -> Path:
    return Path(__file__).resolve().parent / "bootstrap_templates" / CONTRACT_FILENAME


def _contract_file_usable(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def resolve_session_contract_path(repo_root: Path | None = None) -> Path | None:
    """Prefer non-empty repo docs copy; fall back to packaged bootstrap template."""
    if repo_root is not None:
        repo_contract = repo_root / "docs" / CONTRACT_FILENAME
        if _contract_file_usable(repo_contract):
            return repo_contract
    packaged = _packaged_contract_path()
    if _contract_file_usable(packaged):
        return packaged
    return None


def load_session_contract_text(*, repo_root: Path | None = None) -> str:
    source = resolve_session_contract_path(repo_root)
    if source is None:
        raise RosettaEjectError(
            f"Rosetta session contract not found (expected docs/{CONTRACT_FILENAME} or packaged template)"
        )
    return source.read_text(encoding="utf-8")


def infer_project_name(repo_root: Path | None = None) -> str:
    if repo_root is not None:
        name = repo_root.name.strip()
        if name and name not in {".", ".."}:
            return name
    return "My Project"


def build_session_start_prompt(*, project_name: str) -> str:
    name = project_name.strip() or "My Project"
    return SESSION_START_PROMPT_TEMPLATE.format(project_name=name).rstrip() + "\n"


def _build_readme(*, project_name: str) -> str:
    return "\n".join(
        [
            "Rosetta cartridge eject — external planning session",
            "",
            f"Project: {project_name}",
            "",
            "How to use with Perplexity, Google Gemini, ChatGPT, Claude, or NotebookLM:",
            "",
            f"1. Upload {CONTRACT_FILENAME} to the planning session.",
            f"2. Paste the text from {PROMPT_FILENAME} as your first message (or after upload).",
            "3. Plan normally — the AI must tag every artifact with HOOK_ID markers and inline legend rules.",
            "4. At session end, save the produced Planning Rosetta Stone into your repo as docs/planning-rosetta-stone.md.",
            "",
            "The contract teaches any LLM how to scan chat/thread exports and set up the Rosetta Stone legend inline.",
            "",
        ]
    )


def eject_rosetta_cartridge(
    output_dir: Path,
    *,
    repo_root: Path | None = None,
    project_name: str | None = None,
) -> RosettaEjectResult:
    """Write contract + session-start prompt + README under output_dir/rosetta-eject/."""
    source = resolve_session_contract_path(repo_root)
    if source is None:
        raise RosettaEjectError(
            f"Rosetta session contract not found (expected docs/{CONTRACT_FILENAME} or packaged template)"
        )

    name = (project_name or infer_project_name(repo_root)).strip() or "My Project"
    bundle_dir = output_dir / EJECT_DIRNAME
    bundle_dir.mkdir(parents=True, exist_ok=True)

    contract_path = bundle_dir / CONTRACT_FILENAME
    contract_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")

    prompt_path = bundle_dir / PROMPT_FILENAME
    prompt_path.write_text(build_session_start_prompt(project_name=name), encoding="utf-8", newline="\n")

    readme_path = bundle_dir / README_FILENAME
    readme_path.write_text(_build_readme(project_name=name), encoding="utf-8", newline="\n")

    written = [
        contract_path.relative_to(output_dir).as_posix(),
        prompt_path.relative_to(output_dir).as_posix(),
        readme_path.relative_to(output_dir).as_posix(),
    ]
    return RosettaEjectResult(
        output_dir=bundle_dir,
        contract_path=contract_path,
        prompt_path=prompt_path,
        readme_path=readme_path,
        project_name=name,
        contract_source=source,
        files_written=written,
    )
