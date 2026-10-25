"""Screen 3 — Audience Intelligence and the Hidden Gems & Mixed-Response Analyzer."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import Shinigami
from components.styles import TEAL, VERMILION, empty_state, label, page_header, pills
from components.widgets import catalog_card, quote, title_picker
from config import settings
from src import app_data, catalog_service, evidence_store, pipeline, state
from src.data_validation import REVIEW_FIELD_ALIASES, guess_mapping, read_csv_bytes, validate_reviews
from src.opportunity_engine import find_candidates
from src.review_analysis import METHOD, evidence_overview
from src.visibility import describe as describe_visibility
from src.theme_extraction import ASPECT_TAXONOMY, aspect_summary

page_header("Audience understanding", "Audience Intelligence",
            "What do reviewers praise or criticise — and which titles show strengths alongside criticism?")

df = app_data.catalog()
if df is None:
    empty_state("Catalog not loaded", "<p>Open the Command Center for setup instructions.</p>")
    st.stop()
names = dict(zip(df["anime_id"], df.apply(catalog_service.label, axis=1)))
reviews, evidence = app_data.reviews()


def import_panel() -> None:
    st.markdown("**Import review evidence (CSV)**")
    st.caption("Use only sources whose terms permit it (e.g. the AniList API, free for non-commercial use — see "
               "scripts/fetch_anilist_reviews.py). Rows are linked to the catalog by anime_id, MAL id, AniList id, "
               "or an exact title match; nothing is linked by guesswork.")
    up = st.file_uploader("Review CSV", type=["csv"], key="rev_up")
    local = []
    for name in [settings.REVIEW_TEMPLATE_NAME] + settings.KAGGLE_REVIEWS_FILE_NAMES:
        f = settings.RAW_DATA_DIR / name
        if f.exists() and f.stat().st_size > 0:
            with f.open(encoding="utf-8-sig", errors="ignore") as fh:
                has_rows = sum(1 for _, __ in zip(range(2), fh)) > 1
            if has_rows:
                local.append(f)
            else:
                st.caption(f"{name} in the data folder has headers only (no reviews yet).")
    tmpl = None
    if local and not up:
        pick = st.selectbox("…or use a file already in the data folder", ["(none)"] + [f.name for f in local])
        tmpl = next((f for f in local if f.name == pick), None)
    if not up and tmpl is None:
        return
    try:
        frame = read_csv_bytes(up.getvalue() if up else tmpl.read_bytes())
    except ValueError as exc:
        st.error(str(exc))
        return
    if frame.empty:
        st.warning("The file has no data rows.")
        return
    st.dataframe(frame.head(5), use_container_width=True, hide_index=True)
    guess = guess_mapping(list(frame.columns), REVIEW_FIELD_ALIASES)
    cols = ["(none)"] + list(frame.columns)
    fields = [("text", "Review text*"), ("title", "Anime title"), ("anime_id", "anime_id"), ("mal_id", "MAL id"),
              ("anilist_id", "AniList id"), ("source", "Source"), ("source_url", "Source URL"), ("date", "Date"),
              ("score", "Reviewer score"), ("language", "Language"), ("geography", "Reviewer geography"),
              ("helpful_count", "Helpful votes"), ("review_id", "Review id")]
    mapping = {}
    grid = st.columns(4)
    for i, (fld, lab) in enumerate(fields):
        sel = grid[i % 4].selectbox(lab, cols, index=cols.index(guess[fld]) if guess.get(fld) else 0, key=f"rmap_{fld}")
        mapping[fld] = None if sel == "(none)" else sel
    default_source = None if mapping.get("source") else st.text_input("Source name for all rows (required for provenance)", "")
    if not mapping.get("source") and not default_source:
        st.info("Name the source before importing.")
        return
    out, rep = validate_reviews(frame, mapping, app_data.matcher(), up.name if up else tmpl.name, default_source)
    a, b, c = st.columns(3)
    a.metric("Rows read", rep.rows_read)
    b.metric("Valid reviews", rep.rows_valid)
    c.metric("Rejected", rep.rows_rejected)
    for reason, n in rep.rejected.items():
        st.caption(f"✗ {n} row(s): {reason}")
    if rep.ambiguous_titles:
        st.caption(f"✗ {len(rep.ambiguous_titles)} title string(s) match several catalog records; add an id column to link them.")
    for note in rep.notes:
        st.caption(f"ℹ {note}")
    cap = st.number_input("Maximum reviews kept per title (most helpful, then longest)", 5, 500, 30,
                          help="Keeps analysis fast and stops a few very popular titles dominating. Applied before saving.")
    if rep.rows_valid:
        capped = pipeline.cap_per_title(out, int(cap))
        if st.button(f"Save {len(capped):,} reviews and analyse", type="primary"):
            if len(capped) < len(out):
                rep.notes.append(f"Capped at {int(cap)} per title: kept {len(capped):,} of {len(out):,}.")
                rep.rows_valid = len(capped)
            total = evidence_store.save_reviews(capped)
            evidence_store.log_import(rep)
            bar = st.progress(0.0, "Analysing review text…")
            pipeline.build_analysis_cache(lambda f, msg: bar.progress(f, msg))
            app_data.refresh()
            st.success(f"Saved and analysed. The review store now holds {total:,} records.")
            st.rerun()


with st.expander("➕ Import review evidence", expanded=reviews.empty):
    import_panel()

tab_title, tab_gems = st.tabs(["Title evidence", "Hidden Gems & Mixed-Response Analyzer"])

# =========================================================== title tab ====
def title_tab() -> None:
    left, right = st.columns([1.5, 1])
    with left:
        rec = title_picker("ai")
    if rec is None:
        with right:
            Shinigami.render("guide", "Select a title to see the audience evidence that actually belongs to it.")
        return
    aid = rec["anime_id"]
    r = reviews[reviews["anime_id"] == aid]
    ev = evidence[evidence["anime_id"] == aid]
    ov = evidence_overview(r)
    summ = aspect_summary(ev, settings.ASPECT_MIN_MENTIONS)
    praised = summ.loc[summ["stance"] == "mostly praised", "aspect"].tolist()
    criticised = summ.loc[summ["stance"] == "mostly criticised", "aspect"].tolist()

    with right:
        cautions, discoveries = [], []
        if ov["records"] == 0:
            cautions.append(f"{rec['title']} has catalog metadata, but no loaded review evidence, so I can't describe audience response.")
        else:
            if ov["records"] < settings.REVIEW_MIN_FOR_ANALYSIS:
                cautions.append(f"Only {ov['records']} review(s) — below the {settings.REVIEW_MIN_FOR_ANALYSIS} needed for a title-level finding.")
            if ov["india_tagged"] == 0:
                cautions.append("These reviews are not verified as coming from Indian viewers.")
            if praised and ov["records"] >= settings.REVIEW_MIN_FOR_ANALYSIS:
                msg = f"In {ov['records']} reviews, {', '.join(praised[:2])} is mostly praised"
                msg += f" while {', '.join(criticised[:2])} is mostly criticised." if criticised else "."
                discoveries.append(msg)
        Shinigami.speak(cautions, discoveries, "Pick the themes you want to carry into the Creative Lab and Business Planner.")
    catalog_card(rec)

    if ov["records"] == 0:
        empty_state("No audience evidence for this title", "<p>Catalog metadata is not audience evidence. Import reviews "
                    "for this title (above) to analyse what viewers praise or criticise.</p>")
        return

    st.markdown(f"#### Evidence overview {label('observed')}", unsafe_allow_html=True)
    m = st.columns(5)
    m[0].metric("Review records", ov["records"])
    m[1].metric("Sources", len(ov["sources"]), help=", ".join(ov["sources"]))
    m[2].metric("Dated span (days)", (ov["date_max"] - ov["date_min"]).days if ov["date_min"] else "—",
                help=f"{ov['date_min']} to {ov['date_max']}" if ov["date_min"] else "No dates")
    m[3].metric("Reviewer score mean", "—" if ov["score_mean"] is None else f"{ov['score_mean']}/10",
                help=None if ov["score_std"] is None else f"Standard deviation {ov['score_std']} across {ov['with_score']} scored reviews")
    m[4].metric("India-tagged reviews", ov["india_tagged"])
    st.caption(f"Sources: {', '.join(ov['sources'])} · Dates: {ov['date_min']} to {ov['date_max']} · "
               f"Languages: {', '.join(ov['languages']) or 'not recorded'} · Reviews with reviewer geography: "
               f"{ov['with_geography']} of {ov['records']}. Without geography, reviews describe general reviewer response, not India.")

    counts = r["overall"].value_counts()
    st.markdown(f"#### Overall reception {label('calc')}", unsafe_allow_html=True)
    oc = st.columns(3)
    for col, lab in zip(oc, ("positive", "mixed", "negative")):
        col.metric(lab.capitalize(), int(counts.get(lab, 0)))
    st.caption("Uses the reviewer's own score when present (≥7 positive, ≤4 negative, else mixed); otherwise the text "
               f"sentiment score. Method: {METHOD}.")

    st.markdown(f"#### Storytelling aspects {label('interp')}", unsafe_allow_html=True)
    if summ.empty:
        st.info("No aspect keywords were found in these reviews.")
    else:
        fig = go.Figure()
        s2 = summ.sort_values("mentions")
        fig.add_bar(y=s2["aspect"], x=s2["positive"], name="Positive mentions", orientation="h", marker_color=TEAL)
        fig.add_bar(y=s2["aspect"], x=-s2["negative"], name="Negative mentions", orientation="h", marker_color=VERMILION,
                    customdata=s2["negative"], hovertemplate="%{customdata} negative<extra></extra>")
        fig.update_layout(barmode="relative", height=max(260, 34 * len(s2)), margin=dict(l=10, r=10, t=10, b=10),
                          plot_bgcolor="#fff", xaxis_title="← criticised   ·   praised →", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.dataframe(summ.rename(columns={"aspect": "Aspect", "reviews": "Reviews mentioning", "mentions": "Mentions",
                                          "positive": "Reviews praising", "negative": "Reviews criticising", "neutral": "Neutral only",
                                          "positive_share": "Positive share", "stance": "Stance"}),
                     hide_index=True, use_container_width=True,
                     column_config={"Positive share": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="percent")})
        st.caption(f"Aspect = keyword match in a sentence; polarity = that sentence's sentiment score (≥0.25 positive, ≤−0.25 negative). "
                   "Counts are per review: a review counts once as praising and/or once as criticising an aspect. "
                   f"A stance needs at least {settings.ASPECT_MIN_MENTIONS} polar mentions. Check the excerpts before relying on a stance.")

        st.markdown("#### Evidence by aspect")
        options = summ["aspect"].tolist()
        valid_prev = [t for t in st.session_state.get("selected_themes", []) if t in options]
        chosen = st.multiselect("Themes to carry forward to the Creative Lab and Business Planner", options, default=valid_prev,
                                key=f"themes_{aid}")
        if chosen != st.session_state.get("selected_themes"):
            st.session_state["selected_themes"] = chosen
            st.session_state["selected_finding"] = {
                "anime_id": aid, "title": rec["title"], "themes": chosen,
                "praised": [t for t in chosen if t in praised], "criticised": [t for t in chosen if t in criticised],
                "n_reviews": ov["records"], "sources": ov["sources"],
                "summary": f"{rec['title']}: " + "; ".join(
                    f"{row.aspect} {row.stance} ({row.positive}+ / {row.negative}−)" for row in summ[summ["aspect"].isin(chosen)].itertuples())
                    + f" — from {ov['records']} reviews ({', '.join(ov['sources'])}); not India-specific."}
            state.save_workspace()
        focus = st.selectbox("Show excerpts for", options, index=options.index(chosen[0]) if chosen else 0)
        fe = ev[ev["aspect"] == focus]
        pc, nc = st.columns(2)
        with pc:
            pos = fe[fe["polarity"] == "positive"].sort_values("compound", ascending=False).head(4)
            st.markdown(f"**Praise · {len(fe[fe['polarity']=='positive'])} review(s)**")
            st.markdown("".join(quote(x.sentence, x.source, x.source_url, x.date) for x in pos.itertuples())
                        or "_No positive sentences for this aspect._", unsafe_allow_html=True)
        with nc:
            neg = fe[fe["polarity"] == "negative"].sort_values("compound").head(4)
            st.markdown(f"**Criticism · {len(fe[fe['polarity']=='negative'])} review(s)**")
            st.markdown("".join(quote(x.sentence, x.source, x.source_url, x.date, negative=True) for x in neg.itertuples())
                        or "_No negative sentences for this aspect._", unsafe_allow_html=True)
        st.caption("Excerpts are verbatim sentences from the loaded reviews (shortened with … where long).")

with tab_title:
    title_tab()


# ============================================================ gems tab ====
def gems_tab() -> None:
    st.markdown("Finds titles where some storytelling aspects are mostly praised **and** others are criticised or "
                "divided, or overall reception is mixed. These are **candidates for further investigation**, not "
                "'underrated' verdicts.")
    if reviews.empty:
        Shinigami.render("caution", "No review evidence is loaded, so the analyzer has nothing to examine.")
        empty_state("Analyzer waiting for review evidence",
                    "<p>For the Kaggle MyAnimeList <code>reviews.csv</code> (~650 MB), put it in the data folder and run "
                    "<code>python scripts/ingest.py reviews-kaggle data/raw/reviews.csv</code> — it is streamed in chunks "
                    "and analysed once. Smaller CSVs can be imported above.</p><p>The analyzer needs at least "
                    f"{settings.REVIEW_MIN_FOR_ANALYSIS} reviews per title and {settings.ASPECT_MIN_MENTIONS} polar "
                    "mentions per aspect before it reports anything.</p>")
        return
    g1, g2, g3 = st.columns([1, 1.3, 1.2])
    min_rev = g1.number_input("Minimum reviews per title", 3, 100, settings.REVIEW_MIN_FOR_ANALYSIS)
    focus_aspect = g2.selectbox("Storytelling element to look for (must be mostly praised)",
                                ["(any)"] + list(ASPECT_TAXONOMY))
    vis_df, _ = app_data.visibility()
    low_vis = g3.checkbox("Only lower-visibility titles", disabled=vis_df.empty,
                          help="Keep titles at or below the 50th percentile of MAL members among same-format, same-year "
                               "titles (2020 snapshot). Titles not in the snapshot are excluded when this is on.")
    cands = app_data.gem_candidates(app_data.review_stamp(), None if focus_aspect == "(any)" else focus_aspect, int(min_rev))
    if low_vis:
        cands = [c for c in cands if c.anime_id in vis_df.index and vis_df.loc[c.anime_id, "peer_percentile"] <= 50]
    eligible = int((reviews["anime_id"].value_counts() >= min_rev).sum())
    trends = app_data.trends()
    if cands:
        Shinigami.render("discovery", f"{len(cands)} of {eligible} title(s) with enough reviews show praised aspects alongside "
                    "criticism or mixed reception. Read each one's limitations before using it.")
    else:
        Shinigami.render("caution", f"None of the {eligible} title(s) with ≥{int(min_rev)} reviews meets the mixed-response pattern"
                    + (f" with '{focus_aspect}' praised." if focus_aspect != "(any)" else "."))
    if len(cands) > 20:
        st.caption(f"Showing the 20 candidates with the highest contrast index of {len(cands)}. "
                   "Use the storytelling-element filter to narrow the list.")
    for c in cands[:20]:
        title = names.get(c.anime_id, c.anime_id)
        tr = trends[(trends["anime_id"] == c.anime_id) & (trends["geo"].fillna("").str.lower() == "india")]
        vis = (f"India search index, latest {tr.sort_values('date')['value'].iloc[-1]:.0f} (observed {tr['date'].max():%d %b %Y}). "
               if not tr.empty else "No India trend observations. ")
        vis += describe_visibility(app_data.visibility_row(c.anime_id))
        rec_c = catalog_service.get_record(df, c.anime_id)
        cat_score = f"{rec_c['score']:.2f}/10 (global cross-site catalog score)" if rec_c is not None and pd.notna(rec_c["score"]) else "—"
        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            h1.markdown(f"### {title}")
            h2.metric("Contrast index (experimental)", "—" if c.contrast_index is None else c.contrast_index,
                      help="Best praised aspect's positive share minus the weakest aspect's positive share. Describes how sharply "
                           "reviewers split by aspect. Not validated; not a measure of commercial potential.")
            st.markdown(f"{label('calc')} **Why selected:** {c.why}", unsafe_allow_html=True)
            v1, v2, v3 = st.columns(3)
            v1.markdown(f"**Visibility signal**<br><span style='font-size:.88rem'>{vis}</span>", unsafe_allow_html=True)
            v2.markdown(f"**Reception**<br><span style='font-size:.88rem'>Catalog score {cat_score}; reviewer scores "
                        f"{'—' if c.score_mean is None else f'mean {c.score_mean}, sd {c.score_std}'}; "
                        f"{c.mixed_share:.0%} mixed/negative</span>", unsafe_allow_html=True)
            v3.markdown(f"**Supporting records**<br><span style='font-size:.88rem'>{c.n_reviews} reviews "
                        "(evidence volume, not popularity)</span>", unsafe_allow_html=True)
            st.markdown(f"**Praised:** {pills(c.praised)}  **Criticised / divided:** {pills(c.criticised + c.divided)}",
                        unsafe_allow_html=True)
            ev_c = evidence[evidence["anime_id"] == c.anime_id]
            q1, q2 = st.columns(2)
            p = ev_c[(ev_c["aspect"].isin(c.praised)) & (ev_c["polarity"] == "positive")].sort_values("compound", ascending=False).head(2)
            n = ev_c[(ev_c["aspect"].isin(c.criticised + c.divided)) & (ev_c["polarity"] == "negative")].sort_values("compound").head(2)
            q1.markdown("".join(quote(x.sentence, x.source, x.source_url, x.date) for x in p.itertuples()), unsafe_allow_html=True)
            q2.markdown("".join(quote(x.sentence, x.source, x.source_url, x.date, True) for x in n.itertuples()), unsafe_allow_html=True)
            st.markdown(f"{label('hyp')} **Business relevance to investigate next:** " + " ".join(c.next_steps),
                        unsafe_allow_html=True)
            st.caption("Limitations: " + " ".join(c.limitations))
            if st.button("Use this finding in the workspace", key=f"use_{c.anime_id}"):
                state.select_title(c.anime_id, title)
                st.session_state["selected_themes"] = c.praised + c.criticised
                st.session_state["selected_finding"] = {
                    "anime_id": c.anime_id, "title": title, "themes": c.praised + c.criticised,
                    "praised": c.praised, "criticised": c.criticised, "n_reviews": c.n_reviews,
                    "summary": f"{title}: {c.why} ({c.n_reviews} reviews; not India-specific)."}
                state.save_workspace()
                st.success("Finding saved. It is now available in the Creative Lab, Business Planner and Brief.")


with tab_gems:
    gems_tab()
