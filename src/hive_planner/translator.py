from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from hive_planner.config import RepoPaths

Bucket = Literal["holistic", "macro", "micro", "memory", "reject"]

DRAFT_BANNER = "<!-- DRAFT: review before promoting -->"
MAX_BULLET_CHARS = 240

CLASS_KEYWORDS: dict[Bucket, tuple[str, ...]] = {
    "holistic": (
        "mission",
        "goal",
        "non-goal",
        "invariant",
        "success criteria",
        "constraint",
        "problem",
        "purpose",
    ),
    "macro": (
        "subsystem",
        "architecture",
        "workflow",
        "module",
        "interface",
        "data contract",
    ),
    "micro": (
        "acceptance criteria",
        "file scope",
        "edge case",
        "active task",
        "bug gate",
        "feature name",
    ),
    "memory": (
        "durable",
        "always",
        "never",
        "guardrail",
        "agents.md",
        "promote",
    ),
}

HEADING_BUCKET_HINTS: dict[Bucket, tuple[str, ...]] = {
    "holistic": ("holistic", "mission", "goal", "purpose", "problem", "non-goal"),
    "macro": ("macro", "architecture", "workflow", "subsystem", "module"),
    "micro": ("micro", "feature", "task", "acceptance", "scope", "validation"),
    "memory": ("memory", "guardrail", "agents"),
}

BUCKET_PRIORITY: tuple[Bucket, ...] = ("holistic", "macro", "micro", "memory")
SPECSEED_KEYWORDS = ("acceptance criteria", "requirement", "behavior", "must")
TABLE_LINE_RE = re.compile(r"^\|.*\|$")
TABLE_SEP_RE = re.compile(r"^\|?[\s\-:|]+\|?$")


def _specseed_matches(bullet: str) -> bool:
    lowered = bullet.lower()
    for kw in SPECSEED_KEYWORDS:
        if " " in kw:
            if kw in lowered:
                return True
        elif re.search(rf"\b{re.escape(kw)}\b", lowered):
            return True
    return False


class TranslatorError(Exception):
    """Translator input or emit failed."""


@dataclass
class ClassifiedSegment:
    text: str
    bucket: Bucket
    compressed: str = ""


@dataclass
class TranslatorResult:
    status: str
    cartridge_id: str
    files_written: list[str] = field(default_factory=list)
    promotions: dict[str, int | bool] = field(default_factory=dict)
    rejections: int = 0
    classification_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "cartridge_id": self.cartridge_id,
            "files_written": self.files_written,
            "promotions": self.promotions,
            "rejections": self.rejections,
            "classification_counts": self.classification_counts,
        }


def _normalize_for_dedupe(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return bool(TABLE_LINE_RE.match(stripped) or TABLE_SEP_RE.match(stripped))


def _is_structural_noise(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return True
    if all(_is_table_line(ln) for ln in lines):
        return True
    if all(ln in {"---", "***", "___"} or ln.startswith("---") for ln in lines):
        return True
    prose_chars = sum(len(re.sub(r"[|`\-*\[\]()#>\s]", "", ln)) for ln in lines)
    if prose_chars < 8:
        return True
    return False


def segment_text(text: str) -> list[str]:
    """Split markdown into segments by headings and blank-line paragraphs."""
    segments: list[str] = []
    current_heading = ""
    paragraph_lines: list[str] = []
    in_fence = False

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        body = "\n".join(paragraph_lines).strip()
        paragraph_lines = []
        if not body:
            return
        if current_heading:
            segments.append(f"{current_heading}\n\n{body}")
        else:
            segments.append(body)

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            paragraph_lines.append(line)
            continue

        heading_match = None if in_fence else re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            flush_paragraph()
            current_heading = heading_match.group(2).strip()
            continue
        if not line.strip():
            flush_paragraph()
            continue
        paragraph_lines.append(line)

    flush_paragraph()

    if segments:
        return segments

    body = text.strip()
    return [body] if body else []


def _split_segment(segment: str) -> tuple[str, str]:
    if "\n\n" in segment:
        heading, body = segment.split("\n\n", 1)
        return heading.strip(), body.strip()
    return "", segment.strip()


def _heading_bucket_hint(heading: str) -> Bucket | None:
    lowered = heading.lower()
    best: Bucket | None = None
    best_score = 0
    for bucket in BUCKET_PRIORITY:
        score = sum(1 for hint in HEADING_BUCKET_HINTS[bucket] if hint in lowered)
        if score > best_score:
            best_score = score
            best = bucket
    return best


def _keyword_matches(keyword: str, haystack: str) -> bool:
    if " " in keyword:
        return keyword in haystack
    return re.search(rf"\b{re.escape(keyword)}\b", haystack, re.IGNORECASE) is not None


def classify_segment(segment: str) -> Bucket:
    heading, body = _split_segment(segment)
    if _is_structural_noise(body):
        return "reject"

    haystack = body.lower()
    scores: dict[Bucket, int] = {
        bucket: sum(1 for kw in CLASS_KEYWORDS[bucket] if _keyword_matches(kw, haystack))
        for bucket in BUCKET_PRIORITY
    }

    hint = _heading_bucket_hint(heading) if heading else None
    if hint:
        scores[hint] += 2

    best_bucket = max(BUCKET_PRIORITY, key=lambda b: scores[b])
    if scores[best_bucket] == 0:
        return "reject"
    return best_bucket


def compress_segment(segment: str) -> str:
    _, body = _split_segment(segment)
    text = re.sub(r"\s+", " ", body.strip())
    text = re.sub(r"^[-*]\s+", "", text)
    if len(text) > MAX_BULLET_CHARS:
        text = text[: MAX_BULLET_CHARS - 3].rstrip() + "..."
    return f"- {text}" if text else ""


def _dedupe_bullets(bullets: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for bullet in bullets:
        if not bullet:
            continue
        key = _normalize_for_dedupe(bullet)
        if key in seen:
            continue
        seen.add(key)
        result.append(bullet)
    return result


def _resolve_input_path(paths: RepoPaths, input_path: Path) -> Path:
    candidate = input_path if input_path.is_absolute() else paths.root / input_path
    if not candidate.exists():
        raise TranslatorError(f"Input file not found: {input_path}")
    if not candidate.is_file():
        raise TranslatorError(f"Input path is not a file: {input_path}")
    return candidate.resolve()


def _cartridge_relative(path: Path, cartridge_root: Path) -> str:
    return path.relative_to(cartridge_root).as_posix()


def _allowed_cartridge_path(cartridge_root: Path, target: Path) -> None:
    resolved = target.resolve()
    root = cartridge_root.resolve()
    if root not in resolved.parents and resolved != root:
        raise TranslatorError(f"Refusing to write outside cartridge/: {target}")


def _write_draft_markdown(path: Path, title: str, bullets: list[str], cartridge_root: Path) -> None:
    _allowed_cartridge_path(cartridge_root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(bullets) if bullets else "- (no segments classified for this bucket)"
    content = f"{DRAFT_BANNER}\n\n# {title}\n\n{body}\n"
    path.write_text(content, encoding="utf-8")


def translate_document(paths: RepoPaths, input_path: Path, feature: str) -> TranslatorResult:
    source = _resolve_input_path(paths, input_path)
    text = source.read_text(encoding="utf-8", errors="replace")
    raw_segments = segment_text(text)
    if not raw_segments:
        raise TranslatorError(f"No segments found in input: {input_path}")

    classified: list[ClassifiedSegment] = []
    counts: dict[str, int] = {b: 0 for b in (*BUCKET_PRIORITY, "reject")}

    for segment in raw_segments:
        bucket = classify_segment(segment)
        counts[bucket] += 1
        compressed = compress_segment(segment)
        if bucket == "reject" or not compressed:
            continue
        classified.append(ClassifiedSegment(text=segment, bucket=bucket, compressed=compressed))

    buckets: dict[Bucket, list[str]] = {b: [] for b in BUCKET_PRIORITY}
    for item in classified:
        buckets[item.bucket].append(item.compressed)

    for bucket in BUCKET_PRIORITY:
        buckets[bucket] = _dedupe_bullets(buckets[bucket])

    cartridge_root = paths.cartridge.resolve()
    paths.cartridge.mkdir(parents=True, exist_ok=True)

    cartridge_id = f"ctx-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{feature}"
    files_written: list[str] = []

    outputs = {
        cartridge_root / "holistic.md": ("Holistic Context (draft)", buckets["holistic"]),
        cartridge_root / "macro.md": ("Macro Architecture (draft)", buckets["macro"]),
        cartridge_root / "micro" / f"{feature}.md": (f"Micro Brief: {feature} (draft)", buckets["micro"]),
        cartridge_root / "memory.md": ("Memory Candidates (draft)", buckets["memory"]),
    }

    for path, (title, bullets) in outputs.items():
        _write_draft_markdown(path, title, bullets, cartridge_root)
        files_written.append(_cartridge_relative(path, cartridge_root))

    specseed_created = False
    specseed_bullets = [b for b in buckets["micro"] if _specseed_matches(b)]
    if specseed_bullets:
        spec_path = cartridge_root / "specs" / f"{feature}.specseed.md"
        _write_draft_markdown(
            spec_path,
            f"Spec Seed: {feature} (draft)",
            _dedupe_bullets(specseed_bullets),
            cartridge_root,
        )
        files_written.append(_cartridge_relative(spec_path, cartridge_root))
        specseed_created = True

    agents_candidates = len(buckets["memory"])
    cursor_candidates = sum(
        1 for b in buckets["memory"] if re.search(r"\brule\b", b, re.IGNORECASE)
    )

    return TranslatorResult(
        status="ok",
        cartridge_id=cartridge_id,
        files_written=files_written,
        promotions={
            "agents_md_candidates": agents_candidates,
            "cursor_rule_candidates": cursor_candidates,
            "spec_seed_created": specseed_created,
        },
        rejections=counts["reject"],
        classification_counts=counts,
    )


def write_translator_status(paths: RepoPaths, result: TranslatorResult) -> Path:
    status_path = paths.cartridge / "translator-status.json"
    _allowed_cartridge_path(paths.cartridge, status_path)
    paths.cartridge.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return status_path
