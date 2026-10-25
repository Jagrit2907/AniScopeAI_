"""Aspect (storytelling theme) extraction from review text.

Method — transparent and rule-based, so every finding can be traced to a sentence:
  1. Split each review into sentences.
  2. A sentence mentions an aspect when it matches one of that aspect's
     keyword patterns (the taxonomy below; editable).
  3. The sentence's polarity comes from the sentiment scorer in
     ``review_analysis`` (VADER lexicon if installed, else a small built-in lexicon).
  4. Each (review, aspect, sentence, polarity) becomes one evidence row.

Limitations: keyword matching misses paraphrases and can misfire on sarcasm or
negated comparisons; polarity is per sentence, so a sentence that praises one
aspect and criticises another gets one score. Excerpts are always shown so a
reader can check the call.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

ASPECT_TAXONOMY: dict[str, dict] = {
    "Story & premise": {
        "patterns": [r"\bstory\b", r"\bstoryline\b", r"\bplot\b", r"\bpremise\b", r"\bnarrative\b", r"\bconcept\b", r"\bwriting\b"],
        "description": "Overall story, premise and narrative quality."},
    "Character development": {
        "patterns": [r"character development", r"\bcharacter arcs?\b", r"\bcharacters?\b", r"\bcast\b", r"\bdevelop(?:ed|ment)\b"],
        "description": "How characters are written and grow."},
    "Protagonist": {
        "patterns": [r"\bprotagonist\b", r"\bmain character\b", r"\bmc\b", r"\blead character\b", r"\bhero(?:ine)?\b"],
        "description": "Traits and writing of the main character."},
    "Intelligent / strategic conflict": {
        "patterns": [r"\bmind games?\b", r"\bstrateg(?:y|ic|ies)\b", r"\bintelligen(?:t|ce)\b", r"\bclever\b", r"\bgenius\b", r"\bpsychological\b", r"\bbattle of wits\b", r"\btactic"],
        "description": "Smart protagonists, strategy, psychological duels."},
    "World-building": {
        "patterns": [r"world[- ]?building", r"\blore\b", r"\bsetting\b", r"\buniverse\b", r"\bmagic system\b", r"\bworld\b"],
        "description": "Depth and consistency of the setting."},
    "Pacing": {
        "patterns": [r"\bpac(?:e|ing|ed)\b", r"\bslow\b", r"\brushed\b", r"\bdragg(?:ed|ing|s)\b", r"\bfiller\b", r"\bboring\b"],
        "description": "Speed and rhythm of the story."},
    "Emotional impact": {
        "patterns": [r"\bemotion(?:al|ally|s)?\b", r"\bcried\b", r"\btears?\b", r"\bheartbreak", r"\btouching\b", r"\bmoving\b", r"\bfeels\b"],
        "description": "Ability to make viewers feel something."},
    "Visuals & animation": {
        "patterns": [r"\banimation\b", r"\banimated\b", r"\bart ?style\b", r"\bvisuals?\b", r"\bcgi\b", r"\bcinematography\b", r"\bgorgeous\b", r"\bbeautiful(?:ly)? (?:drawn|animated)\b"],
        "description": "Animation quality and art direction."},
    "Action & fights": {
        "patterns": [r"\bfights?\b", r"\bfighting\b", r"\baction\b", r"\bbattles?\b", r"\bchoreograph"],
        "description": "Fight choreography and action scenes."},
    "Dialogue": {
        "patterns": [r"\bdialog(?:ue)?s?\b", r"\bconversations?\b", r"\blines\b", r"\bbanter\b"],
        "description": "Quality of the writing in conversations."},
    "Repetitive conflicts": {
        "patterns": [r"\brepetitive\b", r"\brepeat(?:s|ed|ing)?\b", r"\bformulaic\b", r"\bsame (?:thing|pattern|formula)\b", r"\bpredictable\b"],
        "description": "Recycled conflicts or predictable structure."},
    "Music & sound": {
        "patterns": [r"\bsoundtrack\b", r"\bost\b", r"\bmusic\b", r"\bopening\b", r"\bending song\b", r"\bvoice act", r"\bsound\b"],
        "description": "Soundtrack, songs and voice acting."},
    "Ending": {
        "patterns": [r"\bending\b", r"\bfinale\b", r"\bconclusion\b", r"\blast episode\b"],
        "description": "How the story concludes."},
    "Humour": {
        "patterns": [r"\bfunny\b", r"\bhumou?r\b", r"\bcomedy\b", r"\bhilarious\b", r"\bjokes?\b"],
        "description": "Comedy and humour."},
}

_COMPILED = {a: [re.compile(p, re.I) for p in spec["patterns"]] for a, spec in ASPECT_TAXONOMY.items()}
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(str(text)) if p and p.strip()]
    return [p for p in parts if len(p) >= 15]


def aspects_in(sentence: str) -> list[str]:
    return [a for a, pats in _COMPILED.items() if any(p.search(sentence) for p in pats)]


def extract_aspect_evidence(reviews: pd.DataFrame, scorer) -> pd.DataFrame:
    """Return one row per (review, aspect, sentence) with polarity.

    ``scorer`` is a callable str -> compound score in [-1, 1].
    """
    rows = []
    for r in reviews.itertuples(index=False):
        for sent in split_sentences(r.text):
            hits = aspects_in(sent)
            if not hits:
                continue
            compound = scorer(sent)
            polarity = "positive" if compound >= 0.25 else "negative" if compound <= -0.25 else "neutral"
            for a in hits:
                rows.append({"review_id": r.review_id, "anime_id": r.anime_id, "aspect": a,
                             "sentence": sent, "compound": round(compound, 3), "polarity": polarity,
                             "source": r.source, "source_url": r.source_url, "date": r.date})
    return pd.DataFrame(rows, columns=["review_id", "anime_id", "aspect", "sentence", "compound",
                                       "polarity", "source", "source_url", "date"])


SUMMARY_COLUMNS = ["aspect", "reviews", "mentions", "positive", "negative", "neutral", "positive_share", "stance"]


def aspect_summary_all(evidence: pd.DataFrame, min_mentions: int = 3) -> pd.DataFrame:
    """Vectorised per-(title, aspect) counts for every title at once.

    Shares are computed over positive+negative counts only. Stance needs at
    least ``min_mentions`` polar counts: >=65% positive mostly praised,
    <=35% mostly criticised, otherwise divided.
    """
    if evidence.empty:
        return pd.DataFrame(columns=["anime_id"] + SUMMARY_COLUMNS)
    keys = ["anime_id", "aspect"]
    pol = pd.crosstab([evidence["anime_id"], evidence["aspect"]], evidence["polarity"])
    for c in ("positive", "negative", "neutral"):
        if c not in pol:
            pol[c] = 0
    g = evidence.groupby(keys)
    out = pd.DataFrame({"reviews": g["review_id"].nunique(), "mentions": g.size()}).join(
        pol[["positive", "negative", "neutral"]]).reset_index()
    polar = out["positive"] + out["negative"]
    out["positive_share"] = (out["positive"] / polar.where(polar > 0)).round(2)
    out["stance"] = np.select(
        [polar < min_mentions, out["positive_share"] >= 0.65, out["positive_share"] <= 0.35],
        ["too few polar mentions", "mostly praised", "mostly criticised"], default="divided")
    return out.sort_values(["anime_id", "reviews", "mentions"], ascending=[True, False, False]).reset_index(drop=True)


def aspect_summary(evidence: pd.DataFrame, min_mentions: int = 3) -> pd.DataFrame:
    """Per-aspect counts for one title's evidence (same rules as aspect_summary_all)."""
    if evidence.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    ev = evidence.assign(anime_id="_")
    return aspect_summary_all(ev, min_mentions)[SUMMARY_COLUMNS].reset_index(drop=True)


def compact_evidence(evidence: pd.DataFrame, max_chars: int = 400) -> pd.DataFrame:
    """Reduce to one row per (review, aspect, polarity): the strongest sentence.

    Counts then mean "reviews that praise / criticise / neutrally mention this
    aspect", so a single long review cannot dominate a title's aspect stance.
    A neutral row is kept only when the review has no polar sentence for that aspect.
    """
    if evidence.empty:
        return evidence
    e = evidence.assign(_strength=evidence["compound"].abs())
    e = e.sort_values("_strength", ascending=False).drop_duplicates(["review_id", "aspect", "polarity"])
    polar = e[e["polarity"] != "neutral"][["review_id", "aspect"]].drop_duplicates()
    neutral = e[e["polarity"] == "neutral"].merge(polar, on=["review_id", "aspect"], how="left", indicator=True)
    neutral = neutral[neutral["_merge"] == "left_only"].drop(columns="_merge")
    out = pd.concat([e[e["polarity"] != "neutral"], neutral], ignore_index=True).drop(columns="_strength")
    out["sentence"] = out["sentence"].str.slice(0, max_chars)
    return out.reset_index(drop=True)
