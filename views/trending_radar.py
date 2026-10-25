"""Screen 2 — Trending Radar: observed attention level vs growth momentum."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import Shinigami
from components.styles import PLOT_COLORS, empty_state, label, page_header
from components.widgets import title_picker
from config import settings
from src import app_data, catalog_service, evidence_store, pipeline, state
from src.data_validation import (TREND_FIELD_ALIASES, guess_mapping, parse_google_trends_export,
                                 read_csv_bytes, validate_trends)
from src.trend_analysis import candidate_table, detect_frequency, explain, level_vs_momentum

page_header("Audience discovery", "Trending Radar",
            "Which titles show growing search attention? Visibility (level) and momentum (growth) are measured separately.")

df = app_data.catalog()
if df is None:
    empty_state("Catalog not loaded", "<p>Open the Command Center for setup instructions.</p>")
    st.stop()
matcher = app_data.matcher()
trends = app_data.trends()
names = dict(zip(df["anime_id"], df.apply(catalog_service.label, axis=1)))


# ---------------------------------------------------------------- import ----
def import_panel() -> None:
    st.markdown("**Import trend observations (CSV)**")
    st.caption("Recommended source: Google Trends → Explore → region **India** → compare up to 5 titles (keep one fixed "
               "anchor title in every export) → ⬇ Download CSV from 'Interest over time'. The native file is detected "
               "automatically. Any other CSV with date, value and title/anime_id columns can be mapped below.")
    up = st.file_uploader("Trend CSV", type=["csv"], key="trend_up")
    tmpl = settings.RAW_DATA_DIR / settings.TREND_TEMPLATE_NAME
    use_tmpl = False
    if tmpl.exists():
        n_rows = max(0, sum(1 for _ in tmpl.open(encoding="utf-8-sig", errors="ignore")) - 1)
        if n_rows:
            use_tmpl = st.checkbox(f"Use {tmpl.name} from the data folder ({n_rows} rows)")
        else:
            st.caption(f"{tmpl.name} in the data folder has headers only (no observations yet).")
    if not up and not use_tmpl:
        return
    data = up.getvalue() if up else tmpl.read_bytes()
    fname = up.name if up else tmpl.name
    native = parse_google_trends_export(data)
    if native is not None:
        frame = native
        mapping = {"date": "date", "value": "raw_value", "query": "query", "geo": "geo", "anime_id": None, "source": None}
        geos_in_file = native["geo"].dropna().unique().tolist()
        st.success(f"Google Trends export detected: {native['query'].nunique()} term(s); geography in file: "
                   f"{', '.join(geos_in_file) or 'none'}.")
        default_geo = None
        if not geos_in_file:
            default_geo = st.text_input("This file has no geography column. Which market did you export? "
                                        "(leave blank if unsure — rows will not be labelled India)",
                                        "", placeholder="India") or None
    else:
        try:
            frame = read_csv_bytes(data)
        except ValueError as exc:
            st.error(str(exc))
            return
        if frame.empty:
            st.warning("The file has no data rows.")
            return
        st.dataframe(frame.head(5), use_container_width=True, hide_index=True)
        guess = guess_mapping(list(frame.columns), TREND_FIELD_ALIASES)
        cols = ["(none)"] + list(frame.columns)
        c = st.columns(5)
        mapping = {}
        for i, (fld, lab) in enumerate((("date", "Date column"), ("value", "Value column"), ("query", "Title / query column"),
                                        ("anime_id", "anime_id column"), ("geo", "Geography column"))):
            sel = c[i].selectbox(lab, cols, index=cols.index(guess[fld]) if guess.get(fld) else 0, key=f"map_{fld}")
            mapping[fld] = None if sel == "(none)" else sel
        mapping["source"] = guess.get("source")
        default_geo = None
        if not mapping.get("geo"):
            default_geo = st.text_input("No geography column. If every row is from one market, state it "
                                        "(leave blank if unknown — rows will not be labelled India):", "") or None
    overrides = st.session_state.setdefault("trend_overrides", {})
    qmap, _ = pipeline.load_query_map(df)   # curated, MAL-id-verified links (data/mappings/trend_query_map.csv)
    out, rep = validate_trends(frame, mapping, matcher, fname, default_geo=default_geo,
                               query_overrides={**qmap, **overrides}, source=f"Google Trends export ({fname})")
    if len(out):
        out["batch_id"] = Path(fname).stem

    a, b, c = st.columns(3)
    a.metric("Rows read", rep.rows_read)
    b.metric("Valid observations", rep.rows_valid)
    c.metric("Rejected", rep.rows_rejected)
    for reason, n in rep.rejected.items():
        st.caption(f"✗ {n} row(s): {reason}")
    for note in rep.notes:
        st.caption(f"ℹ {note}")
    unresolved = list(rep.ambiguous_titles) + rep.unmatched_titles
    if unresolved:
        st.warning(f"{len(unresolved)} title(s) need to be linked to a catalog record before their rows can be imported.")
        for q in unresolved[:10]:
            cands = rep.ambiguous_titles.get(q)
            col1, col2 = st.columns([1, 2])
            col1.markdown(f"**{q}**" + (f" — {len(cands)} catalog records share this name" if cands else " — no exact match"))
            pool = df[df["anime_id"].isin(cands)] if cands else catalog_service.search(df, q, 25)
            if pool.empty:
                col2.caption("No similar catalog titles; search the catalog to check the spelling.")
                continue
            opts = ["(skip)"] + pool["anime_id"].tolist()
            pick = col2.selectbox("Link to", opts, format_func=lambda x: x if x == "(skip)" else names.get(x, x), key=f"ov_{q}")
            if pick != "(skip)":
                overrides[q] = pick
        if st.button("Apply links"):
            st.rerun()
    if rep.rows_valid and st.button(f"Save {rep.rows_valid} valid observations", type="primary"):
        total = evidence_store.save_trends(out)
        evidence_store.log_import(rep)
        app_data.refresh()
        st.success(f"Saved. The trend store now holds {total:,} observations.")
        st.rerun()


with st.expander("➕ Import trend data", expanded=trends.empty):
    import_panel()

if trends.empty:
    Shinigami.render("caution", "No dated trend observations are loaded, so I cannot measure growth for any title. "
                "Import a Google Trends export to start.")
    empty_state("No trend observations yet", """
<p>Trending Radar only shows <b>measured</b> observations. Nothing is estimated or filled in.</p>
<ol><li>Open Google Trends, set the region to <b>India</b> and the range to <b>Past 5 years</b>.</li>
<li>Compare one anchor title (keep it in every export) with up to four other titles. Prefer the Topic suggestion over a plain search term.</li>
<li>Download the 'Interest over time' CSV and import it above.</li></ol>
<p>Google Trends values are relative 0–100 indices, not counts of searches or viewers.</p>""")
    st.stop()

# ----------------------------------------------------------- filters ----
geos = sorted(trends["geo"].dropna().unique().tolist())
f1, f2, f3 = st.columns([1, 1.6, 1])
market_opts = geos + (["Unspecified geography"] if trends["geo"].isna().any() else [])
market = f1.selectbox("Market (from the data)", market_opts,
                      index=market_opts.index("India") if "India" in market_opts else 0)
dmin, dmax = trends["date"].min().date(), trends["date"].max().date()
dr = f2.date_input("Observation period", (dmin, dmax), min_value=dmin, max_value=dmax)
start, end = (dr if isinstance(dr, tuple) and len(dr) == 2 else (dmin, dmax))
sub = trends if market != "Unspecified geography" else trends[trends["geo"].isna()]
freq = detect_frequency(sub["date"])
if freq == "monthly":
    window = f3.number_input("Comparison window (months)", 2, 24, settings.TREND_WINDOW_MONTHS, step=1,
                             help="The data is monthly: recent N months vs the N months before.")
    unit = "month"
    table, results = candidate_table(sub, None, None if market == "Unspecified geography" else market, start, end,
                                     window_months=int(window))
else:
    window = f3.number_input("Comparison window (weeks)", 4, 52, settings.TREND_WINDOW_WEEKS, step=1)
    unit = "week"
    table, results = candidate_table(sub, int(window), None if market == "Unspecified geography" else market, start, end)
if table.empty:
    st.info("No observations fall inside these filters.")
    st.stop()
table.insert(0, "title", table["anime_id"].map(lambda a: names.get(a, a)))
batch_of = sub.groupby(["anime_id", "query"])["batch_id"].first()
table["export"] = [batch_of.get((a, q), "") for a, q in zip(table["anime_id"], table["query"])]
multi_batch = table["export"].nunique() > 1
by_key = {(r.anime_id, r.query): r for r in results}

# --------------------------------------------------------- Shinigami + table ----
sufficient = table[table["reliability"] == "sufficient"]
cautions, discoveries = [], []
if market not in ("India",):
    cautions.append(f"These observations are for '{market}', not India — do not read them as Indian demand.")
if sufficient.empty:
    cautions.append("No series has enough observations in both windows to calculate a reliable growth figure.")
else:
    ranked = sufficient.dropna(subset=["pct_change"]).sort_values("pct_change", ascending=False)
    if not ranked.empty and ranked.iloc[0]["pct_change"] > 0:
        top = ranked.iloc[0]
        discoveries.append(f"{top['title']} shows the largest measured relative rise: average index {top['baseline_mean']} → "
                           f"{top['recent_mean']} ({top['pct_change']:+.0f}%) across the last two {int(window)}-{unit} windows "
                           f"({market}). Search interest is not demand or revenue.")
if multi_batch:
    cautions.append(f"These {table['export'].nunique()} exports were each scaled 0–100 separately and share no anchor title, "
                    "so index levels are not comparable between exports. Rankings use % change within each series.")
Shinigami.speak(cautions, discoveries, "Select a row to chart it and carry the title to Audience Intelligence.")

st.markdown(f"#### Candidates {label('calc')}", unsafe_allow_html=True)
st.caption(f"{freq.capitalize()} data. Recent window = last {int(window)} {unit}s up to the latest observation; baseline = the "
           f"{int(window)} {unit}s before that. Change = mean(recent) − mean(baseline) in index points, comparable only within one "
           f"export; % change (baseline at least 1 point) is used for ranking. 'Insufficient' = too few observations in a window — not ranked. "
           f"A high share of zeros means search volume was often below Google's reporting threshold.")
rank_key = "pct_change" if multi_batch else "abs_change"
rank_view = table.sort_values(["reliability", rank_key], key=lambda s: s.map({"sufficient": 0, "limited": 1, "insufficient": 2})
                              if s.name == "reliability" else s, ascending=[True, False], na_position="last")
show = rank_view[["title", "query", "export", "latest_value", "baseline_mean", "recent_mean", "abs_change", "pct_change",
                  "observations", "last_date", "zero_share", "reliability"]].rename(columns={"export": "Export (own scale)",
    "title": "Title", "query": "Query", "geo": "Market", "latest_value": "Latest index", "baseline_mean": "Baseline mean",
    "recent_mean": "Recent mean", "abs_change": "Change (pts)", "pct_change": "Change %", "observations": "Obs.",
    "last_date": "Last obs.", "zero_share": "Zeros in windows", "reliability": "Reliability"})
event = st.dataframe(show, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
                     key="tr_table", column_config={"Change %": st.column_config.NumberColumn(format="%.1f%%")})
rows = event.selection.rows if event and event.selection else []
if rows:
    chosen = rank_view.iloc[rows[0]]
    if chosen["anime_id"] != st.session_state.get("selected_anime_id"):
        if st.button(f"Investigate “{chosen['title']}” across AniScope", type="primary"):
            state.select_title(chosen["anime_id"], chosen["title"])
            st.rerun()

# -------------------------------------------------------------- chart ----
st.markdown(f"#### Observed index over time {label('observed')}", unsafe_allow_html=True)
series_keys = [f"{r.anime_id}||{r.query}" for r in results]
sel_id = st.session_state.get("selected_anime_id")
default = [k for k in series_keys if k.startswith(f"{sel_id}||")] or series_keys[:3]
picked = st.multiselect("Series to plot", series_keys, default=default[:5],
                        format_func=lambda k: f"{names.get(k.split('||')[0], k)} — “{k.split('||')[1]}”")
if picked:
    fig = go.Figure()
    batches = set()
    for i, k in enumerate(picked):
        aid, q = k.split("||")
        s = sub[(sub["anime_id"] == aid) & (sub["query"] == q)]
        s = s[(s["date"] >= pd.Timestamp(start)) & (s["date"] <= pd.Timestamp(end))].sort_values("date")
        batches |= set(s["batch_id"])
        fig.add_trace(go.Scatter(x=s["date"], y=s["value"], mode="lines+markers", name=names.get(aid, aid)[:40],
                                 line=dict(color=PLOT_COLORS[i % len(PLOT_COLORS)], width=2.2), marker=dict(size=4),
                                 hovertemplate="%{x|%d %b %Y}<br>Index %{y}<extra>" + q + "</extra>"))
    if len(picked) == 1:
        r = by_key.get(tuple(picked[0].split("||")))
        if r:
            fig.add_vrect(x0=r.baseline_window[0], x1=r.baseline_window[1], fillcolor="#94A3B8", opacity=0.10, line_width=0,
                          annotation_text="baseline", annotation_position="top left")
            fig.add_vrect(x0=r.recent_window[0], x1=r.recent_window[1], fillcolor="#0D9488", opacity=0.10, line_width=0,
                          annotation_text="recent", annotation_position="top left")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="#fff", hovermode="x unified",
                      yaxis=dict(title="Search interest index (0–100, relative)", gridcolor="#EEF0F3", rangemode="tozero"),
                      xaxis=dict(gridcolor="#F3F4F6"), legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    if len(batches) > 1:
        st.caption("⚠ These series come from different exports; compare their shapes, not their absolute levels.")
    for k in picked[:3]:
        r = by_key.get(tuple(k.split("||")))
        if r:
            st.markdown(f"{label('calc')} {explain(r)}", unsafe_allow_html=True)
            for reason in r.reasons:
                st.caption(f"⚠ {reason}")

# --------------------------------------------------- level vs momentum ----
st.markdown(f"#### Visibility vs momentum {label('interp')}", unsafe_allow_html=True)
pool = table[table["reliability"] != "insufficient"]
if multi_batch:
    exp = st.selectbox("Compare titles within one export (levels are only comparable inside the same export)",
                       sorted(pool["export"].unique()))
    pool = pool[pool["export"] == exp]
q = level_vs_momentum(pool)
if len(q) >= 3:
    fig2 = go.Figure()
    for i, (quad, g) in enumerate(q.groupby("quadrant")):
        fig2.add_trace(go.Scatter(x=g["recent_mean"], y=g["abs_change"], mode="markers+text", name=quad,
                                  text=g["title"].str.slice(0, 22), textposition="top center", cliponaxis=False,
                                  marker=dict(size=11, color=PLOT_COLORS[i % len(PLOT_COLORS)])))
    fig2.add_hline(y=0, line_color="#CBD5E1")
    fig2.add_vline(x=float(q["recent_mean"].median()), line_dash="dot", line_color="#CBD5E1")
    fig2.update_layout(height=380, margin=dict(l=60, r=90, t=30, b=10), plot_bgcolor="#fff",
                       xaxis_title="Level: recent mean index", yaxis_title="Momentum: change in points",
                       legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    st.caption("Quadrants split at the median level of the compared series. 'Emerging' means a lower observed level with a "
               "rising index — a reason to investigate, not a prediction of commercial success.")
else:
    st.caption("Needs at least three series with enough observations to compare level and momentum.")

# ------------------------------------------------- selected title focus ----
with st.expander("Check a specific catalog title"):
    rec = title_picker("tr")
    if rec is not None:
        has = rec["anime_id"] in set(trends["anime_id"])
        st.markdown(f"**{rec['title']}** — " + ("trend observations loaded." if has else
                    "no trend observations loaded for this title; growth cannot be assessed."))
