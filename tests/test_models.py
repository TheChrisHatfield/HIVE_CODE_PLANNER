from __future__ import annotations

from hive_planner.emitter import keyword_score
from hive_planner.models import ChunkRecord, NormalizeResult


def test_chunk_null_keywords_join_in_emitter():
    chunk = ChunkRecord("c1", "d1", "Intro", "pipeline text", keywords=None)  # type: ignore[arg-type]
    assert chunk.keywords == []
    assert keyword_score(chunk, ["pipeline"]) == 1


def test_chunk_string_keywords_are_one_term_not_characters():
    chunk = ChunkRecord("c1", "d1", "h", "body", keywords="compiler")  # type: ignore[arg-type]
    assert chunk.keywords == ["compiler"]
    assert keyword_score(chunk, ["compiler"]) == 1


def test_chunk_page_coerces_numeric_string_and_rejects_bool():
    assert ChunkRecord("c", "d", "h", "t", page="12").page == 12
    assert ChunkRecord("c", "d", "h", "t", page=True).page is None  # type: ignore[arg-type]


def test_normalize_result_none_extra_metadata_is_empty_dict():
    result = NormalizeResult("body", "raw", "title", extra_metadata=None)  # type: ignore[arg-type]
    result.extra_metadata["format"] = "txt"
    assert result.extra_metadata == {"format": "txt"}
