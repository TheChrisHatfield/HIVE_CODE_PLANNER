"""Netflix-style genre browse: TMDB discover popular titles, then torrent search per title."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from metadata.tmdb_client import TmdbClient, TmdbDiscoverMovie
from torrtux_core.filters import interleave_by_site, seed_count
from torrtux_core.genres import genre_search_query, tmdb_genre_id
from torrtux_core.searcher import SearchOutcome, TorrentSearcher

logger = logging.getLogger(__name__)
_discover_rotation_lock = threading.Lock()
_discover_rotation_counts: dict[str, int] = {}

GENRE_TITLE_SEARCH_LIMIT = 28
GENRE_TITLE_FANOUT_TIMEOUT_SEC = 45
GENRE_RELEASES_PER_TITLE = 3
# Walk several discover pages per fetch (not a single popularity page).
GENRE_DISCOVER_MAX_PAGES = 4
# How many TMDB titles to torrent-search into the genre pool (was 8).
TMDB_ENRICH_TITLE_LIMIT = 24
# Discover page rotation window (each pull-to-refresh / rebuild advances one page).
DISCOVER_PAGE_WINDOW = 8
# Shared rank band so TMDB popularity order does not always beat indexer rows.
GENRE_RANK_BASE = 24
GENRE_KEYWORD_PAGE_LIMIT = 3
# Broad indexer fan-out (primary pool driver — all movie sites via keyword search).
BROAD_KEYWORD_PAGE_LIMIT = 3
BROAD_KEYWORD_LIMIT = 250
BROAD_1337X_PAGE_LIMIT = 2
BROAD_1337X_LIMIT = 120


def discover_page_offset(genre_id: str, *, rotate: bool, now: float | None = None) -> int:
    """Advance TMDB discover start page on each rebuild (not a 30-minute time bucket)."""
    del now  # kept so callers/tests can pass a clock without changing the signature
    if not rotate:
        return 1
    key = genre_id.strip().lower()
    if not key:
        return 1
    with _discover_rotation_lock:
        count = _discover_rotation_counts.get(key, 0) + 1
        _discover_rotation_counts[key] = count
    # Cold load stays on page 1; the first refresh starts at page 2.
    return (count % DISCOVER_PAGE_WINDOW) + 1


def _attach_discover_metadata(row: dict, rank: int, movie: TmdbDiscoverMovie) -> None:
    row["_genre_rank"] = GENRE_RANK_BASE + rank
    if movie.poster_url and not row.get("poster_url"):
        row["poster_url"] = movie.poster_url
    if movie.overview and not row.get("overview"):
        row["overview"] = movie.overview


def _discover_genre_movies(
    tmdb: TmdbClient,
    tmdb_id: int,
    *,
    title_limit: int,
    page_offset: int = 1,
) -> list[TmdbDiscoverMovie]:
    """Fetch multiple TMDB discover pages for broader unique title coverage."""
    movies: list[TmdbDiscoverMovie] = []
    seen_ids: set[int] = set()
    page = max(page_offset, 1)
    while len(movies) < title_limit and page < page_offset + GENRE_DISCOVER_MAX_PAGES:
        batch = tmdb.discover_movies(tmdb_id, page=page, limit=20)
        if not batch:
            break
        added = 0
        for movie in batch:
            if movie.tmdb_id in seen_ids:
                continue
            seen_ids.add(movie.tmdb_id)
            movies.append(movie)
            added += 1
            if len(movies) >= title_limit:
                break
        if added == 0:
            break
        page += 1
    return movies


def _sort_genre_rows(rows: list[dict]) -> list[dict]:
    def sort_key(row: dict) -> tuple:
        rank = int(row.get("_genre_rank", 9999))
        seeds = seed_count(row.get("seeds", "-")) or 0
        return (rank, -seeds)

    return sorted(rows, key=sort_key)


def curated_genre_search(
    searcher: TorrentSearcher,
    genre_id: str,
    tmdb: TmdbClient,
    *,
    sites: list | None = None,
    movie_profile: bool = True,
    min_seeds: int | None = None,
    max_seeds: int | None = None,
    max_size: str | None = None,
    limit: int | None = None,
    title_limit: int = GENRE_TITLE_SEARCH_LIMIT,
    discover_page_offset: int = 1,
) -> SearchOutcome | None:
    """
    Discover popular movies in genre via TMDB, search torrents per title across indexers.
    Returns None when TMDB discover cannot run (caller should keyword-fallback).
    """
    normalized = genre_id.strip().lower()
    tmdb_id = tmdb_genre_id(normalized)
    if not tmdb_id or not tmdb.configured:
        return None

    movies = _discover_genre_movies(
        tmdb,
        tmdb_id,
        title_limit=title_limit,
        page_offset=discover_page_offset,
    )
    if not movies:
        return None

    all_results: list[dict] = []
    failed_sites: list[str] = []

    with ThreadPoolExecutor(max_workers=min(6, len(movies))) as pool:
        futures = {
            pool.submit(
                searcher.search,
                movie.title,
                sites=sites,
                movie_profile=movie_profile,
                page_limit=1,
                parallel=True,
                min_seeds=min_seeds,
                max_seeds=max_seeds,
                max_size=max_size,
                limit=GENRE_RELEASES_PER_TITLE,
            ): (rank, movie)
            for rank, movie in enumerate(movies)
        }
        try:
            for future in as_completed(futures, timeout=GENRE_TITLE_FANOUT_TIMEOUT_SEC):
                rank, movie = futures[future]
                try:
                    outcome = future.result()
                    for row in outcome.results:
                        _attach_discover_metadata(row, rank, movie)
                    all_results.extend(outcome.results)
                    failed_sites.extend(outcome.failed_sites)
                except Exception as exc:
                    logger.warning("genre title search failed %s: %s", movie.title, exc)
        except TimeoutError:
            pending = [movie.title for future, (_, movie) in futures.items() if not future.done()]
            for future in futures:
                future.cancel()
            if pending:
                logger.warning(
                    "genre curated search timed out after %ss; skipped %s",
                    GENRE_TITLE_FANOUT_TIMEOUT_SEC,
                    ", ".join(pending[:5]),
                )

    if not all_results:
        return None

    sorted_results = _sort_genre_rows(all_results)
    if limit is not None:
        sorted_results = sorted_results[:limit]

    queried_names = {site.name for site in (sites or [])} if sites else set()
    all_sources_failed = bool(queried_names) and not sorted_results
    return SearchOutcome(
        results=sorted_results,
        failed_sites=list(dict.fromkeys(failed_sites)),
        all_sources_failed=all_sources_failed,
    )


def broad_indexer_genre_pool(
    searcher: TorrentSearcher,
    genre_id: str,
    *,
    sites: list | None = None,
    movie_profile: bool = True,
    page_limit: int | None = None,
    parallel: bool = True,
    min_seeds: int | None = None,
    max_seeds: int | None = None,
    max_size: str | None = None,
) -> SearchOutcome:
    """
    Primary genre pool: fan out across all movie indexers via keyword search,
    plus 1337x genre browse when the genre slug is supported there.
    """
    normalized = genre_id.strip().lower()
    outcomes: list[SearchOutcome] = []
    keyword_pages = max(1, min(page_limit or BROAD_KEYWORD_PAGE_LIMIT, 10))
    x1337_pages = max(1, min(page_limit or BROAD_1337X_PAGE_LIMIT, 10))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            "keyword": pool.submit(
                keyword_genre_search,
                searcher,
                normalized,
                sites=sites,
                movie_profile=movie_profile,
                page_limit=keyword_pages,
                parallel=parallel,
                min_seeds=min_seeds,
                max_seeds=max_seeds,
                max_size=max_size,
                limit=BROAD_KEYWORD_LIMIT,
            ),
            "1337x": pool.submit(
                searcher.browse_1337x_genre,
                normalized,
                movie_profile=movie_profile,
                page_limit=x1337_pages,
                min_seeds=min_seeds,
                max_seeds=max_seeds,
                max_size=max_size,
                limit=BROAD_1337X_LIMIT,
            ),
        }
        for name, future in futures.items():
            try:
                outcomes.append(future.result())
            except Exception as exc:
                logger.warning("broad indexer genre %s failed: %s", name, exc)

    all_results: list[dict] = []
    failed_sites: list[str] = []
    indexers_unavailable = False
    for outcome in outcomes:
        all_results.extend(outcome.results)
        failed_sites.extend(outcome.failed_sites)
        if outcome.indexers_unavailable:
            indexers_unavailable = True

    if not all_results and indexers_unavailable:
        return SearchOutcome([], failed_sites, indexers_unavailable=True)

    all_results = interleave_by_site(all_results)
    for index, row in enumerate(all_results):
        if row.get("_genre_rank") is None:
            row["_genre_rank"] = GENRE_RANK_BASE + (index % TMDB_ENRICH_TITLE_LIMIT)

    return SearchOutcome(
        results=all_results,
        failed_sites=list(dict.fromkeys(failed_sites)),
        all_sources_failed=not all_results and bool(failed_sites),
    )


def keyword_genre_search(
    searcher: TorrentSearcher,
    genre_id: str,
    *,
    sites: list | None = None,
    movie_profile: bool = True,
    page_limit: int = GENRE_KEYWORD_PAGE_LIMIT,
    parallel: bool = True,
    min_seeds: int | None = None,
    max_seeds: int | None = None,
    max_size: str | None = None,
    limit: int | None = None,
) -> SearchOutcome:
    normalized = genre_id.strip().lower()
    query = genre_search_query(normalized)
    if not query:
        return SearchOutcome([], [], indexers_unavailable=True)
    return searcher.search(
        query,
        sites=sites,
        movie_profile=movie_profile,
        page_limit=page_limit,
        parallel=parallel,
        min_seeds=min_seeds,
        max_seeds=max_seeds,
        max_size=max_size,
        limit=limit,
    )
