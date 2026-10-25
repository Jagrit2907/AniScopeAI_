"""Screen 6 — Opportunity Brief: assembled live from the current workspace."""
from html import escape

import pandas as pd
import streamlit as st

from components import Shinigami
from components.styles import page_header
from config import settings
from src import app_data, catalog_service, state
from src.brief_generator import build_brief, to_markdown
from src.business_calculator import Assumptions, calculate
from src.export_service import PDF_AVAILABLE, brief_to_pdf, to_csv_bytes
from src.review_analysis import evidence_overview
from src.theme_extraction import aspect_summary
from src.trend_analysis import candidate_table, explain
from src.visibility import describe as describe_visibility

page_header("Deliverable", "Opportunity Brief",
            "A structured brief for a Japanese entertainment company, built only from what this workspace contains.")

res = app_data.catalog_result()
df = res.df if res.ok else None
rec = catalog_service.get_record(df, st.session_state.get("selected_anime_id")) if df is not None else None
aid = rec["anime_id"] if rec is not None else None

# ---- gather inputs from the shared workspace -------------------------------
trend_info, trend_table = None, pd.DataFrame()
if aid:
    t = app_data.trends()
    t = t[t["anime_id"] == aid]
    if not t.empty:
        trend_table, results = candidate_table(t)
        if results:
            best = sorted(results, key=lambda r: (r.geo != "India", r.reliability != "sufficient"))[0]
            trend_info = {**best.as_row(), "explanation": explain(best)}

reviews, evidence = app_data.reviews()
ov, aspects_df = None, pd.DataFrame()
if aid:
    r = reviews[reviews["anime_id"] == aid]
    ov = evidence_overview(r)
    aspects_df = aspect_summary(evidence[evidence["anime_id"] == aid], settings.ASPECT_MIN_MENTIONS)
themes = st.session_state.get("selected_themes") or []
aspects_for_brief = aspects_df[aspects_df["aspect"].isin(themes)] if themes and not aspects_df.empty else aspects_df

a_dict = st.session_state.get("assumptions")
calc = None
if a_dict and a_dict.get("target_audience"):
    calc = calculate(Assumptions(**a_dict))

finding = st.session_state.get("selected_finding")
if finding and aid and finding.get("anime_id") not in (None, aid):
    finding = None   # never attach another title's finding

catalog_source = res.path.name if res.ok else "not loaded"
if res.ok and res.manifest:
    snap = res.manifest.get("snapshot_date") or res.manifest.get("lastUpdate")
    catalog_source += f", snapshot {snap}" if snap else ""

title_dict = None
if rec is not None:
    title_dict = {k: (None if (not isinstance(rec[k], list) and pd.isna(rec[k])) else rec[k])
                  for k in ("title", "type", "year", "episodes", "status", "score", "tags")}
    if not app_data.visibility()[0].empty:
        title_dict["visibility"] = describe_visibility(app_data.visibility_row(aid))

brief = build_brief(title=title_dict, trend=trend_info, evidence=ov, aspects=aspects_for_brief.to_dict("records"),
                    finding=finding, concept=st.session_state.get("concept"), plan=st.session_state.get("plan"),
                    assumptions=a_dict, calc=calc, validation=st.session_state.get("validation_plan"),
                    catalog_source=catalog_source)

n_gaps = len(brief["gaps"])
if rec is None:
    Shinigami.render("caution", "No title is selected, so this brief isn't anchored to an anime. Select one in the Command Center.")
elif n_gaps:
    Shinigami.render("caution", f"This brief has {n_gaps} evidence gap(s). They are listed under Risks and limitations, "
                "and the next steps say how to close them.")
else:
    Shinigami.render("discovery", "Every section has supporting inputs. Remember: it is still a set of hypotheses for validation.")

with st.expander("Revise inputs"):
    st.markdown("Each section is rebuilt from the workspace. To change it, edit the source screen:")
    cols = st.columns(4)
    cols[0].page_link("views/command_center.py", label="Title", icon=":material/search:")
    cols[1].page_link("views/audience_intelligence.py", label="Evidence & themes", icon=":material/forum:")
    cols[2].page_link("views/creative_lab.py", label="Concept", icon=":material/lightbulb:")
    cols[3].page_link("views/business_planner.py", label="Offer, assumptions, test", icon=":material/storefront:")

b1, b2, b3, b4 = st.columns(4)
if b1.button("Regenerate", type="primary", use_container_width=True):
    st.rerun()
if b2.button("Save brief to workspace", use_container_width=True):
    st.session_state["saved_briefs"] = (st.session_state.get("saved_briefs") or []) + [
        {"title": brief["title"], "generated_at": brief["generated_at"], "markdown": to_markdown(brief)}]
    st.toast("Brief saved." if state.save_workspace() else "Could not save the workspace file.")
md = to_markdown(brief)
fname = "".join(ch if ch.isalnum() else "_" for ch in brief["title"])[:60]
b3.download_button("Download Markdown", md.encode("utf-8"), f"{fname}.md", "text/markdown", use_container_width=True)
if PDF_AVAILABLE:
    b4.download_button("Download PDF", brief_to_pdf(brief), f"{fname}.pdf", "application/pdf", use_container_width=True)
else:
    b4.caption("PDF export needs `reportlab` (pip install reportlab).")

# ---- render ---------------------------------------------------------------
st.markdown(f'<div class="as-card" style="border-top:4px solid #0D9488"><div class="as-kicker">AniScope AI · Opportunity Brief</div>'
            f'<h2 style="margin:4px 0">{escape(brief["title"])}</h2>'
            f'<div style="color:#6B7280;font-size:.85rem">Generated {escape(brief["generated_at"])} · decision support, '
            f'not independently verified · print with Ctrl+P</div></div>', unsafe_allow_html=True)
for i, (head, items) in enumerate(brief["sections"].items(), 1):
    body = "".join(f"<li>{escape(str(x))}</li>" for x in items)
    accent = "#E76F51" if head == "Risks and limitations" else "#E5E7EB"
    st.markdown(f'<div class="as-card" style="border-left:4px solid {accent}"><h4>{i}. {escape(head)}</h4>'
                f'<ul style="margin:0;padding-left:18px">{body}</ul></div>', unsafe_allow_html=True)

st.markdown("#### Tabular exports")
e1, e2, e3 = st.columns(3)
e1.download_button("Aspect findings (CSV)", to_csv_bytes(aspects_df), "aspect_findings.csv", "text/csv",
                   disabled=aspects_df.empty, use_container_width=True)
e2.download_button("Trend metrics (CSV)", to_csv_bytes(trend_table), "trend_metrics.csv", "text/csv",
                   disabled=trend_table.empty, use_container_width=True)
assump_rows = pd.DataFrame([{**(a_dict or {}), **{k: v for k, v in (calc or {}).items() if k not in ("errors", "warnings")}}]) if a_dict else pd.DataFrame()
e3.download_button("Assumptions & estimates (CSV)", to_csv_bytes(assump_rows), "assumptions_estimates.csv", "text/csv",
                   disabled=assump_rows.empty, use_container_width=True)
