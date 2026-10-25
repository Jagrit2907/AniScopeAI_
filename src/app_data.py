"""Cached data access for the Streamlit app.

Caches are keyed on file path + modification time, so the 41k-record catalog is
read once and reloaded only if the file changes. Expensive NLP over reviews
runs once per review-store version, not on every widget interaction.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import settings
from src import data_loader, evidence_store, pipeline, visibility as vis
from src.data_validation import TitleMatcher


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


# cache_resource returns the same object without copying 41k rows on every call.
# Pages must treat the catalog as read-only.
@st.cache_resource(show_spinner="Loading anime catalog…")
def _catalog_cached(data_dir: str, stamp: float) -> data_loader.CatalogLoadResult:
    return data_loader.load_catalog(Path(data_dir))


def catalog_result() -> data_loader.CatalogLoadResult:
    files = data_loader.discover_files(settings.RAW_DATA_DIR)
    stamp = _mtime(files["catalog"]) if files["catalog"] else 0.0
    return _catalog_cached(str(settings.RAW_DATA_DIR), stamp)


def catalog() -> pd.DataFrame | None:
    r = catalog_result()
    return r.df if r.ok else None


@st.cache_resource(show_spinner=False)
def _matcher_cached(stamp: float, n: int) -> TitleMatcher | None:
    df = catalog()
    return TitleMatcher(df) if df is not None else None


def matcher() -> TitleMatcher | None:
    df = catalog()
    if df is None:
        return None
    files = data_loader.discover_files(settings.RAW_DATA_DIR)
    return _matcher_cached(_mtime(files["catalog"]), len(df))


@st.cache_data(show_spinner=False)
def _trends_cached(stamp: float) -> pd.DataFrame:
    return evidence_store.load_trends()


def trends() -> pd.DataFrame:
    return _trends_cached(_mtime(settings.TREND_STORE))


@st.cache_resource(show_spinner="Loading review analysis…")
def _reviews_cached(stamp: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Uses the on-disk analysis cache when it matches the review store; rebuilds otherwise.
    return pipeline.reviews_with_analysis()


def reviews() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(reviews with overall labels, aspect evidence rows)."""
    return _reviews_cached(_mtime(settings.REVIEW_STORE))


@st.cache_resource(show_spinner="Linking 2020 MAL visibility snapshot…")
def _visibility_cached(path: str, stamp: float, n: int) -> tuple[pd.DataFrame, str | None]:
    df = catalog()
    try:
        snap = vis.load_snapshot(Path(path))
        return vis.attach(df, snap), None
    except Exception as exc:  # noqa: BLE001 - shown in Data & Methods
        return pd.DataFrame(), f"Could not read {Path(path).name}: {exc}"


def visibility() -> tuple[pd.DataFrame, str | None]:
    """(frame indexed by anime_id, error). Empty frame when animes.csv is absent."""
    df = catalog()
    path = vis.find_snapshot(settings.RAW_DATA_DIR, settings.VISIBILITY_FILE_NAMES)
    if df is None or path is None:
        return pd.DataFrame(), None
    return _visibility_cached(str(path), _mtime(path), len(df))


def visibility_row(anime_id: str | None) -> pd.Series | None:
    v, _ = visibility()
    if v.empty or anime_id not in v.index:
        return None
    return v.loc[anime_id]


def refresh() -> None:
    _trends_cached.clear()
    _reviews_cached.clear()


def coverage() -> dict:
    t = trends()
    r, _ = reviews()
    return {
        "trend_titles": int(t["anime_id"].nunique()) if not t.empty else 0,
        "trend_obs": int(len(t)),
        "trend_last": None if t.empty else t["date"].max().date(),
        "trend_geos": sorted(t["geo"].dropna().unique().tolist()) if not t.empty else [],
        "review_titles": int(r["anime_id"].nunique()) if not r.empty else 0,
        "reviews": int(len(r)),
        "visibility_titles": int(len(visibility()[0])),
    }


@st.cache_data(show_spinner="Screening titles for mixed-response patterns…", max_entries=16)
def gem_candidates(stamp: float, focus_aspect: str | None, min_reviews: int):
    """Cached Hidden Gems screening (recomputed only when reviews or parameters change)."""
    from src.opportunity_engine import find_candidates
    r, e = reviews()
    return find_candidates(r, e, focus_aspect, min_reviews)


def review_stamp() -> float:
    return _mtime(settings.REVIEW_STORE)
