"""Review-sentiment model — SYNTHETIC fixture data only. These tests check mechanics,
never real model quality, and never touch the real reviews.csv."""
import importlib
import json
import os
import random

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src import ml_sentiment as ml

POS = ["the animation is gorgeous", "I loved every character", "a brilliant moving story", "fantastic soundtrack throughout"]
NEG = ["the pacing is painfully slow", "a boring messy plot", "flat annoying characters", "a total waste of time"]
MIX = ["good moments but it drags", "some episodes great others dull", "decent yet forgettable", "fun at first then loses steam"]
FILL = ["I watched it over a weekend.", "This covers season one.", "No spoilers here.", "Adapted from the manga."]


def write_kaggle_csv(path, n=800, titles=40, seed=3):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        s = rng.randint(1, 10)
        bank = POS if s >= 7 else NEG if s <= 4 else MIX
        body = " ".join(rng.sample(bank, 3) + rng.sample(FILL, 2)) + f" Review {i}."
        text = f"\n more pics \n Overall\n {s} \n Story\n 5 \n Animation\n 6 \n Sound\n 7 \n Character\n 8 \n Enjoyment\n {s} \n {body} \n Helpful"
        rows.append({"uid": i, "profile": f"user{i}", "anime_uid": i % titles, "text": text, "score": s, "scores": "{}", "link": ""})
    rows.append(dict(rows[0]))                                                 # repeated id
    rows.append({**rows[1], "uid": 9001, "anime_uid": 999})                    # exact duplicate text, other title
    rows.append({"uid": 9002, "profile": "u", "anime_uid": 1, "text": "", "score": 7, "scores": "{}", "link": ""})
    rows.append({"uid": 9003, "profile": "u", "anime_uid": 1, "text": "long enough text but the score is not a number at all", "score": "n/a", "scores": "{}", "link": ""})
    rows.append({"uid": 9004, "profile": "u", "anime_uid": 1, "text": "long enough text but the score is outside the scale", "score": 11, "scores": "{}", "link": ""})
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture
def trained(tmp_path):
    src = tmp_path / "reviews.csv"
    write_kaggle_csv(src)
    frame, stats = ml.load_training_data(src, chunksize=100)
    model, meta = ml.train_and_evaluate(frame, seed=42, test_share=0.25, min_df=1, log=lambda *_: None)
    meta["data"] = {"file": src.name, **stats}
    return ml.save(model, meta, tmp_path / "model"), stats, meta, frame


def test_cleaning_strips_score_table_and_maps_labels():
    t = "\n more pics \n Overall\n 9 \n Story\n 8 \n Animation\n 9 \n Sound\n 7 \n Character\n 8 \n Enjoyment\n 9 \n Great show. \n Helpful"
    assert ml.prepare_text(t) == "Great show."
    assert [ml.label_for(x) for x in (1, 4, 5, 6, 7, 10)] == ["negative", "negative", "mixed", "mixed", "positive", "positive"]
    assert ml.label_for(0) is None and ml.label_for(11) is None and ml.label_for(7.5) is None and ml.label_for("x") is None


def test_training_data_filters_and_title_split(trained):
    _, stats, meta, frame = trained
    assert stats["rows_read"] == 805 and stats["duplicate_review_id"] == 1 and stats["duplicate_text"] == 1
    assert stats["invalid_or_missing_score"] == 2 and stats["missing_or_short_text"] == 1 and stats["usable"] == 800
    held = frame["group"].map(lambda g: ml.in_test_set(g, 42, 0.25))
    assert not set(frame[held]["group"]) & set(frame[~held]["group"])           # no title on both sides
    sp, m = meta["split"], meta["test_metrics"]
    assert sp["train_reviews"] + sp["test_reviews"] == 800 and sp["test_titles"] > 0
    assert set(m) >= {"accuracy", "macro_f1", "per_class", "confusion_matrix"}
    assert sum(map(sum, m["confusion_matrix"])) == sp["test_reviews"] and meta["majority_baseline"]["predicts"] in ml.LABELS


def test_save_load_predict(trained):
    out, *_ = trained
    model, meta = ml.load(out)
    p = ml.predict_text("The animation is gorgeous and I loved every character.", out)
    assert p["label"] in ml.LABELS and set(p["probabilities"]) == set(ml.LABELS)
    assert abs(sum(p["probabilities"].values()) - 1) < 1e-3 and all(0 <= v <= 1 for v in p["probabilities"].values())
    assert p["probabilities"][p["label"]] == max(p["probabilities"].values()) and p["model_id"] == meta["model_id"]
    agg = ml.predict_reviews(["a boring messy plot and flat annoying characters", "a total waste of time"], out)
    assert agg["n"] == 2 and sum(agg["counts"].values()) == 2
    assert (out / ml.REPORT_FILE).read_text(encoding="utf-8").startswith("# Sentiment model evaluation")


@pytest.mark.parametrize("bad", ["", "   ", None, 5, "x" * 20_001])
def test_invalid_input_rejected(trained, bad):
    with pytest.raises(ValueError):
        ml.predict_text(bad, trained[0])


def test_missing_model(tmp_path):
    with pytest.raises(ml.ModelUnavailable):
        ml.load(tmp_path / "none")
    with pytest.raises(ml.ModelUnavailable):
        ml.predict_text("a fine review", tmp_path / "none")


@pytest.fixture
def client(tmp_path, trained):
    raw, proc, db = tmp_path / "raw", tmp_path / "proc", tmp_path / "db"
    for d in (raw, proc, db):
        d.mkdir()
    pd.DataFrame({"aniscope_catalog_id": ["a1", "b2"], "title": ["Synthetic Alpha", "Synthetic Beta"], "type": ["TV", "TV"],
                  "season_year": [2024, 2025], "sources_json": ['["https://myanimelist.net/anime/901"]', '["https://myanimelist.net/anime/902"]'],
                  "tags_json": ['["drama"]', '["action"]'], "score_arithmetic_mean": [7.2, 6.4]}).to_csv(raw / "anime_catalog_all_titles.csv", index=False)
    (raw / "dataset_manifest.json").write_text(json.dumps({"upstream_snapshot_date": "2026-07-04"}))
    pd.DataFrame({"review_id": [f"t:{i}" for i in range(6)], "anime_id": "a1", "source": "synthetic", "source_url": "", "date": "",
                  "text": [f"The animation is gorgeous and I loved every character. Note {i}." for i in range(6)], "score_10": 9,
                  "language": "", "geography": "", "helpful_count": "", "imported_at": "x"}).to_csv(proc / "review_evidence.csv", index=False)
    os.environ.update(ANISCOPE_DATA_DIR=str(raw), ANISCOPE_PROCESSED_DIR=str(proc), ANISCOPE_DATABASE_DIR=str(db),
                      ANISCOPE_MODEL_DIR=str(trained[0]))
    from config import settings
    importlib.reload(settings)
    from server import data
    data._cache.clear()
    from server.api import app
    yield TestClient(app), settings
    os.environ.pop("ANISCOPE_MODEL_DIR", None)


def test_api_prediction_and_audience(client):
    c, _ = client
    r = c.post("/api/ml/sentiment", json={"text": "The animation was beautiful and the story was engaging."})
    body = r.json()
    assert r.status_code == 200 and body["label"] in ml.LABELS and abs(sum(body["probabilities"].values()) - 1) < 1e-3
    assert c.post("/api/ml/sentiment", json={"text": "   "}).status_code == 422
    assert c.post("/api/ml/sentiment", json={}).status_code == 422
    assert c.post("/api/ml/sentiment", json={"text": 12}).status_code == 422
    a = c.get("/api/audience/a1").json()["ml"]
    assert a["available"] and a["prediction"]["n"] == 6
    b = c.get("/api/audience/b2").json()["ml"]
    assert b["available"] and b["prediction"] is None                          # no reviews → no prediction


def test_api_without_model(client, tmp_path):
    c, settings = client
    settings.ML_MODEL_DIR = tmp_path / "missing"
    assert c.post("/api/ml/sentiment", json={"text": "great show"}).status_code == 503
    a = c.get("/api/audience/a1").json()
    assert a["ml"]["available"] is False and a["overview"]["records"] == 6     # rest of Audience still works
