"""Persistent store for validated evidence (CSV files in data/processed)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import settings
from src.data_validation import REVIEW_COLUMNS, TREND_COLUMNS, ImportReport


def _read(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(path, dtype={"anime_id": str, "review_id": str}, encoding="utf-8")
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame(columns=columns)
    for c in columns:
        if c not in df.columns:
            df[c] = None
    return df[columns]


def load_trends(path: Path | None = None) -> pd.DataFrame:
    df = _read(path or settings.TREND_STORE, TREND_COLUMNS)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["below_one"] = df["below_one"].astype(str).str.lower().eq("true")
    return df.dropna(subset=["date", "value", "anime_id"])


def load_reviews(path: Path | None = None) -> pd.DataFrame:
    df = _read(path or settings.REVIEW_STORE, REVIEW_COLUMNS)
    df["score_10"] = pd.to_numeric(df["score_10"], errors="coerce")
    df["helpful_count"] = pd.to_numeric(df["helpful_count"], errors="coerce")
    return df.dropna(subset=["text", "anime_id"])


def _append(path: Path, new: pd.DataFrame, columns: list[str], key: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read(path, columns)
    combined = pd.concat([existing.astype(str), new[columns].astype(str)], ignore_index=True)
    combined = combined.replace({"nan": "", "None": "", "NaT": ""})
    combined = combined.drop_duplicates(subset=key, keep="last")
    combined.to_csv(path, index=False, encoding="utf-8")
    return len(combined)


def save_trends(new: pd.DataFrame, path: Path | None = None) -> int:
    return _append(path or settings.TREND_STORE, new, TREND_COLUMNS, ["anime_id", "geo", "date", "query"])


def save_reviews(new: pd.DataFrame, path: Path | None = None) -> int:
    return _append(path or settings.REVIEW_STORE, new, REVIEW_COLUMNS, ["review_id"])


def clear_store(kind: str) -> None:
    path = settings.TREND_STORE if kind == "trend" else settings.REVIEW_STORE
    if path.exists():
        path.unlink()
    log_import({"kind": kind, "file": "(cleared by user)", "rows_valid": 0, "rows_read": 0, "rejected": {}})


def log_import(entry: ImportReport | dict, path: Path | None = None) -> None:
    path = path or settings.IMPORT_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    log = read_import_log(path)
    log.append(entry.to_dict() if isinstance(entry, ImportReport) else entry)
    path.write_text(json.dumps(log[-200:], indent=2, ensure_ascii=False), encoding="utf-8")


def read_import_log(path: Path | None = None) -> list[dict]:
    path = path or settings.IMPORT_LOG
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
