from __future__ import annotations

import csv
from pathlib import Path

from hive_planner.models import NormalizeResult
from hive_planner.normalizers import EmptySourceError


def normalize_csv(file_path: Path) -> NormalizeResult:
    title = file_path.stem.replace("-", " ").title()
    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise EmptySourceError(f"Could not read CSV: {exc}") from exc

    if not raw.strip():
        raise EmptySourceError("CSV is empty")

    try:
        rows = list(csv.reader(raw.splitlines()))
    except csv.Error as exc:
        raise EmptySourceError(f"Could not parse CSV: {exc}") from exc

    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise EmptySourceError("CSV has no data rows")

    lines = [f"# {title}", ""]
    raw_parts: list[str] = []

    if len(rows) == 1 and len(rows[0]) == 1:
        text = rows[0][0].strip()
        lines.extend([text, ""])
        raw_parts.append(text)
    elif all(len(row) == 1 for row in rows):
        for row in rows:
            text = row[0].strip()
            if text:
                lines.extend([text, ""])
                raw_parts.append(text)
    else:
        headers = [cell.strip() or f"col{i + 1}" for i, cell in enumerate(rows[0])]
        data_rows = rows[1:] if len(rows) > 1 else []
        if not data_rows:
            for idx, header in enumerate(headers):
                line = f"{header}: {rows[0][idx].strip()}"
                lines.extend([line, ""])
                raw_parts.append(line)
        else:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in data_rows:
                padded = row + [""] * (len(headers) - len(row))
                cells = [cell.strip().replace("|", "\\|") for cell in padded[: len(headers)]]
                lines.append("| " + " | ".join(cells) + " |")
                raw_parts.append(" | ".join(cell.strip() for cell in padded[: len(headers)]))

    if not raw_parts:
        raise EmptySourceError("CSV has no extractable content")

    normalized_body = "\n".join(lines).strip() + "\n"
    return NormalizeResult(
        normalized_body=normalized_body,
        raw_text="\n".join(raw_parts),
        title=title,
        extra_metadata={"format": "csv", "row_count": len(rows)},
    )
