"""Shared fixtures. All data here is SYNTHETIC test data for unit tests only."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_loader import standardize_catalog  # noqa: E402


@pytest.fixture
def catalog():
    raw = pd.DataFrame({
        "title": ["Test Alpha", "Test Beta", "Test Beta", "Gamma Show", None],
        "synonyms": ["Alpha Alt | TA", "", "", '["Gamma"]', ""],
        "type": ["TV", "TV", "MOVIE", "ONA", "TV"],
        "year": [2020, 2021, 2022, None, 2020],
        "episodes": [12, 24, 1, None, 3],
        "sources": ["https://myanimelist.net/anime/1 | https://anilist.co/anime/11",
                    "https://myanimelist.net/anime/2", "https://myanimelist.net/anime/3",
                    "https://anilist.co/anime/44", ""],
        "tags": ["action | drama", "comedy", "", "mystery", ""],
        "score": [7.5, None, 6.0, 8.1, None],
    })
    df, *_ = standardize_catalog(raw)
    return df
