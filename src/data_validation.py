"""Import and validation of trend observations and review evidence.

Kept separate from the UI. Each importer returns the valid rows plus a report
that lists every reason a row was rejected, so data-quality problems are never
hidden.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from src.data_loader import normalize_title

TREND_COLUMNS = ["anime_id", "query", "geo", "date", "value", "below_one",
                 "source", "batch_id", "imported_at"]
REVIEW_COLUMNS = ["review_id", "anime_id", "source", "source_url", "date", "text",
                  "score_10", "language", "geography", "helpful_count", "imported_at"]

TREND_FIELD_ALIASES = {
    "date": ["date", "observation_date", "week", "day", "month", "time", "week_start", "period_start"],
    "value": ["value", "normalized_value", "interest", "index", "search_interest", "trend_value", "score"],
    "query": ["query", "query_or_topic", "term", "keyword", "search_term", "title", "anime_title"],
    "anime_id": ["anime_id", "aniscope_catalog_id", "catalog_id", "aniscope_id"],
    "geo": ["geo", "geography", "region", "country", "market", "location"],
    "source": ["source", "data_source", "provider"],
}
REVIEW_FIELD_ALIASES = {
    "text": ["text", "review_text_or_permitted_excerpt", "review", "review_text", "body", "content", "comment"],
    "anime_id": ["anime_id", "aniscope_catalog_id", "catalog_id", "aniscope_id"],
    "title": ["title", "anime_title", "anime", "media_title"],
    "mal_id": ["mal_id", "anime_uid", "idmal", "myanimelist_id"],
    "anilist_id": ["anilist_id", "media_id", "mediaid"],
    "source": ["source", "platform", "site", "data_source"],
    "source_url": ["source_url", "url", "link", "review_url", "site_url"],
    "aspect_scores": ["scores", "aspect_scores", "sub_scores"],
    "date": ["date", "review_date", "created_at", "createdat", "posted", "timestamp"],
    "score": ["score", "rating", "review_score", "user_score"],
    "language": ["language", "language_if_known", "lang"],
    "geography": ["geography", "region_if_supported", "geo", "country", "region", "location"],
    "helpful_count": ["helpful_count", "helpful", "upvotes", "rating_amount", "reactions"],
    "review_id": ["review_id", "source_review_id", "id", "uid"],
}


@dataclass
class ImportReport:
    kind: str
    file_name: str
    rows_read: int = 0
    rows_valid: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    unmatched_titles: list[str] = field(default_factory=list)
    ambiguous_titles: dict[str, list[str]] = field(default_factory=dict)
    duplicates_dropped: int = 0
    notes: list[str] = field(default_factory=list)

    def reject(self, reason: str, n: int = 1) -> None:
        if n:
            self.rejected[reason] = self.rejected.get(reason, 0) + int(n)

    @property
    def rows_rejected(self) -> int:
        return sum(self.rejected.values())

    def to_dict(self) -> dict:
        return {"kind": self.kind, "file": self.file_name, "rows_read": self.rows_read,
                "rows_valid": self.rows_valid, "rejected": self.rejected,
                "unmatched_titles": self.unmatched_titles[:50],
                "ambiguous_titles": {k: v[:5] for k, v in list(self.ambiguous_titles.items())[:50]},
                "duplicates_dropped": self.duplicates_dropped, "notes": self.notes,
                "imported_at": now_iso()}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def guess_mapping(columns: list[str], aliases: dict[str, list[str]]) -> dict[str, str | None]:
    norm = {re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_"): c for c in columns}
    out: dict[str, str | None] = {}
    for target, names in aliases.items():
        out[target] = next((norm[n] for n in names if n in norm), None)
    return out


# --------------------------------------------------------------------------
# Title matching
# --------------------------------------------------------------------------
class TitleMatcher:
    """Exact matching of a free-text title to catalog ids via titles + synonyms.

    Only exact normalised matches are accepted. If a string matches several
    catalog records (e.g. a franchise name used by many seasons) it is reported
    as ambiguous and the user must choose; it is never guessed.
    """

    def __init__(self, catalog: pd.DataFrame):
        index: dict[str, set[str]] = {}
        primary: dict[str, set[str]] = {}
        for aid, title, syns in zip(catalog["anime_id"], catalog["title"], catalog["synonyms"]):
            key = normalize_title(title)
            primary.setdefault(key, set()).add(aid)
            index.setdefault(key, set()).add(aid)
            for s in syns:
                index.setdefault(normalize_title(s), set()).add(aid)
        self._primary = primary
        self._index = index
        self._mal = dict(zip(catalog["mal_id"].dropna().astype(int), catalog.loc[catalog["mal_id"].notna(), "anime_id"]))
        self._al = dict(zip(catalog["anilist_id"].dropna().astype(int), catalog.loc[catalog["anilist_id"].notna(), "anime_id"]))

    def match(self, text: str) -> tuple[str | None, list[str]]:
        key = normalize_title(text)
        if not key:
            return None, []
        hits = self._primary.get(key) or self._index.get(key) or set()
        if len(hits) == 1:
            return next(iter(hits)), []
        return None, sorted(hits)

    def by_mal(self, mal_id) -> str | None:
        try:
            return self._mal.get(int(mal_id))
        except (TypeError, ValueError):
            return None

    def by_anilist(self, anilist_id) -> str | None:
        try:
            return self._al.get(int(anilist_id))
        except (TypeError, ValueError):
            return None


# --------------------------------------------------------------------------
# Trend observations
# --------------------------------------------------------------------------
GT_HEADER = re.compile(r"^(?P<query>.+?):\s*\((?P<geo>[^)]+)\)\s*$")


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
    raise ValueError("Could not decode the file")


def parse_google_trends_export(data: bytes) -> pd.DataFrame | None:
    """Parse the native Google Trends 'Interest over time' CSV.

    That file starts with a 'Category: ...' line and a blank line, then a header
    like ``Week,Frieren: (India),Naruto: (India)``. Returns a long frame with
    columns date, query, geo, raw_value — or None if the file is not in that format.
    """
    text = data.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    # Two layouts are accepted:
    #   Week,Frieren: (India),...   -> geography read from each header
    #   "Time","Frieren",...        -> headers are terms only; geography is NOT in the file (geo = None)
    header_idx = None
    for i, line in enumerate(lines[:6]):
        cells = next(csv.reader([line]), [])
        cells = [c.strip() for c in cells]
        if len(cells) >= 2 and cells[0].lower() in {"week", "day", "month", "time", "date"} and \
                all(c and not _is_number(c) for c in cells[1:]):
            header_idx = i
            break
    if header_idx is None:
        return None
    wide = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])), dtype=str)
    date_col = wide.columns[0]
    long = wide.melt(id_vars=[date_col], var_name="header", value_name="raw_value")
    parts = long["header"].str.extract(GT_HEADER)
    has_geo = parts["query"].notna()
    return pd.DataFrame({"date": long[date_col],
                         "query": parts["query"].where(has_geo, long["header"]).str.strip(),
                         "geo": parts["geo"].where(has_geo).str.strip(),
                         "raw_value": long["raw_value"]})


def _is_number(text: str) -> bool:
    try:
        float(text.replace("<", ""))
        return True
    except ValueError:
        return False


def validate_trends(frame: pd.DataFrame, mapping: dict[str, str | None], matcher: TitleMatcher,
                    file_name: str, default_geo: str | None = None, source: str = "Google Trends export",
                    query_overrides: dict[str, str] | None = None) -> tuple[pd.DataFrame, ImportReport]:
    """Validate a trend frame. ``mapping`` maps date/value/query/anime_id/geo/source to columns.

    ``query_overrides`` lets the user resolve unmatched/ambiguous queries to a catalog id.
    """
    rep = ImportReport("trend", file_name, rows_read=len(frame))
    if frame.empty:
        rep.notes.append("File contains no data rows.")
        return pd.DataFrame(columns=TREND_COLUMNS), rep
    for req in ("date", "value"):
        if not mapping.get(req):
            rep.reject(f"no '{req}' column mapped", len(frame))
            return pd.DataFrame(columns=TREND_COLUMNS), rep
    if not mapping.get("query") and not mapping.get("anime_id"):
        rep.reject("no title/query or anime_id column mapped", len(frame))
        return pd.DataFrame(columns=TREND_COLUMNS), rep

    overrides = query_overrides or {}
    df = pd.DataFrame(index=frame.index)
    df["date"] = pd.to_datetime(frame[mapping["date"]].astype(str).str.strip(), errors="coerce", format="mixed")
    raw_val = frame[mapping["value"]].astype(str).str.strip()
    df["below_one"] = raw_val.eq("<1")
    df["value"] = pd.to_numeric(raw_val.where(~df["below_one"], "0"), errors="coerce")
    df["query"] = frame[mapping["query"]].astype(str).str.strip() if mapping.get("query") else ""
    geo = frame[mapping["geo"]].astype(str).str.strip() if mapping.get("geo") else pd.Series(None, index=frame.index, dtype=object)
    geo = geo.replace({"nan": None, "": None, "None": None})
    # A user-supplied market only fills rows where the file itself states no geography.
    df["geo"] = geo.where(geo.notna(), default_geo) if default_geo else geo
    df["source"] = frame[mapping["source"]].astype(str) if mapping.get("source") else source

    ids = []
    cache: dict[str, str | None] = {}
    for i in frame.index:
        aid = None
        if mapping.get("anime_id"):
            v = str(frame.at[i, mapping["anime_id"]]).strip()
            aid = v if v and v.lower() != "nan" else None
        if aid is None:
            q = df.at[i, "query"]
            if q in overrides:
                aid = overrides[q]
            else:
                if q not in cache:
                    hit, cands = matcher.match(q)
                    cache[q] = hit
                    if hit is None:
                        if cands:
                            rep.ambiguous_titles[q] = cands
                        elif q not in rep.unmatched_titles:
                            rep.unmatched_titles.append(q)
                aid = cache[q]
        ids.append(aid)
    df["anime_id"] = ids

    bad_date = df["date"].isna()
    rep.reject("unparseable date", bad_date.sum())
    bad_val = ~bad_date & df["value"].isna()
    rep.reject("non-numeric value", bad_val.sum())
    out_of_range = ~bad_date & ~bad_val & ((df["value"] < 0) | (df["value"] > 100))
    rep.reject("value outside 0–100 index range", out_of_range.sum())
    no_id = ~bad_date & ~bad_val & ~out_of_range & df["anime_id"].isna()
    rep.reject("title not matched to a catalog record", no_id.sum())
    keep = ~(bad_date | bad_val | out_of_range | no_id)

    out = df[keep].copy()
    out["batch_id"] = uuid.uuid4().hex[:8]
    out["imported_at"] = now_iso()
    before = len(out)
    out = out.drop_duplicates(subset=["anime_id", "geo", "date", "query"], keep="last")
    rep.duplicates_dropped = before - len(out)
    if out["geo"].isna().any():
        rep.notes.append("Some rows have no geography; they will not be labelled as India-specific.")
    rep.notes.append("Google Trends values are normalised 0–100 indices within one export, not search counts.")
    rep.rows_valid = len(out)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out[TREND_COLUMNS].reset_index(drop=True), rep


# --------------------------------------------------------------------------
# Review evidence
# --------------------------------------------------------------------------
def clean_review_text(text):
    """Remove markup only (HTML tags, image/link syntax, spoiler markers); words are kept verbatim."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    t = str(text)
    # Kaggle MAL review dumps prefix the text with the page's score table and suffix "Helpful".
    t = re.sub(r"^\s*(?:more pics\s*)?Overall\s*\d+\s*Story\s*\d+\s*Animation\s*\d+\s*Sound\s*\d+\s*"
               r"Character\s*\d+\s*Enjoyment\s*\d+\s*", "", t, flags=re.I)
    t = re.sub(r"\s*(?:Helpful|read more)\s*$", "", t, flags=re.I)
    t = re.sub(r"img\d*%?\(.*?\)", " ", t)                 # AniList image embeds
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)             # markdown images
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)          # markdown links -> text
    t = re.sub(r"<[^>]+>", " ", t)                          # HTML tags
    t = t.replace("~!", " ").replace("!~", " ").replace("__", "").replace("**", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    return t or None


def validate_reviews(frame: pd.DataFrame, mapping: dict[str, str | None], matcher: TitleMatcher,
                     file_name: str, default_source: str | None = None,
                     min_chars: int = 40) -> tuple[pd.DataFrame, ImportReport]:
    rep = ImportReport("review", file_name, rows_read=len(frame))
    if frame.empty:
        rep.notes.append("File contains no data rows.")
        return pd.DataFrame(columns=REVIEW_COLUMNS), rep
    if not mapping.get("text"):
        rep.reject("no review text column mapped", len(frame))
        return pd.DataFrame(columns=REVIEW_COLUMNS), rep
    if not any(mapping.get(k) for k in ("anime_id", "title", "mal_id", "anilist_id")):
        rep.reject("no title or id column mapped", len(frame))
        return pd.DataFrame(columns=REVIEW_COLUMNS), rep

    def col(name):
        c = mapping.get(name)
        return frame[c].astype(str).str.strip().replace({"nan": None, "": None, "None": None}) if c else pd.Series(None, index=frame.index, dtype=object)

    df = pd.DataFrame(index=frame.index)
    df["text"] = col("text").map(clean_review_text)
    # Link to catalog, strongest key first: explicit id > MAL id > AniList id > exact title.
    ids = []
    for i in frame.index:
        aid = col("anime_id").at[i] if mapping.get("anime_id") else None
        if not aid and mapping.get("mal_id"):
            aid = matcher.by_mal(col("mal_id").at[i])
        if not aid and mapping.get("anilist_id"):
            aid = matcher.by_anilist(col("anilist_id").at[i])
        if not aid and mapping.get("title"):
            t = col("title").at[i] or ""
            aid, cands = matcher.match(t)
            if aid is None and t:
                if cands:
                    rep.ambiguous_titles[t] = cands
                elif t not in rep.unmatched_titles:
                    rep.unmatched_titles.append(t)
        ids.append(aid)
    df["anime_id"] = ids
    df["source"] = col("source").fillna(default_source) if mapping.get("source") else default_source
    df["source_url"] = col("source_url")
    df.loc[df["source_url"].notna() & ~df["source_url"].fillna("").str.match(r"^https?://"), "source_url"] = None
    raw_date = col("date")
    numeric = pd.to_numeric(raw_date, errors="coerce")
    parsed = pd.to_datetime(raw_date, errors="coerce", utc=True, format="mixed")
    # Unix timestamps (AniList createdAt) are numbers of seconds.
    parsed = parsed.where(numeric.isna(), pd.to_datetime(numeric, unit="s", errors="coerce", utc=True))
    df["date"] = parsed.dt.strftime("%Y-%m-%d")
    score = pd.to_numeric(col("score"), errors="coerce")
    if score.notna().any() and score.max() > 10:
        score = score / 10.0  # 0–100 scale (e.g. AniList) → 0–10
        rep.notes.append("Scores above 10 detected; treated as a 0–100 scale and divided by 10.")
    df["score_10"] = score.where((score >= 0) & (score <= 10))
    df["language"] = col("language")
    df["geography"] = col("geography")
    df["helpful_count"] = pd.to_numeric(col("helpful_count"), errors="coerce")
    df["review_id"] = col("review_id")

    no_text = df["text"].isna()
    rep.reject("empty review text", no_text.sum())
    short = ~no_text & (df["text"].str.len() < min_chars)
    rep.reject(f"text shorter than {min_chars} characters", short.sum())
    no_id = ~no_text & ~short & df["anime_id"].isna()
    rep.reject("not matched to a catalog record", no_id.sum())
    keep = ~(no_text | short | no_id)
    out = df[keep].copy()

    missing_rid = out["review_id"].isna()
    out.loc[missing_rid, "review_id"] = [uuid.uuid5(uuid.NAMESPACE_URL, f"{a}|{t[:200]}").hex[:16]
                                         for a, t in zip(out.loc[missing_rid, "anime_id"], out.loc[missing_rid, "text"])]
    out["review_id"] = out["source"].fillna("unknown").astype(str) + ":" + out["review_id"].astype(str)
    before = len(out)
    out = out.drop_duplicates(subset=["review_id"], keep="last")
    rep.duplicates_dropped = before - len(out)
    out["imported_at"] = now_iso()
    if out["geography"].isna().all() and len(out):
        rep.notes.append("No geography supplied: these reviews cannot be treated as Indian audience evidence.")
    rep.rows_valid = len(out)
    return out[REVIEW_COLUMNS].reset_index(drop=True), rep
