"""Web API tests (SYNTHETIC data). The API must expose the same analytics as src/, never invented values."""
import importlib
import json
import os

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    raw, proc, db = tmp_path / "raw", tmp_path / "proc", tmp_path / "db"
    for d in (raw, proc, db):
        d.mkdir()
    pd.DataFrame({"aniscope_catalog_id": ["a1", "b2"], "title": ["Synthetic Alpha", "Synthetic Beta"], "type": ["TV", "TV"],
                  "season_year": [2024, 2025], "sources_json": ['["https://myanimelist.net/anime/901"]', '["https://myanimelist.net/anime/902"]'],
                  "tags_json": ['["drama"]', '["action"]'], "score_arithmetic_mean": [7.2, 6.4]}).to_csv(raw / "anime_catalog_all_titles.csv", index=False)
    (raw / "dataset_manifest.json").write_text(json.dumps({"upstream_snapshot_date": "2026-07-04"}))
    dates = pd.date_range("2021-10-01", periods=24, freq="MS").strftime("%Y-%m-%d")
    pd.DataFrame({"anime_id": "a1", "query": "Alpha", "geo": "India", "date": dates, "value": [10] * 18 + [20] * 6,
                  "below_one": False, "source": "synthetic", "batch_id": "b1", "imported_at": "x"}).to_csv(proc / "trend_observations.csv", index=False)
    text = "The world-building is brilliant and the lore is fascinating. The pacing is painfully slow and boring."
    pd.DataFrame({"review_id": [f"t:{i}" for i in range(6)], "anime_id": "a1", "source": "synthetic", "source_url": "https://example.org/r",
                  "date": "2025-01-01", "text": [f"{text} ({i})" for i in range(6)], "score_10": 6, "language": "", "geography": "",
                  "helpful_count": "", "imported_at": "x"}).to_csv(proc / "review_evidence.csv", index=False)
    os.environ.update(ANISCOPE_DATA_DIR=str(raw), ANISCOPE_PROCESSED_DIR=str(proc), ANISCOPE_DATABASE_DIR=str(db))
    from config import settings
    importlib.reload(settings)
    from server import data
    data._cache.clear()
    from server.api import app
    return TestClient(app)


def test_status_counts_real_files(client):
    s = client.get("/api/status").json()
    assert s["catalog_ok"] and s["summary"]["records"] == 2
    assert s["coverage"]["trend_titles"] == 1 and s["coverage"]["reviews"] == 6 and s["coverage"]["review_titles"] == 1


def test_trends_monthly_growth_matches_src(client):
    t = client.get("/api/trends").json()
    row = t["rows"][0]
    assert t["frequency"] == "monthly" and row["anime_id"] == "a1"
    assert row["baseline_mean"] == 10 and row["recent_mean"] == 20 and row["pct_change"] == 100
    s = client.get("/api/trends/series", params={"anime_id": "a1", "query": "Alpha"}).json()
    assert len(s["points"]) == 24 and s["geo"] == "India"


def test_audience_and_missing_evidence_is_honest(client):
    a = client.get("/api/audience/a1").json()
    assert a["overview"]["records"] == 6 and a["overview"]["india_tagged"] == 0
    assert any(x["aspect"] == "World-building" for x in a["aspects"])
    assert a["excerpts"]["World-building"]["positive"][0]["url"] == "https://example.org/r"
    b = client.get("/api/audience/b2").json()
    assert b["overview"] == {"records": 0} and "aspects" not in b


def test_gems_workspace_brief_and_exports(client):
    g = client.get("/api/gems").json()
    assert g["total"] == 1 and "World-building" in g["candidates"][0]["praised"]
    c = g["candidates"][0]
    client.post(f"/api/gems/{c['anime_id']}/use", json={"praised": c["praised"], "criticised": c["criticised"], "why": c["why"], "n_reviews": c["n_reviews"]})
    ws = client.get("/api/workspace").json()
    assert ws["selected_anime_id"] == "a1" and ws["selected_finding"]["praised"] == c["praised"]
    con = client.post("/api/concept", json={"themes": ["World-building"], "variation": 0}).json()
    assert con["inspired_by_themes"] == ["World-building"]
    calc = client.post("/api/calc", json={"target_audience": 1000, "reach_rate_pct": 10, "conversion_rate_pct": 10, "price": 100,
                                           "variable_cost": 40, "fixed_costs": 100, "currency": "INR", "duration_weeks": 1, "is_demo": False}).json()
    assert calc["result"]["customers"] == 10 and calc["result"]["result_after_fixed"] == 500
    b = client.get("/api/brief").json()
    assert "Synthetic Alpha" in b["title"] and con["working_title"] in json.dumps(b)
    assert client.get("/api/brief.md").status_code == 200
    assert client.get("/api/export/aspects.csv").status_code == 200


def test_calc_rejects_invalid(client):
    r = client.post("/api/calc", json={"target_audience": -5, "reach_rate_pct": 150}).json()
    assert len(r["result"]["errors"]) == 2


def test_select_unknown_title_404(client):
    assert client.post("/api/workspace/select", json={"anime_id": "nope"}).status_code == 404
