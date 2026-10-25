"""Smoke tests: every screen renders without exceptions, with and without evidence.

Uses a tiny SYNTHETIC catalog/evidence set in a temp folder (test-only data).
"""
import importlib
import json
import os
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["views/command_center.py", "views/trending_radar.py", "views/audience_intelligence.py",
         "views/creative_lab.py", "views/business_planner.py", "views/opportunity_brief.py", "views/data_methods.py"]


def _configure(tmp: Path, with_catalog=True, with_evidence=False):
    raw, proc, db = tmp / "raw", tmp / "processed", tmp / "db"
    for d in (raw, proc, db):
        d.mkdir(parents=True, exist_ok=True)
    if with_catalog:
        pd.DataFrame({"title": ["Synthetic Alpha", "Synthetic Beta"], "type": ["TV", "TV"], "year": [2024, 2025],
                      "sources": ["https://myanimelist.net/anime/901", "https://myanimelist.net/anime/902"],
                      "tags": ["drama", "action"], "score": [7.2, 6.4]}).to_csv(raw / "anime_catalog_all_titles.csv", index=False)
        (raw / "dataset_manifest.json").write_text(json.dumps({"snapshot_date": "2026-07-04"}))
    if with_evidence:
        dates = pd.date_range("2025-01-05", periods=30, freq="7D")
        pd.DataFrame({"anime_id": "mal-901", "query": "Synthetic Alpha", "geo": "India", "date": dates.strftime("%Y-%m-%d"),
                      "value": list(range(5, 35)), "below_one": False, "source": "synthetic test", "batch_id": "b1",
                      "imported_at": "2026-10-24"}).to_csv(proc / "trend_observations.csv", index=False)
        texts = ["The world-building is brilliant and the lore is fascinating. The pacing is painfully slow and boring."] * 6
        pd.DataFrame({"review_id": [f"t:{i}" for i in range(6)], "anime_id": "mal-901", "source": "synthetic test",
                      "source_url": "", "date": "2025-06-01", "text": [t + f" ({i})" for i, t in enumerate(texts)],
                      "score_10": 6, "language": "en", "geography": "", "helpful_count": "", "imported_at": "2026-10-24"}
                     ).to_csv(proc / "review_evidence.csv", index=False)
    os.environ["ANISCOPE_DATA_DIR"] = str(raw)
    os.environ["ANISCOPE_PROCESSED_DIR"] = str(proc)
    os.environ["ANISCOPE_DATABASE_DIR"] = str(db)
    from config import settings
    importlib.reload(settings)


def _run_all(selected=None):
    for page in PAGES:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
        if selected:
            at.session_state["selected_anime_id"] = selected
        at.run()
        if page != PAGES[0]:
            at.switch_page(page)
            at.run()
        assert not at.exception, f"{page}: {at.exception}"
        yield page, at


@pytest.mark.parametrize("with_evidence", [False, True])
def test_all_pages_render(tmp_path, with_evidence):
    _configure(tmp_path, with_evidence=with_evidence)
    texts = {}
    for page, at in _run_all("mal-901"):
        texts[page] = " ".join(m.value for m in at.markdown)
    if with_evidence:
        assert "Synthetic Alpha" in texts["views/opportunity_brief.py"]
        assert "World-building" in " ".join(texts.values())
    else:
        assert "No dated trend observations" in texts["views/trending_radar.py"] or \
               "No trend observations yet" in texts["views/trending_radar.py"]


def test_missing_catalog_shows_help(tmp_path):
    _configure(tmp_path, with_catalog=False)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception
    assert any("Catalog not loaded" in m.value for m in at.markdown)


def test_workflow_carries_state_to_brief(tmp_path):
    """Concept built in the Lab and demo assumptions in the Planner appear in the Brief."""
    _configure(tmp_path, with_evidence=True)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["selected_anime_id"] = "mal-901"
    at.run()
    at.switch_page("views/creative_lab.py").run()
    at.multiselect[0].set_value(["World-building", "Pacing"]).run()
    next(b for b in at.button if b.label == "Build concept").click().run()
    assert not at.exception
    concept = at.session_state["concept"]
    assert concept["inspired_by_themes"] == ["World-building", "Pacing"]
    at.switch_page("views/business_planner.py").run()
    next(b for b in at.button if b.label == "Load demo assumptions").click().run()
    assert not at.exception
    assert at.session_state["assumptions"]["is_demo"] is True
    assert any("DEMO assumptions" in w.value for w in at.warning)
    at.switch_page("views/opportunity_brief.py").run()
    assert not at.exception
    page = " ".join(m.value for m in at.markdown)
    assert concept["working_title"] in page
    assert "demo assumptions" in page.lower()
