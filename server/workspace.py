"""Workspace persistence for the web app (same file and fields as src/state.py).

The Streamlit app keeps these in st.session_state and saves to
data/database/workspace.json; the web app reads and writes the same JSON so
both front ends share one workspace.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime

from config import settings

DEFAULTS = {
    "selected_anime_id": None, "selected_themes": [], "selected_finding": None, "concept": None,
    "plan": None, "assumptions": None, "validation_plan": None, "recent_titles": [],
    "saved_concepts": [], "saved_briefs": [], "concept_variation": 0,
}
_lock = threading.Lock()


def load() -> dict:
    try:
        data = json.loads(settings.WORKSPACE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    out.update({k: v for k, v in data.items() if k in DEFAULTS and v is not None})
    return out


def save(ws: dict) -> bool:
    with _lock:
        try:
            settings.WORKSPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {k: ws.get(k) for k in DEFAULTS}
            payload["saved_at"] = datetime.now().isoformat(timespec="seconds")
            settings.WORKSPACE_FILE.write_text(json.dumps(payload, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
            return True
        except OSError:
            return False


def update(patch: dict) -> dict:
    ws = load()
    for k, v in patch.items():
        if k in DEFAULTS:
            ws[k] = v
    save(ws)
    return ws


def select_title(anime_id: str | None, label: str | None) -> dict:
    """Same rule as src/state.select_title: changing title clears title-bound themes/finding."""
    ws = load()
    if anime_id != ws.get("selected_anime_id"):
        ws["selected_anime_id"] = anime_id
        ws["selected_themes"] = []
        ws["selected_finding"] = None
        if anime_id and label:
            recent = [r for r in ws["recent_titles"] if r.get("id") != anime_id]
            ws["recent_titles"] = [{"id": anime_id, "title": label, "at": datetime.now().strftime("%d %b %H:%M")}] + recent[:7]
        save(ws)
    return ws


def reset() -> dict:
    ws = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    save(ws)
    return ws
