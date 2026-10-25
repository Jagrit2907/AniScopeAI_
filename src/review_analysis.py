"""Review-level sentiment and per-title evidence summaries.

Sentiment method: VADER (Hutto & Gilbert, 2014), a published rule-based
lexicon for English social text, used as-is — AniScope does not train a model.
If ``vaderSentiment`` is not installed a small built-in lexicon is used and the
UI says so. Neither has been evaluated on anime reviews by this project, so no
accuracy figure is claimed.
"""
from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER = SentimentIntensityAnalyzer()
    METHOD = "VADER lexicon (vaderSentiment), rule-based, English; not trained or evaluated by AniScope"
except Exception:  # noqa: BLE001 - optional dependency
    _VADER = None
    METHOD = "Built-in mini lexicon (fallback; install vaderSentiment for better coverage)"

_POS = {"good", "great", "excellent", "amazing", "brilliant", "love", "loved", "beautiful", "best", "masterpiece",
        "enjoyed", "fantastic", "clever", "compelling", "engaging", "well", "perfect", "strong", "fun", "gorgeous"}
_NEG = {"bad", "boring", "worst", "terrible", "awful", "weak", "slow", "rushed", "dull", "annoying", "poor",
        "hate", "hated", "mess", "disappointing", "repetitive", "predictable", "bland", "forgettable", "waste"}
_NEGATORS = {"not", "never", "no", "isn't", "wasn't", "don't", "didn't", "hardly"}


def _fallback(text: str) -> float:
    words = re.findall(r"[a-z']+", text.lower())
    score = 0
    for i, w in enumerate(words):
        sign = 1 if w in _POS else -1 if w in _NEG else 0
        if sign and i > 0 and words[i - 1] in _NEGATORS:
            sign = -sign
        score += sign
    return max(-1.0, min(1.0, score / 3.0))


@lru_cache(maxsize=50_000)
def sentiment(text: str) -> float:
    """Compound polarity in [-1, 1]."""
    if _VADER is not None:
        return float(_VADER.polarity_scores(text)["compound"])
    return _fallback(text)


def review_level(reviews: pd.DataFrame) -> pd.DataFrame:
    """Add a whole-review polarity label.

    If the review carries the author's own score, that is preferred
    (>=7 positive, <=4 negative, else mixed) because it is the reviewer's own
    judgement; otherwise the text compound score is used.
    """
    out = reviews.copy()
    # Whole-text sentiment is only needed when the reviewer gave no score (it is the slow step).
    out["text_compound"] = pd.Series([sentiment(str(t)[:5000]) if pd.isna(s) else float("nan")
                                      for t, s in zip(out["text"], out["score_10"])], index=out.index, dtype="float64")

    def label(row) -> str:
        s = row["score_10"]
        if pd.notna(s):
            return "positive" if s >= 7 else "negative" if s <= 4 else "mixed"
        c = row["text_compound"]
        return "positive" if c >= 0.5 else "negative" if c <= -0.2 else "mixed"
    out["overall"] = out.apply(label, axis=1) if len(out) else pd.Series(dtype=str)
    out["overall_basis"] = out["score_10"].map(lambda s: "reviewer score" if pd.notna(s) else "text sentiment")
    return out


def evidence_overview(reviews: pd.DataFrame) -> dict:
    """Factual description of the evidence available for one title."""
    if reviews.empty:
        return {"records": 0}
    dates = pd.to_datetime(reviews["date"], errors="coerce")
    return {
        "records": int(len(reviews)),
        "sources": sorted(reviews["source"].fillna("unknown").astype(str).unique().tolist()),
        "date_min": None if dates.isna().all() else dates.min().date(),
        "date_max": None if dates.isna().all() else dates.max().date(),
        "undated": int(dates.isna().sum()),
        "languages": sorted(reviews["language"].dropna().astype(str).unique().tolist()),
        "with_geography": int(reviews["geography"].notna().sum()),
        "india_tagged": int(reviews["geography"].fillna("").str.lower().str.contains("india").sum()),
        "with_score": int(reviews["score_10"].notna().sum()),
        "score_mean": None if reviews["score_10"].isna().all() else round(float(reviews["score_10"].mean()), 2),
        "score_std": None if reviews["score_10"].notna().sum() < 2 else round(float(reviews["score_10"].std()), 2),
    }


def excerpt(text: str, max_chars: int = 320) -> str:
    """Shorten verbatim text at a word boundary; an ellipsis marks the cut."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + " …"
