from __future__ import annotations

import re

from hive_planner.models import ChunkRecord

TARGET_CHARS = 1600
OVERLAP_CHARS = 240
PAGE_HEADING_RE = re.compile(r"^(?:Page|Slide)\s+(\d+)$", re.IGNORECASE)


def _keywords(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
    seen: set[str] = set()
    result: list[str] = []
    for word in words:
        if word in seen:
            continue
        seen.add(word)
        result.append(word)
        if len(result) >= limit:
            break
    return result


def _page_from_heading(heading: str) -> int | None:
    match = PAGE_HEADING_RE.match(heading.strip())
    if match:
        return int(match.group(1))
    if " > " in heading:
        tail = heading.split(" > ")[-1]
        match = PAGE_HEADING_RE.match(tail.strip())
        if match:
            return int(match.group(1))
    return None


_FENCE_LINE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")


def _open_fence(line: str) -> str:
    """Return the fence marker when line opens a fence. Indented code does not."""
    match = _FENCE_LINE.match(line)
    if not match:
        return ""
    token = match.group(2)
    info = match.group(3)
    if token.startswith("`") and "`" in info:
        return ""
    return token


def _closes_fence(line: str, marker: str) -> bool:
    match = _FENCE_LINE.match(line)
    if not match:
        return False
    token = match.group(2)
    if token[0] != marker[0] or len(token) < len(marker):
        return False
    return match.group(3).strip() == ""


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading_stack: list[str] = []
    current_lines: list[str] = []
    fence_marker = ""

    def flush_section() -> None:
        nonlocal current_lines
        if not current_lines:
            return
        heading_path = " > ".join(heading_stack) if heading_stack else "document"
        sections.append((heading_path, "\n".join(current_lines).strip()))
        current_lines = []

    for line in text.splitlines():
        if fence_marker:
            if _closes_fence(line, fence_marker):
                fence_marker = ""
            current_lines.append(line)
            continue
        opened = _open_fence(line)
        if opened:
            fence_marker = opened
            current_lines.append(line)
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            flush_section()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip() or "section"
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            current_lines = [line]
        else:
            current_lines.append(line)

    flush_section()

    if not sections:
        body = text.strip()
        if body:
            sections = [("document", body)]

    return sections


def _section_has_content(body: str) -> bool:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^#{1,6}\s", stripped):
            continue
        return True
    return False


def _append_chunk(
    chunks: list[ChunkRecord],
    doc_id: str,
    heading_path: str,
    text: str,
    idx: int,
) -> int:
    page = _page_from_heading(heading_path)
    chunks.append(
        ChunkRecord(
            chunk_id=f"{doc_id}-c{idx:03d}",
            doc_id=doc_id,
            heading_path=heading_path,
            text=text,
            keywords=_keywords(text),
            chunk_index=idx,
            page=page,
        )
    )
    return idx + 1


def chunk_markdown(doc_id: str, text: str) -> list[ChunkRecord]:
    sections = _split_markdown_sections(text)

    chunks: list[ChunkRecord] = []
    idx = 0
    for heading_path, body in sections:
        if not body or not _section_has_content(body):
            continue
        if len(body) <= TARGET_CHARS:
            idx = _append_chunk(chunks, doc_id, heading_path, body, idx)
            continue

        start = 0
        while start < len(body):
            end = min(start + TARGET_CHARS, len(body))
            piece = body[start:end]
            idx = _append_chunk(chunks, doc_id, heading_path, piece, idx)
            if end >= len(body):
                break
            next_start = end - OVERLAP_CHARS
            if next_start <= start:
                next_start = start + 1
            start = next_start

    return chunks


def chunk_plain_text(doc_id: str, title: str, text: str) -> list[ChunkRecord]:
    if not text.strip():
        return []
    wrapped = f"# {title}\n\n{text}"
    return chunk_markdown(doc_id, wrapped)
