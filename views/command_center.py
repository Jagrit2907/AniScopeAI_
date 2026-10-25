"""Screen 1 — Command Center."""
from html import escape

import pandas as pd
import streamlit as st

from components import Shinigami
from components.styles import empty_state
from components.widgets import catalog_card, title_picker
from config import settings
from src import app_data, catalog_service, state
from src.data_loader import catalog_summary

res = app_data.catalog_result()

st.markdown(
    '<div class="as-hero"><div class="as-kanji">観</div>'
    '<h1>AniScope AI</h1>'
    '<p>Turn anime audience signals into evidence-backed commercial opportunities in India.</p>'
    '<div class="as-flow"><span>1 · Discover attention</span><span>2 · Understand responses</span>'
    '<span>3 · Find an underexplored angle</span><span>4 · Shape an offer</span>'
    '<span>5 · Plan validation</span><span>6 · Brief the team</span></div></div>',
    unsafe_allow_html=True)
st.write("")

if not res.ok:
    Shinigami.render("caution", "I can't find the anime catalog yet, so nothing can be analysed.")
    empty_state("Catalog not loaded", f"""
<p>{escape(res.error or 'Unknown error')}</p>
<p><b>How to fix:</b> copy <code>anime_catalog_all_titles.csv</code> (or <code>.jsonl</code>) and
<code>dataset_manifest.json</code> into:<br><code>{escape(str(settings.RAW_DATA_DIR))}</code></p>
<p>Or point AniScope at another folder: create a <code>.env</code> file in the project folder containing
<code>ANISCOPE_DATA_DIR=C:\\path\\to\\your\\data</code>, then restart the app.</p>""")
    st.stop()

df = res.df
cov = app_data.coverage()
summ = catalog_summary(df)
rec = catalog_service.get_record(df, st.session_state.get("selected_anime_id"))

left, right = st.columns([1.55, 1])
with right:
    cautions, discoveries = [], []
    if cov["trend_titles"] == 0:
        cautions.append("No trend observations are loaded yet, so I can't say which titles are gaining attention in India. "
                        "Import a Google Trends export in Trending Radar.")
    if cov["reviews"] == 0:
        cautions.append("No review evidence is loaded, so audience strengths and criticisms are unknown for every title.")
    if cov["trend_titles"]:
        discoveries.append(f"Trend observations cover {cov['trend_titles']} title(s), latest dated {cov['trend_last']}. "
                           "Open Trending Radar to compare momentum.")
    Shinigami.speak(cautions, discoveries,
               "Start by searching for a title, or open Trending Radar to see which titles have observed attention data.")

with left:
    st.subheader("Search the catalog")
    picked = title_picker("cc")
    if rec is not None:
        catalog_card(rec)
        b1, b2 = st.columns(2)
        b1.page_link("views/trending_radar.py", label="See its trend data →", icon=":material/trending_up:")
        b2.page_link("views/audience_intelligence.py", label="See audience evidence →", icon=":material/forum:")

st.markdown("#### Data coverage")
m = st.columns(6)
m[0].metric("Catalog records", f"{summ['records']:,}")
m[1].metric("Unique titles", f"{summ['unique_titles']:,}",
            help=f"{summ['duplicate_title_records']:,} records share a title string with another record (e.g. remakes, movies).")
m[2].metric("Titles w/ trends", f"{cov['trend_titles']:,}")
m[3].metric("Titles w/ reviews", f"{cov['review_titles']:,}")
m[4].metric("Latest observation", str(cov["trend_last"]) if cov["trend_last"] else "—")
evidence_kinds = (cov["trend_titles"] > 0) + (cov["review_titles"] > 0)
m[5].metric("Data readiness", ["Catalog only", "Partial", "Ready"][evidence_kinds],
            help="Catalog only → catalog loaded; Partial → trends or reviews loaded; Ready → both.")
manifest = res.manifest or {}
snap = manifest.get("snapshot_date") or manifest.get("lastUpdate")
lic = manifest.get("license")
lic_name = lic.get("name") if isinstance(lic, dict) else lic
st.caption(f"Source file: {res.path.name}" + (f" · snapshot {snap}" if snap else "")
           + (f" · licence: {lic_name}" if lic_name else "")
           + (f" · {res.rejected_rows} row(s) without a title were skipped" if res.rejected_rows else ""))

st.markdown("#### Entry points")
e = st.columns(4)
e[0].page_link("views/trending_radar.py", label="Explore Trending Radar", icon=":material/trending_up:")
e[1].page_link("views/audience_intelligence.py", label="Explore Audience Intelligence", icon=":material/forum:")
e[2].page_link("views/creative_lab.py", label="Creative Opportunity Lab", icon=":material/lightbulb:")
e[3].page_link("views/business_planner.py", label="Business Opportunity Planner", icon=":material/storefront:")

st.markdown("#### Catalog explorer")
with st.container(border=True):
    f1, f2, f3, f4, f5 = st.columns([1, 1, 1.4, 1.6, 1])
    types = f1.multiselect("Format", sorted(df["type"].dropna().unique().tolist()))
    statuses = f2.multiselect("Status", sorted(df["status"].dropna().unique().tolist()))
    years = df["year"].dropna()
    yr = f3.slider("Year", int(years.min()), int(years.max()), (int(years.min()), int(years.max())))
    tags = f4.multiselect("Tags (all must match)", catalog_service.top_tags(df, 80))
    full_range = yr == (int(years.min()), int(years.max()))
    filtered = catalog_service.filter_catalog(df, types, statuses, None if full_range else yr, tags,
                                              include_unknown_year=full_range)
    vis_df, _ = app_data.visibility()
    sort_opts = ["Year (newest)", "Title (A–Z)", "Catalog score"] + ([] if vis_df.empty else ["MAL members (2020)"])
    sort_by = f5.selectbox("Sort by", sort_opts)
    filtered = filtered.assign(mal_members=filtered["anime_id"].map(vis_df["mal_members"]) if not vis_df.empty else pd.NA)
    sort_args = {"Year (newest)": (["year", "title"], [False, True]), "Title (A–Z)": (["title"], [True]),
                 "Catalog score": (["score"], [False]), "MAL members (2020)": (["mal_members"], [False])}[sort_by]
    show = filtered.sort_values(sort_args[0], ascending=sort_args[1], na_position="last").head(500)
    st.caption(f"{len(filtered):,} of {len(df):,} records match; showing the first 500. Catalog score is a global "
               "cross-site average without vote counts — unreleased or niche titles can show extreme scores.")
    view = pd.DataFrame({"Title": show["title"], "Format": show["type"], "Year": show["year"],
                         "Episodes": show["episodes"], "Status": show["status"], "Catalog score": show["score"].round(2),
                         "MAL members 2020": show["mal_members"],
                         "Tags": show["tags"].map(lambda t: ", ".join(t[:5]))})
    event = st.dataframe(view, hide_index=True, use_container_width=True, height=320,
                         on_select="rerun", selection_mode="single-row", key="cc_table")
    rows = event.selection.rows if event and event.selection else []
    if rows:
        chosen = show.iloc[rows[0]]
        if st.button(f"Select “{chosen['title']}” for investigation", type="primary"):
            state.select_title(chosen["anime_id"], catalog_service.label(chosen))
            st.rerun()

st.markdown("#### Recent workspace activity")
r1, r2 = st.columns(2)
with r1:
    recent = st.session_state.get("recent_titles") or []
    if recent:
        for item in recent[:6]:
            if st.button(f"{item['title']}  ·  {item['at']}", key=f"recent_{item['id']}", use_container_width=True):
                state.select_title(item["id"], item["title"])
                st.rerun()
    else:
        st.caption("No titles investigated yet.")
with r2:
    saved = st.session_state.get("saved_concepts") or []
    briefs = st.session_state.get("saved_briefs") or []
    st.caption(f"Saved concepts: {len(saved)} · Saved briefs: {len(briefs)}")
    for c in saved[-3:][::-1]:
        st.markdown(f"- **{c.get('working_title')}** — {', '.join(c.get('inspired_by_themes') or [])}")
    for b in briefs[-3:][::-1]:
        st.markdown(f"- Brief: {b.get('title')} ({b.get('generated_at')})")
