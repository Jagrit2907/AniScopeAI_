"""Visibility layer from the 2020 MyAnimeList snapshot (Kaggle 'Anime Dataset with Reviews', animes.csv).

What it is: MAL membership counts and popularity ranks scraped around May 2020.
What it is NOT: India-specific, current, or a measure of commercial demand.
Titles released after the crawl are absent ("not in snapshot"), never zero.

Linking: animes.csv ``uid`` is the MyAnimeList anime id, joined to the catalog's
MAL id. Duplicate rows for the same uid are collapsed (the file contains ~3k
exact duplicates).

Peer percentile: a title's member count is ranked against catalog titles of the
same format and release year that are also in the snapshot (falls back to the
same format across all years when fewer than 10 peers exist). It answers
"how visible was this title compared with similar titles", not "how good is it".
Synopsis text is not loaded (copyrighted MAL content not needed for analysis).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

SNAPSHOT_LABEL = "MyAnimeList members, 2020 snapshot (Kaggle, global users)"
MIN_PEERS = 10


def find_snapshot(data_dir: Path, names: list[str]) -> Path | None:
    for n in names:
        if (data_dir / n).exists():
            return data_dir / n
    return None


def load_snapshot(path: Path) -> pd.DataFrame:
    """Return one row per MAL id: mal_id, mal_members, mal_popularity_rank, mal_rank, mal_score_2020."""
    cols = ["uid", "members", "popularity", "ranked", "score", "aired"]
    df = pd.read_csv(path, usecols=lambda c: c in cols, encoding="utf-8")
    missing = {"uid", "members"} - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} lacks required columns: {', '.join(sorted(missing))}")
    df["uid"] = pd.to_numeric(df["uid"], errors="coerce")
    df["members"] = pd.to_numeric(df["members"], errors="coerce")
    df = df.dropna(subset=["uid", "members"])
    # Keep the highest-membership row per id (duplicates are almost all identical).
    df = df.sort_values("members", ascending=False).drop_duplicates("uid")
    return pd.DataFrame({
        "mal_id": df["uid"].astype("int64"),
        "mal_members": df["members"].astype("int64"),
        "mal_popularity_rank": pd.to_numeric(df.get("popularity"), errors="coerce"),
        "mal_rank": pd.to_numeric(df.get("ranked"), errors="coerce"),
        "mal_score_2020": pd.to_numeric(df.get("score"), errors="coerce"),
        "mal_aired": df.get("aired"),
    }).reset_index(drop=True)


def attach(catalog: pd.DataFrame, snap: pd.DataFrame) -> pd.DataFrame:
    """Return a frame indexed by anime_id with snapshot fields and a peer percentile."""
    base = catalog.loc[catalog["mal_id"].notna(), ["anime_id", "mal_id", "type", "year"]].copy()
    base["mal_id"] = base["mal_id"].astype("int64")
    merged = base.merge(snap, on="mal_id", how="inner")
    if merged.empty:
        return merged.set_index("anime_id")
    merged["peer_group"] = merged["type"].fillna("?").astype(str) + " · " + merged["year"].astype("string").fillna("?")
    size = merged.groupby("peer_group")["mal_members"].transform("size")
    pct_year = merged.groupby("peer_group")["mal_members"].rank(pct=True)
    pct_type = merged.groupby(merged["type"].fillna("?"))["mal_members"].rank(pct=True)
    size_type = merged.groupby(merged["type"].fillna("?"))["mal_members"].transform("size")
    use_year = size >= MIN_PEERS
    merged["peer_percentile"] = (pct_year.where(use_year, pct_type) * 100).round(0)
    merged["peer_n"] = size.where(use_year, size_type)
    merged["peer_basis"] = merged["peer_group"].where(use_year, merged["type"].fillna("?").astype(str) + " · all years")
    return merged.drop(columns=["type", "year", "peer_group"]).set_index("anime_id")


def describe(row: pd.Series | None) -> str:
    if row is None:
        return "Not in the 2020 MAL snapshot (released later, or not on MAL) — visibility not measured."
    return (f"{int(row['mal_members']):,} MAL members (2020 snapshot, global) — percentile {int(row['peer_percentile'])} "
            f"among {int(row['peer_n'])} {row['peer_basis']} titles.")
