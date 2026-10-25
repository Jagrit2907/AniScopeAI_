"""Hidden Gems & Mixed-Response Analyzer.

A title becomes a *candidate for investigation* (never "an underrated title")
when ALL of these hold:
  1. It has at least ``min_reviews`` review records (default 5).
  2. At least one aspect is "mostly praised" (>=65% of its polar mentions positive,
     with >= ``min_mentions`` polar mentions).
  3. Either at least one other aspect is "mostly criticised" or "divided", or the
     overall review reception is mixed (>=30% of reviews labelled mixed/negative).

Visibility: the catalog has no popularity field, so visibility is reported only
when India trend observations exist for the title (recent mean index). Review
volume is shown separately and labelled as evidence volume, not popularity.

The "contrast index" is EXPERIMENTAL: best praised-aspect positive share minus
worst criticised-aspect positive share (0–1). It describes how sharply reviewers
split by aspect. It has not been validated and says nothing about commercial value.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config import settings
from src.theme_extraction import aspect_summary, aspect_summary_all

NEXT_STEP_BY_ASPECT = {
    "Story & premise": "Test whether premise-led promotion (trailers, synopsis-first creatives) draws interest.",
    "Character development": "Test character-focused content: profiles, arc recaps, character polls.",
    "Protagonist": "Test protagonist-led creatives and merchandise featuring the lead.",
    "Intelligent / strategic conflict": "Test 'battle of wits' framing, puzzle or strategy community activities.",
    "World-building": "Test lore explainers, maps, art books or setting-focused collectibles.",
    "Emotional impact": "Test emotional-moment clips and watch-party style community events.",
    "Visuals & animation": "Test key-art prints, artbooks, and visual-led social content.",
    "Action & fights": "Test fight-highlight clips and action-figure style merchandise.",
    "Dialogue": "Test quote-led social content; check subtitle/dub quality expectations.",
    "Music & sound": "Test soundtrack streaming promotion and music-event formats.",
    "Ending": "Test 'complete series' binge positioning.",
    "Humour": "Test meme-friendly short-form content.",
    "Pacing": "Investigate recap or curated-episode guides to address pacing complaints.",
    "Repetitive conflicts": "Investigate which arcs reviewers single out before promoting the whole series.",
}


@dataclass
class GemCandidate:
    anime_id: str
    n_reviews: int
    praised: list[str]
    criticised: list[str]
    divided: list[str]
    mixed_share: float
    score_mean: float | None
    score_std: float | None
    contrast_index: float | None
    why: str
    limitations: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    aspects: pd.DataFrame | None = None


def analyse_title(anime_id: str, reviews: pd.DataFrame, evidence: pd.DataFrame,
                  min_reviews: int | None = None, min_mentions: int | None = None) -> GemCandidate | None:
    """``reviews`` must already carry the ``overall`` label from review_analysis.review_level."""
    min_reviews = min_reviews or settings.REVIEW_MIN_FOR_ANALYSIS
    min_mentions = min_mentions or settings.ASPECT_MIN_MENTIONS
    r = reviews[reviews["anime_id"] == anime_id]
    if len(r) < min_reviews:
        return None
    ev = evidence[evidence["anime_id"] == anime_id]
    return _build(anime_id, r, aspect_summary(ev, min_mentions))


def _build(anime_id: str, r: pd.DataFrame, summ: pd.DataFrame) -> GemCandidate | None:
    """Apply the candidate rules to one title's reviews ``r`` and aspect summary ``summ``."""
    praised = summ.loc[summ["stance"] == "mostly praised", "aspect"].tolist()
    criticised = summ.loc[summ["stance"] == "mostly criticised", "aspect"].tolist()
    divided = summ.loc[summ["stance"] == "divided", "aspect"].tolist()
    mixed_share = float(r["overall"].isin(["mixed", "negative"]).mean())
    if not praised or not (criticised or divided or mixed_share >= 0.3):
        return None

    best = summ.loc[summ["aspect"].isin(praised), "positive_share"].max()
    worst_pool = criticised or divided
    worst = summ.loc[summ["aspect"].isin(worst_pool), "positive_share"].min() if worst_pool else None
    contrast = round(float(best - worst), 2) if worst is not None and pd.notna(worst) else None

    why_parts = [f"reviewers mostly praise {', '.join(praised[:3])}"]
    if criticised:
        why_parts.append(f"while mostly criticising {', '.join(criticised[:3])}")
    elif divided:
        why_parts.append(f"while being divided on {', '.join(divided[:3])}")
    if mixed_share >= 0.3:
        why_parts.append(f"and {mixed_share:.0%} of reviews are mixed or negative overall")
    why = "In the loaded reviews, " + " ".join(why_parts) + "."

    limitations = [f"Based on {len(r)} review records from {', '.join(sorted(r['source'].fillna('unknown').astype(str).unique()))}."]
    if r["geography"].isna().all():
        limitations.append("Reviewer location is unknown: this is not evidence about Indian audiences.")
    if len(r) < 15:
        limitations.append("Small sample: a few reviews can change the aspect stances.")
    limitations.append("Aspect stances come from keyword matching and lexicon sentiment, not human coding.")
    limitations.append("Mixed response does not imply the title is underrated, and criticism is not shown to cause low popularity.")

    steps = [NEXT_STEP_BY_ASPECT[a] for a in praised[:2] if a in NEXT_STEP_BY_ASPECT]
    steps.append("Validate with an Indian audience sample before any commercial commitment.")
    sc = r["score_10"].dropna()
    return GemCandidate(anime_id, len(r), praised, criticised, divided, round(mixed_share, 2),
                        round(float(sc.mean()), 2) if len(sc) else None,
                        round(float(sc.std()), 2) if len(sc) > 1 else None,
                        contrast, why, limitations, steps, summ)


def find_candidates(reviews: pd.DataFrame, evidence: pd.DataFrame, focus_aspect: str | None = None,
                    min_reviews: int | None = None, min_mentions: int | None = None) -> list[GemCandidate]:
    """Same rules as analyse_title, computed for all titles in one vectorised pass."""
    min_reviews = min_reviews or settings.REVIEW_MIN_FOR_ANALYSIS
    min_mentions = min_mentions or settings.ASPECT_MIN_MENTIONS
    counts = reviews["anime_id"].value_counts()
    eligible = set(counts[counts >= min_reviews].index)
    if not eligible:
        return []
    ev = evidence[evidence["anime_id"].isin(eligible)]
    summ = aspect_summary_all(ev, min_mentions)
    sub = reviews[reviews["anime_id"].isin(eligible)]
    mixed = sub["overall"].isin(["mixed", "negative"]).groupby(sub["anime_id"]).mean()
    reviews_by = dict(tuple(reviews[reviews["anime_id"].isin(eligible)].groupby("anime_id", sort=False)))
    out = []
    for aid, grp in summ.groupby("anime_id", sort=False):
        praised = grp.loc[grp["stance"] == "mostly praised", "aspect"].tolist()
        if not praised or (focus_aspect and focus_aspect not in praised):
            continue
        criticised = grp.loc[grp["stance"] == "mostly criticised", "aspect"].tolist()
        divided = grp.loc[grp["stance"] == "divided", "aspect"].tolist()
        if not (criticised or divided or mixed.get(aid, 0) >= 0.3):
            continue
        c = _build(aid, reviews_by[aid], grp.drop(columns="anime_id").reset_index(drop=True))
        if c is not None:
            out.append(c)
    return sorted(out, key=lambda c: (c.contrast_index or 0, c.n_reviews), reverse=True)
