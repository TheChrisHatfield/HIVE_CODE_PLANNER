from __future__ import annotations

from dataclasses import dataclass, field


def _keyword_list(value: object) -> list[str]:
    """Index JSON may store keywords as null or a bare string."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _optional_page(value: object) -> int | None:
    if value is None or value is False:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


@dataclass
class SourceDocument:
    doc_id: str
    source_path: str
    format: str
    title: str
    content_hash: str
    category: str = "reference"


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    heading_path: str
    text: str
    keywords: list[str] = field(default_factory=list)
    chunk_index: int = 0
    page: int | None = None

    def __post_init__(self) -> None:
        self.keywords = _keyword_list(self.keywords)
        self.page = _optional_page(self.page)


@dataclass
class DocumentIndex:
    documents: list[SourceDocument] = field(default_factory=list)


@dataclass
class ChunkIndex:
    chunks: list[ChunkRecord] = field(default_factory=list)


@dataclass
class NormalizeResult:
    normalized_body: str
    raw_text: str
    title: str
    extra_metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.extra_metadata, dict):
            self.extra_metadata = {}
