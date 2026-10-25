"""Trend momentum from dated observations.

Method (shown in the UI):
  * Each title's observations are grouped by query + geography (one series).
  * The latest observation date defines the end of the "recent" window.
  * Recent window = the last W weeks; baseline window = the W weeks before it.
  * Growth = mean(recent) − mean(baseline), in index points.
  * Percent change is only reported when mean(baseline) > 0.
  * A window with fewer than ``min_points`` observations is "insufficient";
    missing weeks are never filled in or treated as zero.

Google Trends values are relative 0–100 indices within one export. Comparing
series from different exports is only valid if they were exported together or
rescaled to a shared anchor term; the UI warns about this.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import settings


MIN_BASELINE_FOR_PCT = 1.0  # index points; below this a % change is not reported


@dataclass
class GrowthResult:
    anime_id: str
    query: str
    geo: str | None
    n_obs: int
    first_date: pd.Timestamp
    last_date: pd.Timestamp
    latest_value: float
    recent_mean: float | None
    baseline_mean: float | None
    abs_change: float | None
    pct_change: float | None
    recent_n: int
    baseline_n: int
    recent_window: tuple[pd.Timestamp, pd.Timestamp]
    baseline_window: tuple[pd.Timestamp, pd.Timestamp]
    zero_share: float
    frequency: str
    reliability: str          # "sufficient" | "limited" | "insufficient"
    reasons: list[str]

    def as_row(self) -> dict:
        return {
            "anime_id": self.anime_id, "query": self.query, "geo": self.geo or "unspecified",
            "latest_value": self.latest_value,
            "recent_mean": None if self.recent_mean is None else round(self.recent_mean, 1),
            "baseline_mean": None if self.baseline_mean is None else round(self.baseline_mean, 1),
            "abs_change": None if self.abs_change is None else round(self.abs_change, 1),
            "pct_change": None if self.pct_change is None else round(self.pct_change, 1),
            "observations": self.n_obs, "first_date": self.first_date.date(),
            "last_date": self.last_date.date(), "zero_share": round(self.zero_share, 2),
            "frequency": self.frequency, "recent_n": self.recent_n, "baseline_n": self.baseline_n,
            "reliability": self.reliability,
        }


def detect_frequency(dates: pd.Series) -> str:
    """'monthly' when the median gap between observations is >= 25 days, else 'weekly'."""
    d = pd.Series(sorted(pd.to_datetime(dates).dropna().unique()))
    if len(d) < 2:
        return "weekly"
    return "monthly" if d.diff().dt.days.median() >= 25 else "weekly"


def series_growth(series: pd.DataFrame, window_weeks: int | None = None,
                  min_points: int | None = None, window_months: int | None = None) -> GrowthResult:
    """``series`` holds one title+query+geo: columns anime_id, query, geo, date, value.

    Weekly data: windows of ``window_weeks`` weeks. Monthly data (e.g. 5-year
    Google Trends exports): windows of ``window_months`` calendar months
    (default 6); a window needs >= 75% of its expected months to be sufficient.
    """
    s = series.dropna(subset=["date", "value"]).sort_values("date")
    first = s.iloc[0]
    end = s["date"].max()
    freq = detect_frequency(s["date"])
    if freq == "monthly":
        window_months = window_months or settings.TREND_WINDOW_MONTHS
        expected = window_months
        min_points = min_points or max(2, math.ceil(0.75 * window_months))
        recent_start = (end - pd.DateOffset(months=window_months - 1)).normalize().replace(day=1)
        base_start = recent_start - pd.DateOffset(months=window_months)
        base_end = recent_start - pd.Timedelta(days=1)
    else:
        window_weeks = window_weeks or settings.TREND_WINDOW_WEEKS
        expected = window_weeks
        min_points = min_points or settings.TREND_MIN_POINTS_PER_WINDOW
        recent_start = end - pd.Timedelta(weeks=window_weeks) + pd.Timedelta(days=1)
        base_end = recent_start - pd.Timedelta(days=1)
        base_start = recent_start - pd.Timedelta(weeks=window_weeks)
    recent = s[(s["date"] >= recent_start) & (s["date"] <= end)]["value"]
    base = s[(s["date"] >= base_start) & (s["date"] <= base_end)]["value"]

    reasons: list[str] = []
    recent_mean = float(recent.mean()) if len(recent) else None
    base_mean = float(base.mean()) if len(base) else None
    abs_change = pct = None
    if recent_mean is not None and base_mean is not None:
        abs_change = recent_mean - base_mean
        if base_mean >= MIN_BASELINE_FOR_PCT:
            pct = abs_change / base_mean * 100.0
        elif base_mean > 0:
            reasons.append(f"Baseline average is {base_mean:.1f} index points (below {MIN_BASELINE_FOR_PCT}); "
                           "a percentage change would exaggerate tiny movements, so it is not reported.")
        else:
            reasons.append("Baseline average is 0, so a percentage change is undefined.")
    if len(recent) < min_points:
        reasons.append(f"Recent window has {len(recent)} observations (minimum {min_points}).")
    if len(base) < min_points:
        reasons.append(f"Baseline window has {len(base)} observations (minimum {min_points}).")
    in_windows = pd.concat([recent, base])
    zero_share = float((in_windows == 0).mean()) if len(in_windows) else 1.0
    if zero_share > 0.5:
        reasons.append(f"{zero_share:.0%} of observations in the two windows are 0 or '<1' — search volume was often "
                       "below Google's reporting threshold.")

    if len(recent) < min_points or len(base) < min_points or abs_change is None:
        reliability = "insufficient"
    elif zero_share > 0.5 or len(recent) < 0.75 * expected:
        # Fewer points than ~75% of the window suggests gaps in the data.
        reliability = "limited"
    else:
        reliability = "sufficient"

    geo = s["geo"].dropna().iloc[0] if s["geo"].notna().any() else None
    return GrowthResult(
        anime_id=str(first["anime_id"]), query=str(first.get("query", "")), geo=geo,
        n_obs=len(s), first_date=s["date"].min(), last_date=end,
        latest_value=float(s.iloc[-1]["value"]), recent_mean=recent_mean, baseline_mean=base_mean,
        abs_change=abs_change, pct_change=pct, recent_n=len(recent), baseline_n=len(base),
        recent_window=(recent_start, end), baseline_window=(base_start, base_end),
        zero_share=zero_share, frequency=freq, reliability=reliability, reasons=reasons)


def candidate_table(trends: pd.DataFrame, window_weeks: int | None = None,
                    geo_filter: str | None = None, start=None, end=None,
                    window_months: int | None = None) -> tuple[pd.DataFrame, list[GrowthResult]]:
    """One row per title/query/geo series, computed only from observations in the date filter."""
    if trends.empty:
        return pd.DataFrame(), []
    t = trends
    if geo_filter:
        t = t[t["geo"].fillna("").str.lower() == geo_filter.lower()]
    if start is not None:
        t = t[t["date"] >= pd.Timestamp(start)]
    if end is not None:
        t = t[t["date"] <= pd.Timestamp(end)]
    results = []
    for _, grp in t.groupby(["anime_id", "query", t["geo"].fillna("")], sort=False):
        if len(grp):
            results.append(series_growth(grp, window_weeks, window_months=window_months))
    if not results:
        return pd.DataFrame(), []
    table = pd.DataFrame([r.as_row() for r in results])
    return table, results


def explain(r: GrowthResult) -> str:
    """Plain-language, data-grounded explanation of one series."""
    fmt = "%b %Y" if r.frequency == "monthly" else "%d %b %Y"
    rw = f"{r.recent_window[0]:{fmt}} – {r.recent_window[1]:{fmt}}"
    bw = f"{r.baseline_window[0]:{fmt}} – {r.baseline_window[1]:{fmt}}"
    where = f"in {r.geo}" if r.geo else "(geography not specified)"
    if r.abs_change is None:
        return (f"Observed index for '{r.query}' {where}: {r.n_obs} observations. "
                f"Not enough data in both windows to compare ({r.recent_n} recent, {r.baseline_n} baseline).")
    direction = "rose" if r.abs_change > 0 else "fell" if r.abs_change < 0 else "was unchanged"
    pct = f" ({r.pct_change:+.0f}%)" if r.pct_change is not None else ""
    return (f"Measured: the average search-interest index for '{r.query}' {where} {direction} from "
            f"{r.baseline_mean:.1f} ({bw}, n={r.baseline_n}) to {r.recent_mean:.1f} ({rw}, n={r.recent_n}), "
            f"a change of {r.abs_change:+.1f} points{pct}. This is a relative index, not a count of viewers or buyers.")


def level_vs_momentum(table: pd.DataFrame) -> pd.DataFrame:
    """Quadrant labels separating visibility (level) from growth (momentum).

    Level = recent mean index; split at the median of the compared titles.
    Only meaningful when the series share a scale (same export or anchor-rescaled).
    """
    t = table.dropna(subset=["recent_mean", "abs_change"]).copy()
    if t.empty:
        return t
    med = float(np.median(t["recent_mean"]))
    t["quadrant"] = np.select(
        [(t["recent_mean"] < med) & (t["abs_change"] > 0), (t["recent_mean"] >= med) & (t["abs_change"] > 0),
         (t["recent_mean"] >= med) & (t["abs_change"] <= 0)],
        ["Emerging: lower level, rising", "Established and rising", "High level, flat or falling"],
        default="Lower level, flat or falling")
    return t
