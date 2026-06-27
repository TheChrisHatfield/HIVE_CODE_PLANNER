from __future__ import annotations

from pathlib import Path

from hive_planner.config import RepoPaths

AUTO_SYNC_PREFIX = "<!-- AUTO-SYNC:"
DRAFT_MARKER = "<!-- DRAFT:"
MANUAL_MARKER = "<!-- MANUAL:"


def _repo_relative(paths: RepoPaths, path: Path) -> str:
    try:
        return path.relative_to(paths.root).as_posix()
    except ValueError:
        return path.as_posix()


def _auto_sync_banner(source: Path, paths: RepoPaths) -> str:
    return f"{AUTO_SYNC_PREFIX} from {_repo_relative(paths, source)} -->"


def _strip_leading_banner(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].strip().startswith(AUTO_SYNC_PREFIX):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    body = "\n".join(lines).strip()
    return f"{body}\n" if body else ""


def _first_content_line(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _should_skip_existing(target: Path, *, force: bool) -> tuple[bool, str]:
    if force or not target.exists():
        return False, ""
    content = target.read_text(encoding="utf-8")
    first_line = _first_content_line(content)
    if first_line.startswith(AUTO_SYNC_PREFIX):
        return False, ""
    if first_line.startswith(DRAFT_MARKER) or first_line.startswith(MANUAL_MARKER):
        return True, "draft or manual banner"
    if DRAFT_MARKER in content or MANUAL_MARKER in content:
        return True, "draft or manual banner"
    return True, "exists without auto-sync banner"


def sync_delta_file(
    paths: RepoPaths,
    source: Path,
    target: Path,
    *,
    force: bool = False,
) -> tuple[str, Path | None]:
    if not source.exists():
        return "missing", None

    skip, reason = _should_skip_existing(target, force=force)
    if skip:
        return f"skipped ({reason})", None

    body = _strip_leading_banner(source.read_text(encoding="utf-8"))
    banner = _auto_sync_banner(source, paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    status = "updated" if target.exists() else "written"
    target.write_text(f"{banner}\n\n{body}", encoding="utf-8")
    return status, target


def sync_delta_cartridge(
    paths: RepoPaths,
    feature: str,
    *,
    force: bool = False,
) -> tuple[dict[str, str], dict[str, Path], list[str]]:
    warnings: list[str] = []
    results: dict[str, str] = {}
    written: dict[str, Path] = {}

    sources = {
        "holistic": paths.root / "docs" / "delta" / "00_holistic.md",
        "macro": paths.root / "docs" / "delta" / "10_macro.md",
        "micro": paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md",
    }
    targets = {
        "holistic": paths.cartridge / "holistic.md",
        "macro": paths.cartridge / "macro.md",
        "micro": paths.cartridge / "micro" / f"{feature}.md",
    }

    for layer in ("holistic", "macro", "micro"):
        status, out_path = sync_delta_file(paths, sources[layer], targets[layer], force=force)
        results[layer] = status
        if out_path:
            written[layer] = out_path
        elif status.startswith("skipped"):
            rel = targets[layer].relative_to(paths.cartridge).as_posix()
            warnings.append(f"Skipped cartridge/{rel} ({status})")
        elif status == "missing" and layer in {"holistic", "macro"}:
            warnings.append(f"Missing Delta source: {_repo_relative(paths, sources[layer])}")

    return results, written, warnings
