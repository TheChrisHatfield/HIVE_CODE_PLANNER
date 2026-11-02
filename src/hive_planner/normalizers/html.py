from __future__ import annotations

from pathlib import Path

from hive_planner.models import NormalizeResult
from hive_planner.normalizers import EmptySourceError, MissingDependencyError

_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table")


def _table_lines(table) -> list[str]:
    """One line per row. Cell text is not visited as its own block."""
    lines: list[str] = []
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells: list[str] = []
        for cell in row.find_all(["td", "th"], recursive=False):
            text = cell.get_text(" ", strip=True)
            if text:
                cells.append(text)
        if cells:
            lines.append(" | ".join(cells))
    return lines


def _should_skip_element(element) -> bool:
    if element.find_parent("li") and element.name != "li":
        return True
    if element.name == "li" and element.find_parent("li"):
        return True
    if element.find_parent(["td", "th", "table"]):
        return True
    return False


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = path.read_bytes()
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            return raw.decode("utf-16")
        raise


def normalize_html(file_path: Path) -> NormalizeResult:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise MissingDependencyError(
            "HTML support requires beautifulsoup4: pip install -e '.[html]'"
        ) from exc

    try:
        raw_html = _read_text(file_path)
    except OSError as exc:
        raise EmptySourceError(f"Could not read HTML: {exc}") from exc

    if not raw_html.strip():
        raise EmptySourceError("HTML file is empty")

    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    title = (
        title_tag.get_text(strip=True)
        if title_tag and title_tag.get_text(strip=True)
        else h1_tag.get_text(strip=True)
        if h1_tag and h1_tag.get_text(strip=True)
        else file_path.stem.replace("-", " ").title()
    )

    lines: list[str] = [f"# {title}", ""]
    raw_parts: list[str] = []
    seen_text: set[str] = set()
    root = soup.body or soup

    for element in root.find_all(_BLOCK_TAGS):
        if element.name == "table":
            if element.find_parent("table"):
                continue
            for text in _table_lines(element):
                if not text or text in seen_text:
                    continue
                seen_text.add(text)
                lines.append(text)
                lines.append("")
                raw_parts.append(text)
            continue
        if _should_skip_element(element):
            continue
        name = element.name or ""
        text = element.get_text(" ", strip=True)
        if not text or text in seen_text:
            continue
        if name == "h1" and text.lower() == title.lower():
            continue
        seen_text.add(text)
        if name.startswith("h") and len(name) == 2 and name[1].isdigit():
            level = int(name[1])
            lines.append(f"{'#' * min(level + 1, 6)} {text}")
            lines.append("")
        else:
            lines.append(text)
            lines.append("")
        raw_parts.append(text)

    if not raw_parts:
        body = soup.body
        body_text = body.get_text("\n", strip=True) if body else ""
        if not body_text:
            raise EmptySourceError("HTML has no extractable text")
        lines.extend([body_text, ""])
        raw_parts.append(body_text)

    normalized_body = "\n".join(lines).strip() + "\n"
    return NormalizeResult(
        normalized_body=normalized_body,
        raw_text="\n".join(raw_parts),
        title=title,
        extra_metadata={"format": "html"},
    )
