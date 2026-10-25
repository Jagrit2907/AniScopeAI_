"""Cached access to the existing AniScope data layer for the web server.

Same loaders, stores and analysis as the Streamlit app (src/), cached by file
modification time so the 41k catalog and the review analysis load once and
reload only when the underlying files change. Nothing here re-implements
analytics; it only calls src/.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd

from config import settings
from src import data_loader, evidence_store, pipeline, visibility as vis
from src.data_validation import TitleMatcher

_lock = threading.RLock()
_cache: dict[str, tuple[object, object]] = {}


def _mtime(path: Path | None) -> float:
    try:
        return path.stat().st_mtime if path else 0.0
    except OSError:
        return 0.0


def _cached(key: str, stamp, build):
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
        value = build()
        _cache[key] = (stamp, value)
        return value


def catalog_result() -> data_loader.CatalogLoadResult:
    files = data_loader.discover_files(settings.RAW_DATA_DIR)
    stamp = (str(settings.RAW_DATA_DIR), _mtime(files["catalog"]))
    return _cached("catalog", stamp, lambda: data_loader.load_catalog(settings.RAW_DATA_DIR))


def catalog() -> pd.DataFrame | None:
    r = catalog_result()
    return r.df if r.ok else None


def catalog_index() -> pd.DataFrame | None:
    df = catalog()
    if df is None:
        return None
    return _cached("catalog_index", id(df), lambda: df.set_index("anime_id", drop=False))


def matcher() -> TitleMatcher | None:
    df = catalog()
    return None if df is None else _cached("matcher", id(df), lambda: TitleMatcher(df))


def trends() -> pd.DataFrame:
    return _cached("trends", _mtime(settings.TREND_STORE), evidence_store.load_trends)


def reviews() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(reviews with overall labels, compact aspect evidence) — the pipeline's on-disk cache."""
    return _cached("reviews", _mtime(settings.REVIEW_STORE), pipeline.reviews_with_analysis)


def visibility() -> pd.DataFrame:
    df = catalog()
    path = vis.find_snapshot(settings.RAW_DATA_DIR, settings.VISIBILITY_FILE_NAMES)
    if df is None or path is None:
        return pd.DataFrame()

    def build():
        try:
            return vis.attach(df, vis.load_snapshot(path))
        except Exception:  # noqa: BLE001 - reported as "not measured"
            return pd.DataFrame()
    return _cached("visibility", (_mtime(path), id(df)), build)


def visibility_row(anime_id: str) -> pd.Series | None:
    v = visibility()
    return None if v.empty or anime_id not in v.index else v.loc[anime_id]


def gem_candidates(focus_aspect: str | None, min_reviews: int):
    from src.opportunity_engine import find_candidates
    r, e = reviews()
    key = f"gems:{focus_aspect}:{min_reviews}"
    return _cached(key, _mtime(settings.REVIEW_STORE), lambda: find_candidates(r, e, focus_aspect, min_reviews))


def invalidate() -> None:
    with _lock:
        for k in [k for k in _cache if k in ("trends", "reviews") or k.startswith("gems:")]:
            _cache.pop(k, None)
