"""Review-sentiment classifier: TF-IDF + logistic regression (scikit-learn). Prototype.

What the labels mean
    The model learns to predict a RATING-DERIVED category from review text:
    negative = reviewer score 1-4, mixed = 5-6, positive = 7-10 (the bands
    src/review_analysis.review_level already uses). These are not human sentiment
    annotations; a score and the tone of its text can disagree.

Leakage control
    * The score table the Kaggle dump puts at the start of each text
      ("Overall 8 Story 7 ...") is stripped, since it reveals the label.
    * Exact duplicate texts are removed before splitting.
    * The split is by TITLE (anime_uid): every review of a title is either in
      training or in the test set, so the test measures performance on unseen
      titles and title-specific wording cannot leak across. anime_uid is used only
      for grouping, never as a feature. Near-duplicate texts across different
      titles (e.g. one user reposting) are NOT detected.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from config import settings
from src.data_validation import clean_review_text

LABELS = ["negative", "mixed", "positive"]
MODEL_FILE, META_FILE, REPORT_FILE = "model.joblib", "metadata.json", "evaluation.md"
MAX_CHARS = 5_000            # long reviews are truncated for features
MIN_CHARS = 40               # same minimum the review importer uses
MAX_INPUT_CHARS = 20_000     # API input limit
LABEL_NOTE = ("Labels come from reviewers' own 1-10 scores (negative 1-4, mixed 5-6, positive 7-10). "
              "The model predicts that rating-derived category from text; it is not a verified human sentiment label.")
_TABLE_TERM = re.compile(r"\b(?:overall|story|animation|sound|character|enjoyment)\s*:?\s*\d{1,2}\b", re.I)


# ------------------------------------------------------------------ text and labels
def prepare_text(raw, max_chars: int | None = MAX_CHARS) -> str | None:
    """Importer's cleaning + removal of a leftover score table + whitespace collapse + truncation."""
    t = clean_review_text(raw)
    if not t:
        return None
    head = t[:400]
    if len(_TABLE_TERM.findall(head)) >= 3:
        t = _TABLE_TERM.sub(" ", head) + t[400:]
    t = re.sub(r"^\s*more pics\b", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:max_chars] if max_chars else t) or None


def label_for(score) -> str | None:
    """Integer score 1-10 → label; anything else → None (excluded)."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(s) or s != round(s) or not 1 <= s <= 10:
        return None
    return "negative" if s <= 4 else "mixed" if s <= 6 else "positive"


def _unit(text: str) -> float:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def in_test_set(group: str, seed: int, test_share: float) -> bool:
    """Seeded, reproducible title-level split."""
    return _unit(f"{seed}:{group}") < test_share


# ------------------------------------------------------------------ training data
def load_training_data(path: Path, chunksize: int = 5_000,
                       progress: Callable[[int], None] | None = None) -> tuple[pd.DataFrame, dict]:
    """Stream a Kaggle-style reviews.csv. Reads only uid, anime_uid (grouping), text and score.
    The file is never modified. Returns (frame[text, label, group], stats)."""
    cols = {"uid", "anime_uid", "text", "score"}
    stats: Counter = Counter()
    seen_uid: set = set()
    seen_text: set = set()
    texts, labels, groups = [], [], []
    for chunk in pd.read_csv(path, usecols=lambda c: c in cols, dtype=str, chunksize=chunksize,
                             on_bad_lines="skip", encoding="utf-8", encoding_errors="replace"):
        missing = {"text", "score"} - set(chunk.columns)
        if missing:
            raise ValueError(f"reviews file is missing column(s): {', '.join(sorted(missing))}")
        for col in ("uid", "anime_uid"):
            if col not in chunk:
                chunk[col] = None
        stats["rows_read"] += len(chunk)
        for uid, group, raw, score in zip(chunk["uid"], chunk["anime_uid"], chunk["text"], chunk["score"]):
            if isinstance(uid, str):
                if uid in seen_uid:
                    stats["duplicate_review_id"] += 1
                    continue
                seen_uid.add(uid)
            label = label_for(pd.to_numeric(score, errors="coerce"))
            if label is None:
                stats["invalid_or_missing_score"] += 1
                continue
            text = prepare_text(raw, max_chars=None)
            if not text or len(text) < MIN_CHARS:
                stats["missing_or_short_text"] += 1
                continue
            key = hashlib.md5(text.lower().encode("utf-8")).hexdigest()
            if key in seen_text:
                stats["duplicate_text"] += 1
                continue
            seen_text.add(key)
            texts.append(text[:MAX_CHARS])
            labels.append(label)
            groups.append(group if isinstance(group, str) and group.strip() else f"review:{key}")
        if progress:
            progress(stats["rows_read"])
    frame = pd.DataFrame({"text": texts, "label": labels, "group": groups})
    out = {k: int(v) for k, v in stats.items()}
    out.update(usable=len(frame), titles=int(frame["group"].nunique()) if len(frame) else 0,
               label_distribution={lab: int((frame["label"] == lab).sum()) for lab in LABELS} if len(frame) else {})
    return frame, out


# ------------------------------------------------------------------ train and evaluate
def build_model(seed: int = 42, min_df: int = 3):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    return Pipeline([
        ("tfidf", TfidfVectorizer(lowercase=True, strip_accents="unicode", ngram_range=(1, 2), min_df=min_df,
                                  max_df=0.9, max_features=200_000, sublinear_tf=True, dtype=np.float32)),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed)),
    ])


def evaluate(y_true, y_pred) -> dict:
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
    y_true, y_pred = list(y_true), list(y_pred)
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    return {"n": len(y_true),
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "macro_f1": round(float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)), 4),
            "per_class": {lab: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                                "f1": round(float(f[i]), 4), "support": int(s[i])} for i, lab in enumerate(LABELS)},
            "confusion_matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist()}


def train_and_evaluate(frame: pd.DataFrame, seed: int = 42, test_share: float = 0.2, min_df: int = 3,
                       log: Callable[[str], None] = print) -> tuple[object, dict]:
    """Split by title, fit TF-IDF and the classifier on the training side only, evaluate on the rest."""
    test_mask = frame["group"].map(lambda g: in_test_set(g, seed, test_share))
    train, test = frame[~test_mask], frame[test_mask]
    missing = [lab for lab in LABELS if lab not in set(train["label"])]
    if missing or test.empty:
        raise ValueError(f"Not enough data to train (classes missing from training: {missing or 'none'}; test rows: {len(test)}).")
    log(f"Training on {len(train):,} reviews ({train['group'].nunique():,} titles); "
        f"testing on {len(test):,} reviews from {test['group'].nunique():,} other titles …")
    model = build_model(seed, min_df)
    model.fit(train["text"].tolist(), train["label"].tolist())
    majority = train["label"].value_counts().idxmax()
    meta = {
        "model_id": f"tfidf-logreg-{datetime.now(timezone.utc):%Y%m%d-%H%M}",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "algorithm": "TF-IDF (word 1-2 grams) + logistic regression (class_weight=balanced)",
        "labels": LABELS, "label_note": LABEL_NOTE,
        "split": {"method": "by title (anime_uid), seeded hash", "seed": seed, "test_share": test_share,
                  "train_reviews": int(len(train)), "test_reviews": int(len(test)),
                  "train_titles": int(train["group"].nunique()), "test_titles": int(test["group"].nunique()),
                  "train_distribution": {lab: int((train["label"] == lab).sum()) for lab in LABELS},
                  "test_distribution": {lab: int((test["label"] == lab).sum()) for lab in LABELS}},
        "test_metrics": evaluate(test["label"], model.predict(test["text"].tolist())),
        "majority_baseline": {"predicts": majority, **evaluate(test["label"], [majority] * len(test))},
    }
    return model, meta


# ------------------------------------------------------------------ save / load / predict
def save(model, meta: dict, out_dir: Path | None = None) -> Path:
    import joblib
    out_dir = Path(out_dir or settings.ML_MODEL_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / (MODEL_FILE + ".tmp")
    joblib.dump(model, tmp, compress=3)
    tmp.replace(out_dir / MODEL_FILE)
    (out_dir / META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out_dir / REPORT_FILE).write_text(report_markdown(meta), encoding="utf-8")
    return out_dir


def report_markdown(meta: dict) -> str:
    m, b, sp, d = meta["test_metrics"], meta["majority_baseline"], meta["split"], meta.get("data", {})
    lines = [f"# Sentiment model evaluation — {meta['model_id']}", "", f"{meta['algorithm']}. Trained {meta['created_at']}.", "",
             f"> {LABEL_NOTE}", ""]
    if d:
        lines += [f"**Data:** {d.get('file')} — {d.get('rows_read', 0):,} rows read, {d.get('usable', 0):,} usable from "
                  f"{d.get('titles', 0):,} titles. Dropped: invalid/missing score {d.get('invalid_or_missing_score', 0):,}, "
                  f"missing/short text {d.get('missing_or_short_text', 0):,}, duplicate id {d.get('duplicate_review_id', 0):,}, "
                  f"duplicate text {d.get('duplicate_text', 0):,}.", ""]
    lines += [f"**Split:** {sp['method']} (seed {sp['seed']}, {sp['test_share']:.0%} of titles held out) — "
              f"train {sp['train_reviews']:,} reviews / {sp['train_titles']:,} titles, test {sp['test_reviews']:,} reviews / {sp['test_titles']:,} titles.",
              f"Train classes {sp['train_distribution']} · test classes {sp['test_distribution']}.", "",
              "## Held-out test results", "", "| | Accuracy | Macro F1 |", "|---|---|---|",
              f"| Trained model | {m['accuracy']:.3f} | {m['macro_f1']:.3f} |",
              f"| Majority baseline (always '{b['predicts']}') | {b['accuracy']:.3f} | {b['macro_f1']:.3f} |", "",
              "| Class | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    lines += [f"| {lab} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} | {v['support']:,} |" for lab, v in m["per_class"].items()]
    lines += ["", "Confusion matrix (rows = true, columns = predicted):", "", "| | " + " | ".join(LABELS) + " |", "|---|---|---|---|"]
    lines += [f"| {lab} | " + " | ".join(f"{x:,}" for x in row) + " |" for lab, row in zip(LABELS, m["confusion_matrix"])]
    lines += ["", "## Limitations",
              "- Rating-derived labels, not human sentiment annotations.",
              "- Title-level split; near-duplicate texts across titles are not detected.",
              "- International MyAnimeList reviews with unknown reviewer location: not Indian audience sentiment.",
              "- Bag-of-words: no sarcasm, cross-sentence negation or aspect awareness."]
    return "\n".join(lines) + "\n"


class ModelUnavailable(RuntimeError):
    """No usable trained model on disk."""


_lock = threading.Lock()
_cache: dict = {}


def load(model_dir: Path | None = None):
    """Load once; reload only if the files change."""
    d = Path(model_dir or settings.ML_MODEL_DIR)
    try:
        stamp = (str(d), (d / MODEL_FILE).stat().st_mtime, (d / META_FILE).stat().st_mtime)
    except OSError:
        raise ModelUnavailable("No trained sentiment model found. Train it with: python scripts/train_sentiment.py") from None
    with _lock:
        if _cache.get("stamp") != stamp:
            try:
                import joblib
                model = joblib.load(d / MODEL_FILE)
                meta = json.loads((d / META_FILE).read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001 - corrupt or incompatible artifact
                raise ModelUnavailable(f"The saved model could not be loaded ({type(e).__name__}). Retrain it.") from e
            if sorted(model.classes_) != sorted(LABELS):
                raise ModelUnavailable("The saved model has unexpected classes. Retrain it.")
            _cache.update(stamp=stamp, model=model, meta=meta)
        return _cache["model"], _cache["meta"]


def _probabilities(model, texts: list[str]) -> np.ndarray:
    """Rows of probabilities in LABELS order."""
    probs = model.predict_proba(texts)
    order = [list(model.classes_).index(lab) for lab in LABELS]
    return probs[:, order]


def predict_text(text, model_dir: Path | None = None) -> dict:
    """One prediction. ValueError for unusable input; ModelUnavailable if there is no model."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text is empty.")
    if len(text) > MAX_INPUT_CHARS:
        raise ValueError(f"Text is longer than {MAX_INPUT_CHARS:,} characters.")
    prepared = prepare_text(text)
    if not prepared:
        raise ValueError("Text has no readable words after cleaning.")
    model, meta = load(model_dir)
    p = _probabilities(model, [prepared])[0]
    probs = {lab: round(float(v), 4) for lab, v in zip(LABELS, p)}
    label = max(probs, key=probs.get)
    known = int(model.named_steps["tfidf"].transform([prepared]).nnz)
    out = {"label": label, "probabilities": probs, "model_id": meta["model_id"], "known_terms": known}
    if known == 0:
        out["warning"] = "None of these words were seen in training; the prediction only reflects class balance."
    return out


def predict_reviews(texts: list[str], model_dir: Path | None = None) -> dict | None:
    """Prediction for a title's stored reviews: mean class probabilities and per-review label counts."""
    prepared = [t for t in (prepare_text(x) for x in texts) if t]
    if not prepared:
        return None
    model, meta = load(model_dir)
    p = _probabilities(model, prepared)
    mean = {lab: round(float(v), 4) for lab, v in zip(LABELS, p.mean(axis=0))}
    picks = p.argmax(axis=1)
    return {"label": max(mean, key=mean.get), "probabilities": mean, "n": len(prepared),
            "counts": {lab: int((picks == i).sum()) for i, lab in enumerate(LABELS)}, "model_id": meta["model_id"]}
