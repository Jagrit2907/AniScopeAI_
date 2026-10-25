"""Catalog discovery and loading.

The catalog export's exact column names are not fixed, so the loader maps
common column-name variants onto one internal schema. Nothing is dropped for
missing optional metadata; only rows with no title at all are rejected (and
counted).

Internal catalog schema (one row per catalog record):
    anime_id      stable string key (existing id column, else derived from sources)
    title         primary title
    synonyms      list[str]
    type, episodes, status, season, year
    tags, studios list[str]
    score         cross-site aggregate score if present (global, not India)
    sources       list[str] of source URLs
    mal_id, anilist_id   ints parsed from sources (for linking evidence)
    picture       image URL if present
    search_text   lower-cased title + synonyms (for search)
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config import settings

ALIASES: dict[str, list[str]] = {
    "anime_id": ["aniscope_catalog_id", "anime_id", "aniscope_id", "catalog_id", "record_id", "id", "uid"],
    "title": ["title", "primary_title", "canonical_title", "name", "anime_title", "main_title"],
    "synonyms": ["synonyms", "alternate_titles", "alternative_titles", "alt_titles", "aliases",
                 "other_titles", "title_synonyms", "synonyms_json"],
    "type": ["type", "format", "media_type", "anime_type"],
    "episodes": ["episodes", "episode_count", "num_episodes"],
    "status": ["status", "airing_status"],
    "season": ["season", "anime_season", "animeseason_season", "anime_season_season"],
    "year": ["year", "season_year", "anime_season_year", "animeseason_year", "start_year"],
    "tags": ["tags", "tags_json", "genres", "themes", "tag_list"],
    "studios": ["studios", "studios_json", "studio"],
    "score": ["score", "score_arithmetic_mean", "score_arithmeticmean", "mean_score",
              "score_median", "score_arithmetic_geometric_mean", "average_score"],
    "sources": ["sources", "sources_json", "source_urls", "urls", "source_links", "links"],
    "picture": ["picture", "picture_url", "image", "image_url", "cover_image"],
    "mal_id_col": ["myanimelist_id", "mal_id", "idmal"],
    "anilist_id_col": ["anilist_id"],
}

LIST_FIELDS = ["synonyms", "tags", "studios", "sources"]


@dataclass
class CatalogLoadResult:
    df: pd.DataFrame | None
    path: Path | None
    files_found: list[str] = field(default_factory=list)
    rejected_rows: int = 0
    column_map: dict[str, str] = field(default_factory=dict)
    unmapped_columns: list[str] = field(default_factory=list)
    error: str | None = None
    manifest: dict | None = None

    @property
    def ok(self) -> bool:
        return self.df is not None and self.error is None


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------
def _norm_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def parse_list(value) -> list[str]:
    """Accept a real list, a JSON list string, or a | ; or newline separated string."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, float) and pd.isna(value):
        return []
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "[]"}:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except json.JSONDecodeError:
            pass
    for sep in ("|", ";", "\n"):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    return [text]


def _site_id(sources: list[str], host: str) -> int | None:
    for url in sources:
        m = re.search(rf"{host}/anime/(\d+)", url)
        if m:
            return int(m.group(1))
    return None


def _score_value(value):
    """Scores may arrive as a number, or as a JSON object string from a nested export."""
    if isinstance(value, dict):
        return value.get("arithmeticMean", value.get("median"))
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            obj = json.loads(value.replace("'", '"'))
            return obj.get("arithmeticMean", obj.get("median"))
        except json.JSONDecodeError:
            return None
    return value


def normalize_title(text: str) -> str:
    """Lower-case, strip punctuation and collapse spaces; used for matching."""
    text = str(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
def discover_files(data_dir: Path | None = None) -> dict[str, Path | None]:
    data_dir = data_dir or settings.RAW_DATA_DIR
    found: dict[str, Path | None] = {"catalog": None, "manifest": None,
                                     "trend_template": None, "review_template": None}
    if not data_dir.exists():
        return found
    for name in settings.CATALOG_CANDIDATES:
        if (data_dir / name).exists():
            found["catalog"] = data_dir / name
            break
    if found["catalog"] is None:  # fall back to any catalog-looking file
        for pattern in ("*catalog*.jsonl", "*catalog*.csv"):
            hits = sorted(data_dir.glob(pattern))
            if hits:
                found["catalog"] = hits[0]
                break
    for key, name in (("manifest", settings.MANIFEST_NAME),
                      ("trend_template", settings.TREND_TEMPLATE_NAME),
                      ("review_template", settings.REVIEW_TEMPLATE_NAME)):
        if (data_dir / name).exists():
            found[key] = data_dir / name
    return found


def load_manifest(path: Path | None) -> dict | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def _flatten_aod_record(rec: dict) -> dict:
    """Flatten nested Anime-Offline-Database style records."""
    out = dict(rec)
    season = rec.get("animeSeason")
    if isinstance(season, dict):
        out["season"] = season.get("season")
        out["year"] = season.get("year")
    score = rec.get("score")
    if isinstance(score, dict):
        out["score"] = score.get("arithmeticMean", score.get("median"))
    out.pop("animeSeason", None)
    out.pop("duration", None)
    out.pop("relatedAnime", None)
    return out


def _read_raw(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        rows = []
        with path.open(encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(_flatten_aod_record(json.loads(line)))
                    except json.JSONDecodeError:
                        rows.append({"__bad__": True})
        return pd.DataFrame(rows)
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        records = payload.get("data", payload) if isinstance(payload, dict) else payload
        return pd.DataFrame([_flatten_aod_record(r) for r in records])
    # CSV: try UTF-8 first, then a Windows code page.
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path.name}")


def map_columns(columns: list[str]) -> tuple[dict[str, str], list[str]]:
    """Return {internal_field: source_column} and the list of unmapped columns."""
    norm = {_norm_col(c): c for c in columns}
    mapping: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if _norm_col(alias) in norm:
                mapping[target] = norm[_norm_col(alias)]
                break
    used = set(mapping.values())
    return mapping, [c for c in columns if c not in used]


def standardize_catalog(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str], int]:
    mapping, unmapped = map_columns(list(raw.columns))
    if "title" not in mapping:
        raise ValueError("No title column found. Expected one of: " + ", ".join(ALIASES["title"]))

    df = pd.DataFrame(index=raw.index)
    for target in ALIASES:
        src = mapping.get(target)
        df[target] = raw[src] if src else None

    for col in LIST_FIELDS:
        df[col] = df[col].map(parse_list)
    df["title"] = df["title"].astype("string").str.strip()
    rejected = int(df["title"].isna().sum() + (df["title"] == "").sum())
    df = df[df["title"].notna() & (df["title"] != "")].copy()

    df["episodes"] = pd.to_numeric(df["episodes"], errors="coerce").astype("Int64")
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["score"] = pd.to_numeric(df["score"].map(_score_value), errors="coerce")
    for col in ("type", "status", "season"):
        df[col] = df[col].astype("string").str.upper().str.strip()
        df.loc[df[col].isin(["NAN", "NONE", "UNDEFINED", ""]), col] = pd.NA

    # Prefer explicit id columns from the export; fall back to parsing source URLs.
    mal_from_url = df["sources"].map(lambda s: _site_id(s, "myanimelist.net"))
    al_from_url = df["sources"].map(lambda s: _site_id(s, "anilist.co"))
    df["mal_id"] = pd.to_numeric(df["mal_id_col"], errors="coerce").fillna(pd.to_numeric(mal_from_url, errors="coerce")).astype("Int64")
    df["anilist_id"] = pd.to_numeric(df["anilist_id_col"], errors="coerce").fillna(pd.to_numeric(al_from_url, errors="coerce")).astype("Int64")
    df = df.drop(columns=["mal_id_col", "anilist_id_col"])

    # Stable id: keep an existing id column if it is unique, otherwise derive one.
    existing = df["anime_id"]
    if existing.notna().all() and existing.astype(str).is_unique:
        df["anime_id"] = existing.astype(str)
    else:
        def derive(row) -> str:
            if pd.notna(row["mal_id"]):
                return f"mal-{int(row['mal_id'])}"
            if pd.notna(row["anilist_id"]):
                return f"al-{int(row['anilist_id'])}"
            basis = row["sources"][0] if row["sources"] else f"{row['title']}|{row['type']}|{row['year']}"
            return "h-" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
        df["anime_id"] = df.apply(derive, axis=1)
        # Guarantee uniqueness when two records share a derived key.
        dup = df["anime_id"].duplicated(keep=False)
        if dup.any():
            df.loc[dup, "anime_id"] = df.loc[dup, "anime_id"] + "-" + df.loc[dup].groupby("anime_id").cumcount().astype(str)

    df["search_text"] = (df["title"].fillna("") + " | " + df["synonyms"].map(" | ".join)).str.lower()
    df["title_norm"] = df["title"].map(normalize_title)
    df = df.reset_index(drop=True)
    return df, mapping, unmapped, rejected


def load_catalog(data_dir: Path | None = None) -> CatalogLoadResult:
    data_dir = data_dir or settings.RAW_DATA_DIR
    files = discover_files(data_dir)
    found = [p.name for p in files.values() if p]
    manifest = load_manifest(files["manifest"])
    if not data_dir.exists():
        return CatalogLoadResult(None, None, found, error=f"Data folder not found: {data_dir}", manifest=manifest)
    if files["catalog"] is None:
        return CatalogLoadResult(None, None, found, manifest=manifest,
                                 error=f"No catalog file found in {data_dir}. Expected "
                                       + " or ".join(settings.CATALOG_CANDIDATES[:2]))
    path = files["catalog"]
    try:
        raw = _read_raw(path)
        df, mapping, unmapped, rejected = standardize_catalog(raw)
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a readable error
        return CatalogLoadResult(None, path, found, manifest=manifest, error=f"Could not read {path.name}: {exc}")
    return CatalogLoadResult(df, path, found, rejected, mapping, unmapped, None, manifest)


def catalog_summary(df: pd.DataFrame) -> dict:
    return {
        "records": int(len(df)),
        "unique_titles": int(df["title"].nunique()),
        "duplicate_title_records": int(df["title"].duplicated(keep=False).sum()),
        "with_mal_id": int(df["mal_id"].notna().sum()),
        "with_anilist_id": int(df["anilist_id"].notna().sum()),
        "with_year": int(df["year"].notna().sum()),
        "with_score": int(df["score"].notna().sum()),
        "with_tags": int((df["tags"].map(len) > 0).sum()),
    }
