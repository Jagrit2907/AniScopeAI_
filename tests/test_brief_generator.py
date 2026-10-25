import pandas as pd

from src.brief_generator import build_brief, to_markdown
from src.concept_builder import build_concept
from src.export_service import PDF_AVAILABLE, brief_to_pdf
from src.opportunity_engine import analyse_title
from src.review_analysis import review_level, sentiment
from src.theme_extraction import extract_aspect_evidence

EMPTY = dict(title=None, trend=None, evidence=None, aspects=None, finding=None, concept=None,
             plan=None, assumptions=None, calc=None, validation=None, catalog_source="test")


def test_empty_brief_lists_gaps_not_findings():
    b = build_brief(**EMPTY)
    assert "No title selected" in b["title"]
    assert any("No India trend" in g for g in b["gaps"])
    assert any("No audience review evidence" in g for g in b["gaps"])
    assert "no supporting evidence" in b["sections"]["Executive summary"][0]


def test_brief_reflects_inputs_and_pdf_contains_title():
    args = dict(EMPTY)
    args["title"] = {"title": "Synthetic Show", "type": "TV", "year": 2024, "tags": ["drama"], "score": 7.1}
    args["concept"] = build_concept(["World-building"], "insight", "aud", "Original series pitch")
    b = build_brief(**args)
    md = to_markdown(b)
    assert "Synthetic Show" in md and args["concept"]["working_title"] in md
    if PDF_AVAILABLE:
        pdf = brief_to_pdf(b)
        assert pdf[:4] == b"%PDF" and len(pdf) > 1500


def test_concept_changes_with_variation_and_traces_themes():
    a = build_concept(["Pacing"], "i", "a", "o", variation=0)
    b = build_concept(["Pacing"], "i", "a", "o", variation=1)
    assert a["inspired_by_themes"] == ["Pacing"]
    assert (a["working_title"], a["core_premise"]) != (b["working_title"], b["core_premise"])
    assert "Unvalidated" in a["validation_status"]


def test_hidden_gem_requires_praise_and_criticism():
    # SYNTHETIC reviews for a unit test, not real audience evidence.
    texts = ["The world-building is brilliant and the lore is fascinating. The pacing is painfully slow and boring.",
             "Amazing world-building, a wonderful setting. Sadly the pacing dragged and it was boring.",
             "I loved the world-building and the beautiful setting. The slow pacing was awful.",
             "Great lore and a gorgeous setting. Terrible pacing, so slow and boring.",
             "The universe and setting are excellent. The pacing was bad and dull."]
    rv = pd.DataFrame({"review_id": [f"r{i}" for i in range(5)], "anime_id": "x", "text": texts,
                       "score_10": [6, 5, 6, 7, 5], "source": "test", "source_url": None, "date": "2024-01-01",
                       "geography": None, "language": "en", "helpful_count": None})
    rv = review_level(rv)
    ev = extract_aspect_evidence(rv, sentiment)
    c = analyse_title("x", rv, ev, min_reviews=5, min_mentions=3)
    assert c is not None
    assert "World-building" in c.praised and "Pacing" in c.criticised
    assert any("not evidence about Indian audiences" in x for x in c.limitations)
    assert analyse_title("x", rv.head(3), ev, min_reviews=5) is None   # too few reviews
