"""Workspace page — data status, provenance, import log and analysis methods."""
import pandas as pd
import streamlit as st

from components.styles import page_header
from config import settings
from src import app_data, evidence_store
from src.data_loader import catalog_summary, discover_files
from src.review_analysis import METHOD
from src.theme_extraction import ASPECT_TAXONOMY

page_header("Transparency", "Data & Methods", "Where every number comes from, what was imported, and how it is analysed.")

res = app_data.catalog_result()
files = discover_files(settings.RAW_DATA_DIR)

st.markdown("#### Data folder")
st.code(str(settings.RAW_DATA_DIR))
st.caption("Change it with ANISCOPE_DATA_DIR in a .env file or environment variable, then restart.")
st.dataframe(pd.DataFrame([{"Role": k, "File": v.name if v else "not found"} for k, v in files.items()]),
             hide_index=True, use_container_width=True)

st.markdown("#### Catalog")
if res.ok:
    s = catalog_summary(res.df)
    st.write({**s, "file": res.path.name, "rows skipped (no title)": res.rejected_rows})
    st.caption("Columns mapped: " + ", ".join(f"{k} ← {v}" for k, v in res.column_map.items())
               + (f". Not used: {', '.join(map(str, res.unmapped_columns[:15]))}" if res.unmapped_columns else ""))
    if res.manifest:
        with st.expander("dataset_manifest.json"):
            st.json(res.manifest)
else:
    st.error(res.error)
st.info("Catalog data: Anime Offline Database (manami-project), licensed under the Open Data Commons Open Database "
        "License (ODbL) v1.0 and Database Contents License (DbCL) v1.0. Attribution must be kept; a redistributed "
        "derived database must be shared under the ODbL.")

st.markdown("#### Visibility snapshot (optional)")
vis_df, vis_err = app_data.visibility()
if vis_err:
    st.error(vis_err)
elif vis_df.empty:
    st.caption("No animes.csv in the data folder — visibility is not measured.")
else:
    st.write(f"{len(vis_df):,} catalog records linked by MyAnimeList id to animes.csv "
             "(Kaggle 'Anime Dataset with Reviews - MyAnimeList', crawled 2020). Members = global MAL users who listed the "
             "title; titles released after 2020 are absent. Not India-specific. The Kaggle page does not state a licence; "
             "the data was scraped from MyAnimeList, whose terms restrict reuse — treat it as research-only.")

st.markdown("#### Evidence stores")
cov = app_data.coverage()
c = st.columns(2)
c[0].metric("Trend observations", f"{cov['trend_obs']:,}", help=str(settings.TREND_STORE))
c[1].metric("Review records", f"{cov['reviews']:,}", help=str(settings.REVIEW_STORE))
with st.expander("Danger zone: clear an evidence store"):
    k = st.selectbox("Store", ["trend", "review"])
    if st.checkbox(f"I understand this deletes all imported {k} data") and st.button("Clear"):
        evidence_store.clear_store(k)
        app_data.refresh()
        st.rerun()

st.markdown("#### Import log")
log = evidence_store.read_import_log()
if log:
    st.dataframe(pd.DataFrame([{"When": e.get("imported_at"), "Kind": e.get("kind"), "File": e.get("file"),
                                "Read": e.get("rows_read"), "Valid": e.get("rows_valid"),
                                "Rejected": "; ".join(f"{k}: {v}" for k, v in (e.get("rejected") or {}).items()),
                                "Unmatched titles": ", ".join(e.get("unmatched_titles") or [])[:120]}
                               for e in reversed(log)]), hide_index=True, use_container_width=True)
else:
    st.caption("No imports yet.")

st.markdown("#### Methods")
st.markdown(f"""
**Trend momentum.** Per title/query/market series: recent window = last {settings.TREND_WINDOW_WEEKS} weeks (adjustable),
baseline = the preceding window of equal length. Change = mean(recent) − mean(baseline); % change only if the baseline mean > 0.
A window with fewer than {settings.TREND_MIN_POINTS_PER_WINDOW} observations is *insufficient* and the series is not ranked.
Missing weeks are never filled. Google Trends '<1' is stored as 0 and flagged.

**Review sentiment.** {METHOD}. Whole-review label uses the reviewer's own score when available.

**Aspects.** Sentence-level keyword taxonomy ({len(ASPECT_TAXONOMY)} aspects) + sentence sentiment (≥0.25 positive, ≤−0.25 negative).
Stance needs ≥{settings.ASPECT_MIN_MENTIONS} polar mentions: ≥65% positive = mostly praised, ≤35% = mostly criticised, else divided.

**Hidden Gems candidates.** ≥{settings.REVIEW_MIN_FOR_ANALYSIS} reviews, at least one mostly-praised aspect, and either a criticised/divided
aspect or ≥30% mixed/negative reviews. The contrast index is experimental and unvalidated.

**Creative concepts.** Rules-based (theme → design levers + seeded generic genre blocks). No external AI service.

**Business calculator.** Transparent funnel from user-entered assumptions; outputs are illustrative estimates only.

**Not established by any AniScope output:** Indian audience preference (unless evidence is India-tagged), commercial demand,
revenue, prediction accuracy, licensing or partnership availability.
""")
with st.expander("Aspect taxonomy (keyword patterns)"):
    st.dataframe(pd.DataFrame([{"Aspect": a, "Description": v["description"], "Patterns": ", ".join(v["patterns"])}
                               for a, v in ASPECT_TAXONOMY.items()]), hide_index=True, use_container_width=True)
