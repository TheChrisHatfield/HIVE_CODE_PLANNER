from __future__ import annotations

from dataclasses import dataclass, field


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
