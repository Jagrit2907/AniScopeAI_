import pandas as pd

from src.trend_analysis import candidate_table, level_vs_momentum, series_growth


def weekly(values, start="2025-01-05", anime_id="a", query="q", geo="India"):
    dates = pd.date_range(start, periods=len(values), freq="7D")
    return pd.DataFrame({"anime_id": anime_id, "query": query, "geo": geo, "date": dates, "value": values})


def test_growth_windows_and_percent():
    s = weekly([10] * 12 + [20] * 12)
    r = series_growth(s, window_weeks=12, min_points=6)
    assert r.baseline_mean == 10 and r.recent_mean == 20
    assert r.abs_change == 10 and r.pct_change == 100
    assert r.recent_n == 12 and r.baseline_n == 12 and r.reliability == "sufficient"


def test_zero_baseline_has_no_percent():
    r = series_growth(weekly([0] * 12 + [5] * 12), 12, 6)
    assert r.abs_change == 5 and r.pct_change is None
    assert any("undefined" in x for x in r.reasons)


def test_short_history_is_insufficient():
    r = series_growth(weekly([5, 6, 7]), 12, 6)
    assert r.reliability == "insufficient"


def test_missing_weeks_are_not_filled():
    s = weekly([10] * 24)
    s = s.drop(index=range(14, 22))          # remove 8 weeks inside the recent window
    r = series_growth(s, 12, 6)
    assert r.recent_n == 4 and r.reliability == "insufficient"


def test_candidate_table_geo_filter_and_quadrants():
    t = pd.concat([weekly([10] * 12 + [30] * 12, anime_id="a", query="A"),
                   weekly([60] * 24, anime_id="b", query="B"),
                   weekly([5] * 24, anime_id="c", query="C", geo="Japan")])
    table, results = candidate_table(t, 12, geo_filter="India")
    assert set(table["anime_id"]) == {"a", "b"}
    q = level_vs_momentum(table).set_index("anime_id")["quadrant"]
    assert q["a"] == "Emerging: lower level, rising"


def test_monthly_series_uses_month_windows():
    dates = pd.date_range("2021-10-01", periods=61, freq="MS")
    vals = [10] * 49 + [10] * 6 + [20] * 6          # last 6 months doubled vs the 6 before
    s = pd.DataFrame({"anime_id": "a", "query": "q", "geo": "India", "date": dates, "value": vals})
    r = series_growth(s)
    assert r.frequency == "monthly"
    assert r.recent_n == 6 and r.baseline_n == 6
    assert r.recent_mean == 20 and r.baseline_mean == 10 and r.reliability == "sufficient"
    assert r.recent_window[0] == pd.Timestamp("2026-05-01")
