"""Backend pipeline tests (SYNTHETIC data only)."""
import importlib
import os

import pandas as pd

from src.data_validation import TitleMatcher, parse_google_trends_export


def _settings(tmp_path):
    os.environ["ANISCOPE_PROCESSED_DIR"] = str(tmp_path / "proc")
    os.environ["ANISCOPE_DATA_DIR"] = str(tmp_path / "raw")
    from config import settings
    importlib.reload(settings)
    return settings


def test_time_format_has_no_geography():
    d = parse_google_trends_export(b'"Time","Test Alpha","Test Beta"\n"2025-01-01",5,0\n"2025-02-01",7,3\n')
    assert d["geo"].isna().all() and set(d["query"]) == {"Test Alpha", "Test Beta"} and len(d) == 4


def test_query_map_resolves_by_mal_id_only(tmp_path, catalog):
    from src import pipeline
    p = tmp_path / "map.csv"
    pd.DataFrame({"query": ["Alpha EN", "Ghost"], "myanimelist_id": [1, 999]}).to_csv(p, index=False)
    qmap, problems = pipeline.load_query_map(catalog, p)
    assert qmap == {"Alpha EN": "mal-1"} and len(problems) == 1


def test_trends_import_uses_map_and_file_batch(tmp_path, catalog):
    settings = _settings(tmp_path)
    from src import evidence_store, pipeline
    f = tmp_path / "trends_india_batch_9.csv"
    f.write_text('"Time","Alpha EN"\n' + "\n".join(f'"2025-{m:02d}-01",{m}' for m in range(1, 13)))
    rep, total, out = pipeline.import_trends_file(f, TitleMatcher(catalog), default_geo="India",
                                                  query_map={"Alpha EN": "mal-1"})
    assert rep.rows_valid == 12 and total == 12
    t = evidence_store.load_trends(settings.TREND_STORE)
    assert set(t["batch_id"]) == {"trends_india_batch_9"} and set(t["geo"]) == {"India"}
    assert t["source"].iloc[0] == "Google Trends export (trends_india_batch_9.csv)"


def test_chunked_reviews_match_rates_cap_and_no_usernames(tmp_path, catalog):
    settings = _settings(tmp_path)
    from src import evidence_store, pipeline
    animes = tmp_path / "animes.csv"
    pd.DataFrame({"uid": [1, 2, 3, 77], "title": ["Test Alpha", "Test Beta", "Test Beta", "Not In Catalog"]}).to_csv(animes, index=False)
    long = "The story is clever and the world-building is rich, but the pacing drags badly in the middle. " * 2
    rows = [{"uid": i, "profile": f"secret_user_{i}", "anime_uid": 1, "text": long + str(i), "score": 7, "scores": "{}",
             "link": f"https://myanimelist.net/reviews.php?id={i}"} for i in range(8)]
    rows += [{"uid": 100, "profile": "x", "anime_uid": 77, "text": long, "score": 5, "scores": "{}", "link": ""},
             {"uid": 101, "profile": "y", "anime_uid": "bad", "text": long, "score": 5, "scores": "{}", "link": ""},
             {"uid": 102, "profile": "z", "anime_uid": 2, "text": "too short", "score": 5, "scores": "{}", "link": ""}]
    src = tmp_path / "reviews.csv"
    pd.DataFrame(rows).to_csv(src, index=False)
    stats = pipeline.import_reviews_chunked(src, catalog, animes, "TEST", cap=5, min_reviews=1, chunksize=3)
    assert stats["rows_read"] == 11 and stats["unparseable_anime_uid"] == 1
    assert stats["uid_not_in_catalog"] == 1 and stats["empty_or_short_text"] == 1
    assert stats["reviews_written"] == 5                      # capped at 5 for Test Alpha
    assert stats["match_rate_vs_animes_csv"] == 1.0           # all 10 parseable uids exist in animes.csv
    store = evidence_store.load_reviews(settings.REVIEW_STORE)
    assert store["source_url"].str.startswith("https://myanimelist.net/reviews.php").all()
    assert not store.astype(str).apply(lambda c: c.str.contains("secret_user")).any().any()
    assert store["geography"].isna().all()


def test_mal_audit_counts(tmp_path, catalog):
    from src import pipeline
    animes = tmp_path / "animes.csv"
    pd.DataFrame({"uid": [1, 2, 555], "title": ["Test Alpha", "Something Else", "Missing"]}).to_csv(animes, index=False)
    r = pipeline.mal_mapping_audit(catalog, animes)
    assert r["uids_with_one_catalog_record"] == 2 and r["uids_not_in_catalog"] == 1
    assert r["title_agreement_rate"] == 0.5
