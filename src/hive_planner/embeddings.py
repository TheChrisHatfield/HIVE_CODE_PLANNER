from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field

from hive_planner.discovery import content_hash
from hive_planner.models import ChunkIndex, ChunkRecord, DocumentIndex

BUILTIN_MODEL_ID = "hive-tfidf-v1"
ST_MODEL_ID = "all-MiniLM-L6-v2"
VECTOR_DIM = 384
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")


class EmbeddingDependencyError(Exception):
    """Optional embedding backend unavailable."""


@dataclass
class EmbeddingRecord:
    chunk_id: str
    content_hash: str
    model_id: str
    vector: list[float]


@dataclass
class EmbeddingIndex:
    model_id: str = BUILTIN_MODEL_ID
    embeddings: list[EmbeddingRecord] = field(default_factory=list)


def sentence_transformer_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def active_model_id() -> str:
    return ST_MODEL_ID if sentence_transformer_available() else BUILTIN_MODEL_ID


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def _builtin_embed_text(text: str, dim: int = VECTOR_DIM) -> list[float]:
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % dim
        vec[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


_model_singleton = None


def _sentence_transformer_model():
    global _model_singleton
    if _model_singleton is None:
        from sentence_transformers import SentenceTransformer

        _model_singleton = SentenceTransformer(ST_MODEL_ID)
    return _model_singleton


def embed_texts(texts: list[str], *, model_id: str | None = None) -> tuple[list[list[float]], str]:
    if not texts:
        return [], model_id or active_model_id()
    chosen = model_id or active_model_id()
    if chosen == ST_MODEL_ID and sentence_transformer_available():
        model = _sentence_transformer_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [list(map(float, row)) for row in vectors], ST_MODEL_ID
    return [_builtin_embed_text(text) for text in texts], BUILTIN_MODEL_ID


def embed_query(feature: str, *, model_id: str | None = None) -> list[float]:
    query = feature.replace("-", " ")
    vectors, _ = embed_texts([query], model_id=model_id)
    return vectors[0] if vectors else _builtin_embed_text(query)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def load_embedding_index(path) -> EmbeddingIndex:
    if not path.exists():
        return EmbeddingIndex(model_id=active_model_id())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return EmbeddingIndex(model_id=active_model_id())
    if not isinstance(data, dict):
        return EmbeddingIndex(model_id=active_model_id())
    rows = data.get("embeddings", [])
    embeddings: list[EmbeddingRecord] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                embeddings.append(
                    EmbeddingRecord(
                        chunk_id=row["chunk_id"],
                        content_hash=row["content_hash"],
                        model_id=row.get("model_id", BUILTIN_MODEL_ID),
                        vector=list(row["vector"]),
                    )
                )
            except (KeyError, TypeError):
                continue
    return EmbeddingIndex(model_id=data.get("model_id", active_model_id()), embeddings=embeddings)


def save_embedding_index(path, index: EmbeddingIndex) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_id": index.model_id,
        "embeddings": [asdict(row) for row in index.embeddings],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def embedding_lookup(index: EmbeddingIndex) -> dict[str, list[float]]:
    return {row.chunk_id: row.vector for row in index.embeddings}


def prune_embedding_index(index: EmbeddingIndex, active_chunk_ids: set[str]) -> int:
    before = len(index.embeddings)
    index.embeddings = [row for row in index.embeddings if row.chunk_id in active_chunk_ids]
    return before - len(index.embeddings)


def sync_embedding_index(
    embedding_path,
    chunk_index: ChunkIndex,
    *,
    force: bool = False,
) -> tuple[EmbeddingIndex, list[str]]:
    warnings: list[str] = []
    active_model = active_model_id()
    index = load_embedding_index(embedding_path)
    active_chunk_ids = {chunk.chunk_id for chunk in chunk_index.chunks}

    prior = {
        row.chunk_id: row
        for row in index.embeddings
        if row.chunk_id in active_chunk_ids and row.model_id == active_model
    }
    if index.model_id != active_model:
        prior = {}
        warnings.append(f"Embedding model changed — rebuilding index as {active_model}")

    kept: list[EmbeddingRecord] = []
    to_embed: list[ChunkRecord] = []
    for chunk in chunk_index.chunks:
        digest = content_hash(chunk.text)
        existing = prior.get(chunk.chunk_id)
        if not force and existing and existing.content_hash == digest:
            kept.append(existing)
        else:
            to_embed.append(chunk)

    if to_embed:
        vectors, model_id = embed_texts([chunk.text for chunk in to_embed])
    else:
        vectors, model_id = [], active_model

    rebuilt = kept + [
        EmbeddingRecord(
            chunk_id=chunk.chunk_id,
            content_hash=content_hash(chunk.text),
            model_id=model_id,
            vector=vector,
        )
        for chunk, vector in zip(to_embed, vectors)
    ]
    rebuilt.sort(key=lambda row: row.chunk_id)
    index = EmbeddingIndex(model_id=model_id if to_embed else active_model, embeddings=rebuilt)
    save_embedding_index(embedding_path, index)
    if to_embed:
        warnings.append(f"Embedded {len(to_embed)} chunk(s) with model {index.model_id}")
    return index, warnings
