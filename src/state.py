"""Shared workspace state (Streamlit session) with optional JSON persistence.

Keys are namespaced so a selection on one screen never overwrites work on
another: changing the selected title does not erase a saved concept or plan.
"""
from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from config import settings

DEFAULTS = {
    "selected_anime_id": None,
    "selected_themes": [],          # aspects chosen in Audience Intelligence
    "selected_finding": None,       # dict describing an audience finding
    "concept": None,                # current Creative Lab concept (editable)
    "plan": None,                   # Business Planner selections
    "assumptions": None,            # calculator inputs
    "validation_plan": None,
    "recent_titles": [],
    "saved_concepts": [],
    "saved_briefs": [],
    "concept_variation": 0,
}
PERSISTED = ["recent_titles", "saved_concepts", "saved_briefs", "concept", "plan",
             "assumptions", "validation_plan", "selected_anime_id", "selected_themes", "selected_finding"]


def init() -> None:
    if st.session_state.get("_ws_loaded"):
        return
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v if not isinstance(v, list) else list(v))
    saved = load_workspace()
    for k in PERSISTED:
        if k in saved and saved[k] is not None:
            st.session_state[k] = saved[k]
    st.session_state["_ws_loaded"] = True


def load_workspace() -> dict:
    try:
        return json.loads(settings.WORKSPACE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_workspace() -> bool:
    try:
        settings.WORKSPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {k: st.session_state.get(k) for k in PERSISTED}
        data["saved_at"] = datetime.now().isoformat(timespec="seconds")
        settings.WORKSPACE_FILE.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError:
        return False


def select_title(anime_id: str | None, title: str | None = None) -> None:
    if anime_id == st.session_state.get("selected_anime_id"):
        return
    st.session_state["selected_anime_id"] = anime_id
    # Theme selections belong to the previous title's evidence; clear them so
    # findings from one title are never shown for another.
    st.session_state["selected_themes"] = []
    st.session_state["selected_finding"] = None
    if anime_id and title:
        recent = [r for r in st.session_state["recent_titles"] if r["id"] != anime_id]
        st.session_state["recent_titles"] = [{"id": anime_id, "title": title,
                                              "at": datetime.now().strftime("%d %b %H:%M")}] + recent[:7]
    save_workspace()


def reset_workspace() -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v if not isinstance(v, list) else list(v)
    # Clear widget values so forms don't silently re-populate the reset workspace.
    for k in [k for k in st.session_state if str(k).startswith(("calc_", "vp_", "bp_", "themes_"))]:
        del st.session_state[k]
    save_workspace()
