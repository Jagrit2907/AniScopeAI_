import pandas as pd

from src.catalog_service import search
from src.data_loader import parse_list, standardize_catalog
from src.data_validation import (REVIEW_FIELD_ALIASES, TREND_FIELD_ALIASES, TitleMatcher, guess_mapping,
                                 parse_google_trends_export, validate_reviews, validate_trends)


def test_catalog_keeps_records_with_missing_optional_fields(catalog):
    # 5 raw rows, 1 has no title -> 4 kept; missing year/episodes do not drop rows
    assert len(catalog) == 4
    assert catalog["year"].isna().sum() == 1
    assert catalog.loc[catalog["title"] == "Test Alpha", "mal_id"].iloc[0] == 1
    assert catalog.loc[catalog["title"] == "Gamma Show", "anime_id"].iloc[0] == "al-44"
    assert catalog["anime_id"].is_unique


def test_standardize_counts_rejected_rows():
    raw = pd.DataFrame({"name": ["A", "", None]})
    df, mapping, _, rejected = standardize_catalog(raw)
    assert mapping["title"] == "name" and len(df) == 1 and rejected == 2


def test_parse_list_formats():
    assert parse_list('["a", "b"]') == ["a", "b"]
    assert parse_list("a | b") == ["a", "b"]
    assert parse_list(None) == [] and parse_list(float("nan")) == []


def test_search_uses_synonyms(catalog):
    assert search(catalog, "alpha alt")["title"].tolist() == ["Test Alpha"]
    assert search(catalog, "test beta")["title"].tolist() == ["Test Beta", "Test Beta"]
    assert search(catalog, "").empty


def test_matcher_flags_ambiguous_titles(catalog):
    m = TitleMatcher(catalog)
    assert m.match("test alpha")[0] == "mal-1"
    aid, cands = m.match("Test Beta")      # two records share this title
    assert aid is None and len(cands) == 2
    assert m.by_mal(2) == "mal-2" and m.by_anilist(44) == "al-44"


def test_google_trends_native_format_and_validation(catalog):
    data = ("Category: All categories\n\nWeek,Test Alpha: (India),Unknown Show: (India)\n"
            "2026-01-04,10,<1\n2026-01-11,abc,3\n2026-01-18,250,5\n").encode()
    long = parse_google_trends_export(data)
    assert set(long["geo"]) == {"India"} and len(long) == 6
    mapping = {"date": "date", "value": "raw_value", "query": "query", "geo": "geo"}
    out, rep = validate_trends(long, mapping, TitleMatcher(catalog), "t.csv")
    # Only Test Alpha rows match; of those one is non-numeric and one out of range
    assert rep.rows_valid == 1
    assert rep.rejected["non-numeric value"] == 1
    assert rep.rejected["value outside 0–100 index range"] == 1
    assert rep.rejected["title not matched to a catalog record"] == 3
    assert "Unknown Show" in rep.unmatched_titles


def test_trend_query_override_resolves_ambiguity(catalog):
    frame = pd.DataFrame({"date": ["2026-01-04"], "value": ["5"], "query": ["Test Beta"], "geo": ["India"]})
    m = guess_mapping(list(frame.columns), TREND_FIELD_ALIASES)
    out, rep = validate_trends(frame, m, TitleMatcher(catalog), "x", query_overrides={"Test Beta": "mal-3"})
    assert out["anime_id"].tolist() == ["mal-3"]


def test_review_validation(catalog):
    frame = pd.DataFrame({
        "anime_title": ["Test Alpha", "Test Alpha", "Nope", "Test Alpha"],
        "review_text": ["A long enough review about the story and characters here.", "short",
                        "Another long enough review text that will not match.", ""],
        "rating": ["85", "70", "60", "50"],
        "created_at": ["1700000000", "2024-02-01", "2024-02-02", "2024-02-03"],
    })
    m = guess_mapping(list(frame.columns), REVIEW_FIELD_ALIASES)
    out, rep = validate_reviews(frame, m, TitleMatcher(catalog), "r.csv", default_source="test")
    assert rep.rows_valid == 1
    assert out["score_10"].iloc[0] == 8.5        # 0–100 scale converted
    assert out["date"].iloc[0] == "2023-11-14"   # unix seconds parsed
    assert rep.rejected["not matched to a catalog record"] == 1
