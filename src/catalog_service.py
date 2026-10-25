"""Search and filtering over the full catalog (all records, nothing pre-trimmed)."""
from __future__ import annotations

import re

import pandas as pd

from src.data_loader import normalize_title


def search(df: pd.DataFrame, query: str, limit: int = 50) -> pd.DataFrame:
    """Case-insensitive search across titles and alternate titles.

    Ranking: exact title match, then title prefix, then alternate-title hits.
    """
    q = (query or "").strip().lower()
    if not q:
        return df.head(0)
    mask = df["search_text"].str.contains(re.escape(q), regex=True, na=False)
    hits = df[mask]
    if hits.empty:
        return hits
    qn = normalize_title(q)
    rank = pd.Series(3, index=hits.index)
    rank[hits["title_norm"].str.startswith(qn)] = 1
    rank[hits["title_norm"] == qn] = 0
    rank[(rank == 3) & hits["title"].str.lower().str.contains(re.escape(q), regex=True)] = 2
    order = hits.assign(_rank=rank, _eps=hits["episodes"].fillna(0)).sort_values(
        ["_rank", "_eps"], ascending=[True, False])
    return order.drop(columns=["_rank", "_eps"]).head(limit)


def filter_catalog(df: pd.DataFrame, types: list[str] | None = None, statuses: list[str] | None = None,
                   year_range: tuple[int, int] | None = None, tags: list[str] | None = None,
                   include_unknown_year: bool = True) -> pd.DataFrame:
    out = df
    if types:
        out = out[out["type"].isin(types)]
    if statuses:
        out = out[out["status"].isin(statuses)]
    if year_range:
        lo, hi = year_range
        in_range = out["year"].between(lo, hi)
        out = out[in_range.fillna(False) | (out["year"].isna() & include_unknown_year)]
    if tags:
        wanted = set(t.lower() for t in tags)
        out = out[out["tags"].map(lambda ts: wanted.issubset({t.lower() for t in ts}))]
    return out


def top_tags(df: pd.DataFrame, n: int = 60) -> list[str]:
    return df["tags"].explode().dropna().value_counts().head(n).index.tolist()


def label(row: pd.Series) -> str:
    """Human-readable, disambiguating label: Title (TYPE, YEAR)."""
    bits = [b for b in (row.get("type"), row.get("year")) if pd.notna(b)]
    return f"{row['title']} ({', '.join(str(b) for b in bits)})" if bits else str(row["title"])


def get_record(df: pd.DataFrame, anime_id: str | None) -> pd.Series | None:
    if not anime_id:
        return None
    hit = df[df["anime_id"] == anime_id]
    return None if hit.empty else hit.iloc[0]
