from __future__ import annotations

import importlib.util
import inspect
import sys
import types
from pathlib import Path
from types import SimpleNamespace

SRC = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "ANDROID_MOVIE_APP"
    / "services"
    / "search"
    / "metadata"
    / "genre_browse.py"
)


def _load():
    metadata = types.ModuleType("metadata")
    tmdb = types.ModuleType("metadata.tmdb_client")
    tmdb.TmdbClient = object
    tmdb.TmdbDiscoverMovie = object
    core = types.ModuleType("torrtux_core")
    filters = types.ModuleType("torrtux_core.filters")
    filters.interleave_by_site = lambda rows: rows
    filters.seed_count = lambda _seeds: 0
    genres = types.ModuleType("torrtux_core.genres")
    genres.genre_search_query = lambda genre_id: genre_id or None
    genres.tmdb_genre_id = lambda _genre_id: 1
    searcher = types.ModuleType("torrtux_core.searcher")
    searcher.SearchOutcome = SimpleNamespace
    searcher.TorrentSearcher = object
    sys.modules["metadata"] = metadata
    sys.modules["metadata.tmdb_client"] = tmdb
    sys.modules["torrtux_core"] = core
    sys.modules["torrtux_core.filters"] = filters
    sys.modules["torrtux_core.genres"] = genres
    sys.modules["torrtux_core.searcher"] = searcher
    spec = importlib.util.spec_from_file_location("genre_browse", SRC)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_keyword_genre_search_reads_genre_keyword_page_limit():
    mod = _load()
    default = inspect.signature(mod.keyword_genre_search).parameters["page_limit"].default
    assert default == mod.GENRE_KEYWORD_PAGE_LIMIT
    captured: dict[str, object] = {}

    class Searcher:
        def search(self, _query, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(results=[], failed_sites=[], indexers_unavailable=False)

    mod.keyword_genre_search(Searcher(), "action")
    assert captured["page_limit"] == mod.GENRE_KEYWORD_PAGE_LIMIT
