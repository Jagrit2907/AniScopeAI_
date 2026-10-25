"""Backend ingest pipeline (no Streamlit): import evidence files and precompute analysis.

Why: sentiment + aspect extraction over tens of thousands of reviews is too slow
to redo on every app start. The pipeline runs it once after an import and stores
the result in data/processed/:

    review_evidence.csv        validated reviews (the evidence store)
    reviews_scored.csv         + overall label per review
    aspect_evidence.csv        one row per (review, aspect, sentence)
    analysis_cache.json        fingerprint of the review store the cache was built from

The app reuses the cache while the fingerprint matches and rebuilds it otherwise.
Run from the command line with ``python scripts/ingest.py --help``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd

from config import settings
from src import evidence_store
from src.data_validation import (REVIEW_FIELD_ALIASES, TREND_FIELD_ALIASES, ImportReport, TitleMatcher, guess_mapping,
                                 parse_google_trends_export, read_csv_bytes, validate_reviews, validate_trends)
from src.review_analysis import review_level, sentiment
from src.theme_extraction import compact_evidence, extract_aspect_evidence

SCORED_FILE = "reviews_scored.csv"
ASPECT_FILE = "aspect_evidence.csv"
CACHE_META = "analysis_cache.json"


def _fingerprint(path: Path) -> dict:
    try:
        st = path.stat()
        return {"size": st.st_size, "mtime": round(st.st_mtime, 3)}
    except OSError:
        return {"size": 0, "mtime": 0}


def cap_per_title(df: pd.DataFrame, cap: int | None) -> pd.DataFrame:
    """Keep at most ``cap`` reviews per title: most helpful first, then longest (more aspect detail)."""
    if not cap or df.empty:
        return df
    ranked = df.assign(_help=df["helpful_count"].fillna(-1), _len=df["text"].str.len())
    ranked = ranked.sort_values(["anime_id", "_help", "_len"], ascending=[True, False, False])
    return ranked.groupby("anime_id", sort=False).head(cap).drop(columns=["_help", "_len"])


def import_reviews_file(path: Path, matcher: TitleMatcher, source: str | None = None, cap: int | None = 30,
                        mapping: dict | None = None) -> tuple[ImportReport, int]:
    frame = read_csv_bytes(path.read_bytes())
    mapping = mapping or guess_mapping(list(frame.columns), REVIEW_FIELD_ALIASES)
    out, rep = validate_reviews(frame, mapping, matcher, path.name, default_source=source)
    if cap:
        before = len(out)
        out = cap_per_title(out, cap)
        if before > len(out):
            rep.notes.append(f"Capped at {cap} reviews per title (most helpful, then longest): kept {len(out):,} of {before:,}.")
            rep.rows_valid = len(out)
    total = evidence_store.save_reviews(out) if len(out) else 0
    evidence_store.log_import(rep)
    return rep, total


QUERY_MAP = settings.PROJECT_ROOT / "data" / "mappings" / "trend_query_map.csv"


def load_query_map(catalog: pd.DataFrame, path: Path | None = None) -> tuple[dict[str, str], list[str]]:
    """Read the curated query → MyAnimeList id map and resolve each to one catalog record.

    Returns ({query: anime_id}, problems). A row whose MAL id matches zero or
    several catalog records is reported and NOT used.
    """
    path = path or QUERY_MAP
    if not path.exists():
        return {}, []
    m = pd.read_csv(path, dtype=str)
    by_mal = catalog.dropna(subset=["mal_id"]).groupby(catalog["mal_id"].dropna().astype("int64"))["anime_id"].agg(list)
    out, problems = {}, []
    for q, mid in zip(m["query"], m["myanimelist_id"]):
        try:
            ids = by_mal.get(int(mid), [])
        except (TypeError, ValueError):
            ids = []
        if len(ids) == 1:
            out[str(q)] = ids[0]
        else:
            problems.append(f"{q}: MAL id {mid} matches {len(ids)} catalog records")
    return out, problems


def import_trends_file(path: Path, matcher: TitleMatcher, default_geo: str | None = None,
                       source: str = "Google Trends export", query_map: dict[str, str] | None = None,
                       ) -> tuple[ImportReport, int, pd.DataFrame]:
    """Validate and store one Trends file. Each file is its own batch (its own 0–100 scale)."""
    data = path.read_bytes()
    native = parse_google_trends_export(data)
    if native is not None:
        frame = native
        mapping = {"date": "date", "value": "raw_value", "query": "query", "geo": "geo"}
    else:
        frame = read_csv_bytes(data)
        mapping = guess_mapping(list(frame.columns), TREND_FIELD_ALIASES)
    out, rep = validate_trends(frame, mapping, matcher, path.name, default_geo=default_geo,
                               source=f"{source} ({path.name})", query_overrides=query_map)
    if len(out):
        out["batch_id"] = path.stem  # the export file defines the comparison scale
    total = evidence_store.save_trends(out) if len(out) else 0
    evidence_store.log_import(rep)
    return rep, total, out


def trend_file_report(path: Path, out: pd.DataFrame, rep: ImportReport, frame_rows: int | None = None) -> dict:
    """Per-file summary for the integration report."""
    raw = parse_google_trends_export(path.read_bytes())
    missing = int(raw["raw_value"].isna().sum() + (raw["raw_value"].astype(str).str.strip() == "").sum()) if raw is not None else None
    return {"file": path.name, "titles": sorted(out["query"].unique().tolist()) if len(out) else [],
            "date_min": None if out.empty else str(out["date"].min()), "date_max": None if out.empty else str(out["date"].max()),
            "rows_read": rep.rows_read, "valid": rep.rows_valid, "missing_values": missing,
            "zeros": int((out["value"] == 0).sum()) if len(out) else 0, "below_one": int(out["below_one"].sum()) if len(out) else 0,
            "rejected": rep.rejected, "unmatched": rep.unmatched_titles, "ambiguous": list(rep.ambiguous_titles)}


# --------------------------------------------------------------------------
# MyAnimeList ↔ catalog mapping audit
# --------------------------------------------------------------------------
def mal_mapping_audit(catalog: pd.DataFrame, animes_path: Path) -> dict:
    """Check how animes.csv ``uid`` relates to the catalog's MyAnimeList ids.

    The ids are only treated as interchangeable if (a) most uids resolve to
    exactly one catalog record and (b) titles agree for those records.
    """
    from src.data_loader import normalize_title
    a = pd.read_csv(animes_path, usecols=["uid", "title"]).drop_duplicates("uid")
    cat = catalog.dropna(subset=["mal_id"]).assign(mal=lambda d: d["mal_id"].astype("int64"))
    counts = cat["mal"].value_counts()
    a["catalog_records"] = a["uid"].map(counts).fillna(0).astype(int)
    one = a[a["catalog_records"] == 1].merge(cat[["mal", "title", "synonyms"]], left_on="uid", right_on="mal",
                                             suffixes=("_mal", "_cat"))
    def agree(r):
        names = {normalize_title(r["title_cat"])} | {normalize_title(x) for x in r["synonyms"]}
        return normalize_title(r["title_mal"]) in names
    one["title_agrees"] = one.apply(agree, axis=1)
    return {"animes_unique_uids": int(len(a)),
            "uids_with_one_catalog_record": int((a["catalog_records"] == 1).sum()),
            "uids_with_several_catalog_records": int((a["catalog_records"] > 1).sum()),
            "uids_not_in_catalog": int((a["catalog_records"] == 0).sum()),
            "title_agreement_rate": round(float(one["title_agrees"].mean()), 4) if len(one) else None,
            "title_disagreements_sample": one.loc[~one["title_agrees"], ["uid", "title_mal", "title_cat"]].head(8).values.tolist()}


# --------------------------------------------------------------------------
# Large review files (e.g. Kaggle reviews.csv, ~650 MB) — streamed in chunks
# --------------------------------------------------------------------------
def import_reviews_chunked(path: Path, catalog: pd.DataFrame, animes_path: Path | None, source: str,
                           cap: int | None = 20, min_reviews: int = 1, chunksize: int = 5_000,
                           progress: Callable[[str, int], None] | None = None) -> dict:
    """Stream a large review CSV (e.g. Kaggle reviews.csv, ~650 MB) in two passes.

    Pass 1 reads only ids and text lengths (small memory) and decides which reviews
    to keep: per title, the ``cap`` longest texts (the file has no helpfulness field);
    titles with fewer than ``min_reviews`` usable reviews are skipped.
    Pass 2 streams again and appends only the kept rows to the review store.

    Linking: ``anime_uid`` is a MyAnimeList id. It is compared with animes.csv
    ``uid`` (same source) and mapped to the catalog via the catalog's MAL id,
    accepting only ids that resolve to exactly one catalog record.
    The ``profile`` (username) column is never read.
    """
    from src.data_validation import REVIEW_COLUMNS, clean_review_text, now_iso
    cat = catalog.dropna(subset=["mal_id"]).assign(mal=lambda d: d["mal_id"].astype("int64"))
    counts = cat["mal"].value_counts()
    mal_to_id = dict(zip(cat["mal"], cat["anime_id"]))
    animes_uids = None
    if animes_path and animes_path.exists():
        animes_uids = set(pd.to_numeric(pd.read_csv(animes_path, usecols=["uid"])["uid"], errors="coerce").dropna().astype("int64"))
    cols = {"uid", "anime_uid", "text", "score", "link"}

    def chunks():
        return pd.read_csv(path, usecols=lambda c: c in cols, dtype=str, chunksize=chunksize,
                           on_bad_lines="skip", encoding="utf-8", encoding_errors="replace")

    stats = {"rows_read": 0, "unparseable_anime_uid": 0, "uid_in_animes_csv": 0, "uid_not_in_animes_csv": 0,
             "uid_not_in_catalog": 0, "uid_ambiguous_in_catalog": 0, "empty_or_short_text": 0,
             "duplicate_review_ids": 0, "linked_usable": 0}
    candidates: dict[str, list[tuple[int, str]]] = {}
    seen: set[str] = set()
    for chunk in chunks():                                   # ---- pass 1
        stats["rows_read"] += len(chunk)
        mal = pd.to_numeric(chunk["anime_uid"], errors="coerce")
        stats["unparseable_anime_uid"] += int(mal.isna().sum())
        chunk = chunk.assign(mal=mal).dropna(subset=["mal"])
        chunk["mal"] = chunk["mal"].astype("int64")
        if animes_uids is not None:
            in_a = chunk["mal"].isin(animes_uids)
            stats["uid_in_animes_csv"] += int(in_a.sum())
            stats["uid_not_in_animes_csv"] += int((~in_a).sum())
        n = chunk["mal"].map(counts).fillna(0)
        stats["uid_not_in_catalog"] += int((n == 0).sum())
        stats["uid_ambiguous_in_catalog"] += int((n > 1).sum())
        chunk = chunk[n == 1]
        lengths = chunk["text"].map(lambda t: len(clean_review_text(t) or ""))
        short = lengths < 40
        stats["empty_or_short_text"] += int(short.sum())
        for uid, m, ln in zip(chunk["uid"][~short], chunk["mal"][~short], lengths[~short]):
            if uid in seen:
                stats["duplicate_review_ids"] += 1
                continue
            seen.add(uid)
            stats["linked_usable"] += 1
            candidates.setdefault(mal_to_id[m], []).append((ln, uid))
        if progress:
            progress("scan", stats["rows_read"])

    keep_uids: set[str] = set()
    titles_kept = 0
    for aid, items in candidates.items():
        if len(items) < min_reviews:
            continue
        titles_kept += 1
        items.sort(reverse=True)
        keep_uids.update(uid for _, uid in (items[:cap] if cap else items))

    settings.REVIEW_STORE.parent.mkdir(parents=True, exist_ok=True)
    existing = evidence_store.load_reviews()
    written = 0
    tmp = settings.REVIEW_STORE.with_suffix(".tmp.csv")
    existing.to_csv(tmp, index=False, encoding="utf-8", columns=REVIEW_COLUMNS)
    stamp = now_iso()
    done: set[str] = set()
    read2 = 0
    for chunk in chunks():                                   # ---- pass 2
        read2 += len(chunk)
        chunk = chunk[chunk["uid"].isin(keep_uids) & ~chunk["uid"].isin(done)]
        if chunk.empty:
            if progress:
                progress("write", read2)
            continue
        done.update(chunk["uid"])
        mal = pd.to_numeric(chunk["anime_uid"], errors="coerce").astype("int64")
        score = pd.to_numeric(chunk["score"], errors="coerce")
        link = chunk["link"].where(chunk["link"].fillna("").str.startswith("http"))
        out = pd.DataFrame({"review_id": source + ":" + chunk["uid"].astype(str), "anime_id": mal.map(mal_to_id),
                            "source": source, "source_url": link, "date": None,
                            "text": chunk["text"].map(clean_review_text), "score_10": score.where((score >= 0) & (score <= 10)),
                            "language": None, "geography": None, "helpful_count": None, "imported_at": stamp})
        out = out[~out["review_id"].isin(existing["review_id"])]
        out.to_csv(tmp, mode="a", header=False, index=False, encoding="utf-8", columns=REVIEW_COLUMNS)
        written += len(out)
        if progress:
            progress("write", read2)
    tmp.replace(settings.REVIEW_STORE)

    with_uid = stats["rows_read"] - stats["unparseable_anime_uid"]
    stats.update({
        "titles_with_usable_reviews": len(candidates), "titles_kept": titles_kept, "cap_per_title": cap,
        "min_reviews_per_title": min_reviews, "reviews_written": written, "store_total": len(existing) + written,
        "match_rate_vs_animes_csv": round(stats["uid_in_animes_csv"] / with_uid, 4) if animes_uids is not None and with_uid else None,
        "match_rate_vs_catalog": round((with_uid - stats["uid_not_in_catalog"] - stats["uid_ambiguous_in_catalog"]) / with_uid, 4) if with_uid else None,
        "note": "No reviewer location in the file: international MyAnimeList reviews, not Indian audience evidence."})
    evidence_store.log_import({
        "kind": "review", "file": path.name, "rows_read": stats["rows_read"], "rows_valid": written,
        "rejected": {"anime_uid not in catalog": stats["uid_not_in_catalog"],
                     "anime_uid matches several catalog records": stats["uid_ambiguous_in_catalog"],
                     "empty or short text": stats["empty_or_short_text"],
                     "unparseable anime_uid": stats["unparseable_anime_uid"]},
        "duplicates_dropped": stats["duplicate_review_ids"],
        "notes": [stats["note"], f"Kept up to {cap} longest reviews per title; titles with < {min_reviews} usable reviews skipped."],
        "imported_at": now_iso()})
    return stats


# --------------------------------------------------------------------------
# Analysis cache (sentiment + aspects), rebuilt only when the review store changes
# --------------------------------------------------------------------------
def build_analysis_cache(progress: Callable[[float, str], None] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score every stored review and extract aspect evidence; write the cache files."""
    raw = evidence_store.load_reviews()
    out_dir = settings.PROCESSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    if raw.empty:
        scored = raw.assign(overall=pd.Series(dtype=str), text_compound=pd.Series(dtype=float), overall_basis="")
        evidence = compact_evidence(extract_aspect_evidence(raw, sentiment))
    else:
        chunks_s, chunks_e = [], []
        n = len(raw)
        step = max(1, n // 50)
        for start in range(0, n, step):
            part = review_level(raw.iloc[start:start + step])
            chunks_s.append(part)
            chunks_e.append(compact_evidence(extract_aspect_evidence(part, sentiment)))
            if progress:
                progress(min(1.0, (start + step) / n), f"Analysed {min(n, start + step):,} of {n:,} reviews")
        scored = pd.concat(chunks_s, ignore_index=True)
        evidence = pd.concat(chunks_e, ignore_index=True)
    # Store only the labels; review text lives once, in the review store.
    scored[["review_id", "overall", "overall_basis", "text_compound"]].to_csv(out_dir / SCORED_FILE, index=False, encoding="utf-8")
    evidence.to_csv(out_dir / ASPECT_FILE, index=False, encoding="utf-8")
    (out_dir / CACHE_META).write_text(json.dumps({"review_store": _fingerprint(settings.REVIEW_STORE),
                                                  "reviews": len(scored), "aspect_rows": len(evidence)}), encoding="utf-8")
    return scored, evidence


def load_analysis_cache() -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Return the cached analysis if it was built from the current review store, else None."""
    meta_path = settings.PROCESSED_DIR / CACHE_META
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if meta.get("review_store") != _fingerprint(settings.REVIEW_STORE):
        return None
    try:
        labels = pd.read_csv(settings.PROCESSED_DIR / SCORED_FILE, dtype={"review_id": str})
        evidence = pd.read_csv(settings.PROCESSED_DIR / ASPECT_FILE, dtype={"anime_id": str, "review_id": str})
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return None
    scored = evidence_store.load_reviews().merge(labels, on="review_id", how="left")
    for col in ("score_10", "helpful_count", "text_compound"):
        if col in scored:
            scored[col] = pd.to_numeric(scored[col], errors="coerce")
    for frame, cols in ((scored, ("source_url", "date", "geography", "language")), (evidence, ("source_url", "date"))):
        for col in cols:
            if col in frame:
                frame[col] = frame[col].astype(object).where(frame[col].notna(), None)
    return scored, evidence


def reviews_with_analysis(progress=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    cached = load_analysis_cache()
    return cached if cached is not None else build_analysis_cache(progress)
