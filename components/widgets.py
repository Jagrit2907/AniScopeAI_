"""Shared UI widgets: title picker, catalog card, evidence quotes, sidebar status."""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from components.styles import pills
from src import app_data, catalog_service, state
from src.visibility import describe as describe_visibility
from src.review_analysis import excerpt


def title_picker(key: str, label: str = "Find an anime in the catalog") -> pd.Series | None:
    """Search the full catalog and set the shared selected title. Returns the selected record."""
    df = app_data.catalog()
    if df is None:
        return None
    current = catalog_service.get_record(df, st.session_state.get("selected_anime_id"))
    q = st.text_input(label, key=f"{key}_q", placeholder="Title or alternate title, e.g. Frieren")
    if q:
        hits = catalog_service.search(df, q, limit=40)
        if hits.empty:
            st.caption(f"No catalog records match “{q}”.")
        else:
            options = hits["anime_id"].tolist()
            labels = dict(zip(hits["anime_id"], hits.apply(catalog_service.label, axis=1)))
            idx = options.index(current["anime_id"]) if current is not None and current["anime_id"] in options else 0
            choice = st.selectbox(f"{len(hits)} match(es) — choose a record", options, index=idx,
                                  format_func=lambda a: labels[a], key=f"{key}_sel")
            if st.button("Use this title", key=f"{key}_use", type="primary"):
                state.select_title(choice, labels[choice])
                st.rerun()
    return catalog_service.get_record(df, st.session_state.get("selected_anime_id"))


def catalog_card(rec: pd.Series) -> None:
    meta = [f"{k}: {v}" for k, v in (("Type", rec["type"]), ("Year", rec["year"]), ("Season", rec["season"]),
                                      ("Episodes", rec["episodes"]), ("Status", rec["status"])) if pd.notna(v)]
    score = f"Cross-site catalog score {rec['score']:.2f}/10 (global)" if pd.notna(rec["score"]) else "No catalog score"
    syn = rec["synonyms"][:6]
    links = " · ".join(f'<a href="{escape(u)}" target="_blank">{escape(u.split("/")[2])}</a>' for u in rec["sources"][:5])
    st.markdown(
        f'<div class="as-card"><span class="as-label as-observed">Catalog metadata</span>'
        f'<h4 style="margin-top:6px">{escape(str(rec["title"]))}</h4>'
        f'<div style="color:#6B7280;font-size:.85rem">{escape(" · ".join(meta)) or "Limited metadata"} · {escape(score)}</div>'
        + (f'<div style="margin-top:6px">{pills(rec["tags"][:12])}</div>' if rec["tags"] else "")
        + (f'<div style="margin-top:4px;font-size:.8rem;color:#6B7280">Also known as: {escape(", ".join(syn))}</div>' if syn else "")
        + (f'<div style="margin-top:4px;font-size:.8rem">Sources: {links}</div>' if links else "")
        + '</div>', unsafe_allow_html=True)
    if not app_data.visibility()[0].empty:
        st.markdown(f'<div class="as-card"><span class="as-label as-observed">Visibility snapshot</span> '
                    f'<span style="font-size:.88rem">{escape(describe_visibility(app_data.visibility_row(rec["anime_id"])))}</span></div>',
                    unsafe_allow_html=True)


def quote(text: str, source: str | None, url: str | None, date: str | None, negative: bool = False) -> str:
    src = escape(str(source or "unknown source"))
    if url and str(url).startswith("http"):
        src = f'<a href="{escape(str(url))}" target="_blank">{src}</a>'
    when = f" · {escape(str(date))}" if date and str(date) != "nan" else ""
    return (f'<div class="as-quote{" neg" if negative else ""}">“{escape(excerpt(text))}”'
            f'<span class="src">Excerpt from {src}{when}</span></div>')


def sidebar_status() -> None:
    res = app_data.catalog_result()
    cov = app_data.coverage()
    with st.sidebar:
        st.markdown("### 🍙 AniScope AI")
        if res.ok:
            snap = (res.manifest or {}).get("snapshot_date") or (res.manifest or {}).get("lastUpdate")
            st.markdown(
                f'<div class="as-status"><span class="as-dot" style="background:#0D9488"></span>'
                f'Catalog: <b>{len(res.df):,}</b> records{f" · snapshot {escape(str(snap))}" if snap else ""}<br>'
                f'<span class="as-dot" style="background:{"#0D9488" if cov["trend_titles"] else "#D99A1E"}"></span>'
                f'Trend data: <b>{cov["trend_titles"]}</b> titles · {cov["trend_obs"]:,} obs<br>'
                f'<span class="as-dot" style="background:{"#0D9488" if cov["review_titles"] else "#D99A1E"}"></span>'
                f'Reviews: <b>{cov["reviews"]:,}</b> for {cov["review_titles"]} titles<br>'
                f'<span class="as-dot" style="background:{"#0D9488" if cov["visibility_titles"] else "#D99A1E"}"></span>'
                f'Visibility (MAL 2020): <b>{cov["visibility_titles"]:,}</b> titles</div>',
                unsafe_allow_html=True)
        else:
            st.markdown('<div class="as-status"><span class="as-dot" style="background:#E76F51"></span>'
                        '<b>Catalog not loaded</b></div>', unsafe_allow_html=True)
        df = res.df if res.ok else None
        rec = catalog_service.get_record(df, st.session_state.get("selected_anime_id")) if df is not None else None
        st.markdown("---")
        st.caption("Selected title")
        st.markdown(f"**{rec['title']}**" if rec is not None else "_None yet_")
        if st.session_state.get("selected_themes"):
            st.caption("Selected themes: " + ", ".join(st.session_state["selected_themes"]))
        c1, c2 = st.columns(2)
        if c1.button("Save", use_container_width=True, help="Save workspace to data/database/workspace.json"):
            st.toast("Workspace saved." if state.save_workspace() else "Could not write the workspace file.")
        if c2.button("Reset", use_container_width=True, help="Clear the current workspace"):
            state.reset_workspace()
            st.rerun()
