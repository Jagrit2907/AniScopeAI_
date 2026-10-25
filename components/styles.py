"""Design system: palette, typography and reusable HTML blocks."""
from __future__ import annotations

from html import escape

import streamlit as st

NAVY = "#111827"
SLATE = "#273449"
TEAL = "#0D9488"
VERMILION = "#E76F51"
AMBER = "#D99A1E"
INK = "#1F2937"
MUTED = "#6B7280"
LINE = "#E5E7EB"
SURFACE = "#F7F8FA"

PLOT_COLORS = [TEAL, VERMILION, "#3B6EA8", AMBER, "#7C5CBF", "#5B8C5A"]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Zen+Kaku+Gothic+New:wght@500;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText {{ font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }}
.block-container {{ padding-top: 3.4rem; padding-bottom: 3rem; max-width: 1240px; }}
h1, h2, h3 {{ font-family: 'Zen Kaku Gothic New', 'Inter', sans-serif; color: {NAVY}; letter-spacing: -0.01em; }}
[data-testid="stSidebar"] {{ background: {NAVY}; }}
[data-testid="stSidebar"] * {{ color: #E5E7EB; }}
[data-testid="stSidebar"] .stButton button {{ background: {SLATE}; border: 1px solid #3A4A63; color: #F3F4F6; }}
[data-testid="stSidebarNav"] a span {{ color: #D1D5DB !important; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: rgba(13,148,136,0.22); border-radius: 8px; }}
.stButton button[kind="primary"] {{ background: {TEAL}; border-color: {TEAL}; }}
.stButton button[kind="primary"]:hover {{ background: #0B7F75; border-color: #0B7F75; }}
div[data-testid="stMetric"] {{ background: #fff; border: 1px solid {LINE}; border-radius: 12px; padding: 12px 14px; }}
div[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: 0.78rem; white-space: normal; }}
div[data-testid="stMetricLabel"] {{ min-height: 2.1em; }}
div[data-testid="stMetricValue"] {{ font-size: 1.45rem; font-weight: 600; color: {NAVY}; }}
div[data-testid="stMetricValue"] * {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; overflow-wrap: anywhere; }}
.as-hero {{ background: linear-gradient(120deg, {NAVY} 0%, {SLATE} 70%, #1E4E5C 100%); color: #F9FAFB;
  border-radius: 18px; padding: 28px 30px; position: relative; overflow: hidden; }}
.as-hero h1 {{ color: #fff; font-size: 2.3rem; margin: 0 0 6px 0; }}
.as-hero p {{ color: #CBD5E1; font-size: 1.05rem; margin: 0; max-width: 640px; }}
.as-hero .as-kanji {{ position: absolute; right: 26px; top: -12px; font-size: 7.5rem; color: rgba(255,255,255,0.05);
  font-family: 'Zen Kaku Gothic New', serif; user-select: none; }}
.as-flow {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 16px; }}
.as-flow span {{ background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.14); color: #E2E8F0;
  border-radius: 999px; padding: 4px 11px; font-size: 0.8rem; }}
.as-kicker {{ color: {TEAL}; font-weight: 600; font-size: 0.78rem; letter-spacing: 0.12em; text-transform: uppercase; }}
.as-pagehead h1 {{ margin: 2px 0 4px 0; font-size: 1.9rem; }}
.as-pagehead p {{ color: {MUTED}; margin: 0 0 6px 0; }}
.as-card {{ background: #fff; border: 1px solid {LINE}; border-radius: 14px; padding: 16px 18px; margin-bottom: 10px; }}
.as-card h4 {{ margin: 0 0 6px 0; color: {NAVY}; font-size: 1rem; }}
.as-label {{ display: inline-block; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  border-radius: 6px; padding: 2px 7px; margin-right: 6px; }}
.as-observed {{ background: #E6F4F2; color: #0B6B62; }}
.as-calc {{ background: #E8EEF7; color: #2F4F7F; }}
.as-interp {{ background: #F3ECFB; color: #5E3F8F; }}
.as-hyp {{ background: #FDEEE9; color: #A4472F; }}
.as-assume {{ background: #FFF5DD; color: #8A6212; }}
.as-quote {{ border-left: 3px solid {TEAL}; padding: 6px 12px; margin: 6px 0; color: {INK}; background: {SURFACE};
  border-radius: 0 8px 8px 0; font-size: 0.92rem; }}
.as-quote.neg {{ border-left-color: {VERMILION}; }}
.as-quote .src {{ display: block; color: {MUTED}; font-size: 0.75rem; margin-top: 4px; }}
.as-empty {{ border: 1.5px dashed #CBD5E1; border-radius: 14px; padding: 22px; background: {SURFACE}; color: {INK}; }}
.as-empty h4 {{ margin: 0 0 6px 0; color: {NAVY}; }}
.as-pill {{ display: inline-block; background: {SURFACE}; border: 1px solid {LINE}; border-radius: 999px;
  padding: 2px 10px; margin: 2px 4px 2px 0; font-size: 0.8rem; color: {INK}; }}
.as-status {{ font-size: 0.8rem; line-height: 1.6; }}
.as-status b {{ color: #fff; }}
.as-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
.as-formula {{ font-family: ui-monospace, 'Cascadia Code', Consolas, monospace; font-size: 0.85rem; background: {SURFACE};
  border: 1px solid {LINE}; border-radius: 8px; padding: 8px 12px; }}
@media print {{ [data-testid="stSidebar"], header, .no-print {{ display: none !important; }} }}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def label(kind: str) -> str:
    """Badge marking the epistemic status of a statement."""
    names = {"observed": "Observed data", "calc": "Calculated", "interp": "Interpretation",
             "hyp": "Hypothesis", "assume": "Assumption"}
    return f'<span class="as-label as-{kind}">{names[kind]}</span>'


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(f'<div class="as-pagehead"><div class="as-kicker">{escape(kicker)}</div>'
                f'<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>', unsafe_allow_html=True)


def empty_state(title: str, body: str) -> None:
    st.markdown(f'<div class="as-empty"><h4>{escape(title)}</h4>{body}</div>', unsafe_allow_html=True)


def pills(items: list[str]) -> str:
    return "".join(f'<span class="as-pill">{escape(str(i))}</span>' for i in items)
