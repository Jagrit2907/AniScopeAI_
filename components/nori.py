"""Shinigami — AniScope's original companion (a rice-ball character wrapped in Shinigami).

Shinigami only communicates; every message is computed by the page from real
application state. Three states:
  guide     — teal, gentle bob: what to do next
  discovery — vermilion sparkle, bounce: explains a finding that exists
  caution   — amber, sway + "!" bubble: a genuine data limitation
"""
from __future__ import annotations

from html import escape

import streamlit as st

STATES = {
    "guide": {"accent": "#0D9488", "label": "Guide", "mouth": "M30 47 Q36 52 42 47", "anim": "Shinigami-bob 3.2s ease-in-out infinite"},
    "discovery": {"accent": "#E76F51", "label": "Discovery", "mouth": "M29 46 Q36 55 43 46", "anim": "Shinigami-hop 1.6s ease-in-out infinite"},
    "caution": {"accent": "#D99A1E", "label": "Caution", "mouth": "M31 49 L41 49", "anim": "Shinigami-sway 2.6s ease-in-out infinite"},
}

_CSS = """
<style>
@keyframes Shinigami-bob { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-3px) } }
@keyframes Shinigami-hop { 0%,100% { transform: translateY(0) } 30% { transform: translateY(-6px) } 60% { transform: translateY(0) } }
@keyframes Shinigami-sway { 0%,100% { transform: rotate(0deg) } 25% { transform: rotate(-4deg) } 75% { transform: rotate(4deg) } }
@keyframes Shinigami-twinkle { 0%,100% { opacity: .2 } 50% { opacity: 1 } }
@keyframes Shinigami-blink { 0%,92%,100% { transform: scaleY(1) } 95% { transform: scaleY(0.1) } }
.Shinigami-wrap { display: flex; gap: 12px; align-items: flex-start; background: #fff; border: 1px solid #E5E7EB;
  border-radius: 16px; padding: 12px 14px; }
.Shinigami-svg { flex: 0 0 64px; }
.Shinigami-eye { transform-origin: center; animation: Shinigami-blink 5s infinite; transform-box: fill-box; }
.Shinigami-bubble { font-size: 0.88rem; color: #1F2937; line-height: 1.45; }
.Shinigami-tag { display: inline-block; font-size: 0.68rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  border-radius: 6px; padding: 1px 7px; margin-bottom: 4px; color: #fff; }
</style>
"""


def svg(state: str = "guide", size: int = 64) -> str:
    s = STATES.get(state, STATES["guide"])
    extra = ""
    if state == "discovery":
        extra = (f'<g style="animation: Shinigami-twinkle 1.4s infinite"><path d="M60 8 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="{s["accent"]}"/></g>'
                 f'<circle cx="10" cy="14" r="2.2" fill="{s["accent"]}" style="animation: Shinigami-twinkle 1.9s infinite"/>')
    if state == "caution":
        extra = (f'<circle cx="60" cy="12" r="9" fill="{s["accent"]}"/>'
                 '<rect x="58.8" y="6" width="2.4" height="8" rx="1.2" fill="#fff"/><circle cx="60" cy="17" r="1.4" fill="#fff"/>')
    return f"""<svg class="Shinigami-svg" width="{size}" height="{size}" viewBox="0 0 72 72" role="img" aria-label="Shinigami, {s['label']} state">
  <g style="animation: {s['anim']}; transform-origin: 36px 60px;">
    <path d="M36 6 C50 6 64 34 64 48 C64 60 52 66 36 66 C20 66 8 60 8 48 C8 34 22 6 36 6 Z" fill="#FBFBF8" stroke="#D6D3CC" stroke-width="1.5"/>
    <path d="M14 50 L58 50 C60 56 58 62 50 64 L22 64 C14 62 12 56 14 50 Z" fill="#1E2B26"/>
    <path d="M14 50 L58 50" stroke="{s['accent']}" stroke-width="2.5"/>
    <ellipse class="Shinigami-eye" cx="28" cy="38" rx="2.6" ry="3.4" fill="#111827"/>
    <ellipse class="Shinigami-eye" cx="44" cy="38" rx="2.6" ry="3.4" fill="#111827"/>
    <circle cx="22" cy="44" r="3" fill="{s['accent']}" opacity="0.28"/><circle cx="50" cy="44" r="3" fill="{s['accent']}" opacity="0.28"/>
    <path d="{s['mouth']}" stroke="#111827" stroke-width="2" fill="none" stroke-linecap="round"/>
  </g>{extra}
</svg>"""


def render(state: str, message: str, notes: list[str] | None = None) -> None:
    """Show Shinigami with a message. ``message`` must describe real app state."""
    s = STATES.get(state, STATES["guide"])
    extra = ""
    if notes:
        extra = "".join(f'<div style="margin-top:4px;color:#8A6212">⚠ {escape(n)}</div>' for n in notes[:3])
    st.markdown(_CSS + f'<div class="Shinigami-wrap">{svg(state)}<div class="Shinigami-bubble">'
                f'<span class="Shinigami-tag" style="background:{s["accent"]}">Shinigami · {s["label"]}</span><br>'
                f'{escape(message)}{extra}</div></div>', unsafe_allow_html=True)


def speak(cautions: list[str], discoveries: list[str], guide: str) -> str:
    """Pick Shinigami's state from genuine conditions and render it.

    A real finding → Discovery (remaining cautions listed underneath);
    no finding but a limitation → Caution; otherwise → Guide. Returns the state.
    """
    if discoveries:
        render("discovery", discoveries[0], cautions)
        return "discovery"
    if cautions:
        render("caution", cautions[0], cautions[1:])
        return "caution"
    render("guide", guide)
    return "guide"

