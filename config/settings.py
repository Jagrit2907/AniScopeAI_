"""Central configuration for AniScope AI.

Every path can be overridden without editing code:

1. Environment variable ``ANISCOPE_DATA_DIR`` (highest priority), or
2. a ``.env`` file in the project root containing ``ANISCOPE_DATA_DIR=...``, or
3. the default ``<project>/data/raw``.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env reader (KEY=VALUE lines) so python-dotenv is not required."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_DOTENV = _read_dotenv(PROJECT_ROOT / ".env")


def get_setting(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or _DOTENV.get(name) or default


def _resolve(path_value: str | None, default: Path) -> Path:
    if not path_value:
        return default
    p = Path(os.path.expandvars(os.path.expanduser(path_value)))
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


# Where the raw catalog / templates / manifest live.
RAW_DATA_DIR = _resolve(get_setting("ANISCOPE_DATA_DIR"), PROJECT_ROOT / "data" / "raw")
# Where AniScope stores validated, imported evidence.
PROCESSED_DIR = _resolve(get_setting("ANISCOPE_PROCESSED_DIR"), PROJECT_ROOT / "data" / "processed")
# Where workspace state (saved concepts, plans, briefs) is persisted.
DATABASE_DIR = _resolve(get_setting("ANISCOPE_DATABASE_DIR"), PROJECT_ROOT / "data" / "database")

TREND_STORE = PROCESSED_DIR / "trend_observations.csv"
REVIEW_STORE = PROCESSED_DIR / "review_evidence.csv"
IMPORT_LOG = PROCESSED_DIR / "import_log.json"
WORKSPACE_FILE = DATABASE_DIR / "workspace.json"

# Trained sentiment model (TF-IDF + logistic regression), written by scripts/train_sentiment.py.
ML_MODEL_DIR = _resolve(get_setting("ANISCOPE_MODEL_DIR"), PROJECT_ROOT / "models" / "sentiment")

# File names the catalog loader looks for, in order of preference.
# The CSV comes first: the AniScope export adds a stable aniscope_catalog_id that
# the evidence templates use, while the JSONL is the raw upstream record without it.
CATALOG_CANDIDATES = [
    "anime_catalog_all_titles.csv",
    "anime_catalog_all_titles.jsonl",
    "anime-offline-database.json",
    "anime-offline-database-minified.json",
]
MANIFEST_NAME = "dataset_manifest.json"
TREND_TEMPLATE_NAME = "trend_observations_template.csv"
# Optional 2020 MyAnimeList snapshot (Kaggle "Anime Dataset with Reviews", marlesson):
VISIBILITY_FILE_NAMES = ["animes.csv"]
KAGGLE_REVIEWS_FILE_NAMES = ["reviews.csv"]
REVIEW_TEMPLATE_NAME = "review_evidence_template.csv"

# ---- Analytical thresholds (documented in README "Methods") -------------
TREND_WINDOW_WEEKS = 12          # recent window vs preceding window of equal length
TREND_MIN_POINTS_PER_WINDOW = 6  # below this a (weekly) window is "insufficient"
TREND_WINDOW_MONTHS = 6          # window for monthly data (e.g. 5-year Google Trends exports)
REVIEW_MIN_FOR_ANALYSIS = 5      # minimum review records for a title-level finding
ASPECT_MIN_MENTIONS = 3          # minimum mentions before an aspect is summarised

APP_VERSION = "0.1.0"
