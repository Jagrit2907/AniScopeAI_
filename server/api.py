"""AniScope AI web server: serves the final design (web/) and a JSON API over src/.

Run:  python run_web.py   →  http://127.0.0.1:8000

Every endpoint calls the existing analytics in src/ (the same functions the
Streamlit screens use). The browser only renders results.
"""
from __future__ import annotations

import math
import tempfile
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from config import settings
from server import data, workspace
from src import catalog_service, evidence_store, ml_sentiment, pipeline
from src.brief_generator import build_brief, to_markdown
from src.business_calculator import FORMULAS, Assumptions, as_dict, calculate
from src.concept_builder import build_concept
from src.data_loader import catalog_summary, discover_files
from src.export_service import PDF_AVAILABLE, brief_to_pdf, to_csv_bytes
from src.opportunity_engine import NEXT_STEP_BY_ASPECT
from src.review_analysis import METHOD, evidence_overview, excerpt
from src.theme_extraction import ASPECT_TAXONOMY, aspect_summary
from src.trend_analysis import candidate_table, detect_frequency, explain, level_vs_momentum, series_growth
from src.visibility import describe as describe_visibility

WEB_DIR = settings.PROJECT_ROOT / "web"
app = FastAPI(title="AniScope AI", docs_url="/api/docs", redoc_url=None)


# ------------------------------------------------------------------ helpers --
def clean(obj):
    """Make pandas/numpy values JSON-safe (NaN/NA → None, timestamps → ISO dates)."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return [clean(r) for r in obj.to_dict("records")]
    if isinstance(obj, pd.Series):
        return clean(obj.to_dict())
    if isinstance(obj, (pd.Timestamp, datetime)):
        return None if pd.isna(obj) else obj.strftime("%Y-%m-%d")
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, np.generic):
        obj = obj.item()
    if obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def ok(payload) -> JSONResponse:
    return JSONResponse(clean(payload))


def need_catalog() -> pd.DataFrame:
    df = data.catalog()
    if df is None:
        r = data.catalog_result()
        raise HTTPException(503, detail={"code": "catalog_missing", "message": r.error,
                                         "data_dir": str(settings.RAW_DATA_DIR)})
    return df


def record(anime_id: str | None) -> pd.Series | None:
    idx = data.catalog_index()
    if idx is None or not anime_id or anime_id not in idx.index:
        return None
    return idx.loc[anime_id]


def label(rec: pd.Series) -> str:
    return catalog_service.label(rec)


def rec_dict(rec: pd.Series) -> dict:
    return {"anime_id": rec["anime_id"], "title": rec["title"], "label": label(rec), "type": rec["type"],
            "year": rec["year"], "season": rec["season"], "episodes": rec["episodes"], "status": rec["status"],
            "score": rec["score"], "tags": list(rec["tags"])[:14], "synonyms": list(rec["synonyms"])[:8],
            "sources": list(rec["sources"])[:6], "mal_id": rec["mal_id"], "anilist_id": rec["anilist_id"]}


def coverage() -> dict:
    t = data.trends()
    r, _ = data.reviews()
    return {"trend_titles": int(t["anime_id"].nunique()) if not t.empty else 0, "trend_obs": int(len(t)),
            "trend_last": None if t.empty else t["date"].max(),
            "trend_geos": sorted(t["geo"].dropna().unique().tolist()) if not t.empty else [],
            "trend_exports": int(t["batch_id"].nunique()) if not t.empty else 0,
            "review_titles": int(r["anime_id"].nunique()) if not r.empty else 0, "reviews": int(len(r)),
            "visibility_titles": int(len(data.visibility()))}


# ------------------------------------------------------------------- status --
@app.get("/api/status")
def status():
    res = data.catalog_result()
    files = {k: (v.name if v else None) for k, v in discover_files(settings.RAW_DATA_DIR).items()}
    for n in ("animes.csv", "reviews.csv"):
        files[n] = n if (settings.RAW_DATA_DIR / n).exists() else None
    manifest = res.manifest or {}
    lic = manifest.get("source_license_name") or manifest.get("license")
    return ok({"catalog_ok": res.ok, "catalog_error": res.error, "data_dir": str(settings.RAW_DATA_DIR),
               "catalog_file": res.path.name if res.path else None,
               "summary": catalog_summary(res.df) if res.ok else None,
               "snapshot": manifest.get("upstream_snapshot_date") or manifest.get("snapshot_date"),
               "license": lic.get("name") if isinstance(lic, dict) else lic,
               "coverage": coverage() if res.ok else None, "files": files,
               "analysis_cache": pipeline.load_analysis_cache() is not None,
               "sentiment_method": METHOD, "pdf_available": PDF_AVAILABLE,
               "import_log": evidence_store.read_import_log()[-8:]})


# ------------------------------------------------------------------ catalog --
@app.get("/api/search")
def search(q: str = Query("", max_length=200), limit: int = 25):
    df = need_catalog()
    hits = catalog_service.search(df, q, limit=min(limit, 60))
    t = data.trends()
    r, _ = data.reviews()
    tset = set(t["anime_id"]) if not t.empty else set()
    rset = set(r["anime_id"]) if not r.empty else set()
    rows = [{"anime_id": h.anime_id, "label": catalog_service.label(pd.Series(h._asdict())), "title": h.title,
             "has_trends": h.anime_id in tset, "has_reviews": h.anime_id in rset}
            for h in hits.itertuples(index=False)]
    # Stable re-order: records that carry evidence first, otherwise keep search ranking.
    rows.sort(key=lambda x: (not (x["has_trends"] or x["has_reviews"])))
    return ok(rows)


@app.get("/api/title/{anime_id}")
def title(anime_id: str):
    need_catalog()
    rec = record(anime_id)
    if rec is None:
        raise HTTPException(404, "Unknown catalog id")
    t = data.trends()
    r, _ = data.reviews()
    vrow = data.visibility_row(anime_id)
    return ok({"record": rec_dict(rec),
               "visibility": None if data.visibility().empty else describe_visibility(vrow),
               "trend_obs": int((t["anime_id"] == anime_id).sum()) if not t.empty else 0,
               "reviews": int((r["anime_id"] == anime_id).sum()) if not r.empty else 0})


# ------------------------------------------------------------------- trends --
@app.get("/api/trends")
def trends_table(market: str | None = None, months: int = settings.TREND_WINDOW_MONTHS,
                 weeks: int = settings.TREND_WINDOW_WEEKS, start: str | None = None, end: str | None = None):
    need_catalog()
    t = data.trends()
    if t.empty:
        return ok({"empty": True, "rows": [], "markets": []})
    markets = sorted(t["geo"].dropna().unique().tolist()) + (["Unspecified geography"] if t["geo"].isna().any() else [])
    market = market or ("India" if "India" in markets else markets[0])
    sub = t[t["geo"].isna()] if market == "Unspecified geography" else t
    geo = None if market == "Unspecified geography" else market
    freq = detect_frequency(sub["date"])
    table, results = (candidate_table(sub, None, geo, start, end, window_months=months) if freq == "monthly"
                      else candidate_table(sub, weeks, geo, start, end))
    if table.empty:
        return ok({"empty": False, "rows": [], "markets": markets, "market": market, "frequency": freq})
    idx = data.catalog_index()
    batch_of = sub.groupby(["anime_id", "query"])["batch_id"].first()
    table["export"] = [batch_of.get((a, q), "") for a, q in zip(table["anime_id"], table["query"])]
    table["title"] = [label(idx.loc[a]) if a in idx.index else a for a in table["anime_id"]]
    multi = table["export"].nunique() > 1
    by_key = {(r.anime_id, r.query): r for r in results}
    table["explanation"] = [explain(by_key[(a, q)]) for a, q in zip(table["anime_id"], table["query"])]
    table["reasons"] = [by_key[(a, q)].reasons for a, q in zip(table["anime_id"], table["query"])]
    order = {"sufficient": 0, "limited": 1, "insufficient": 2}
    rank_key = "pct_change" if multi else "abs_change"
    table = table.assign(_o=table["reliability"].map(order)).sort_values(["_o", rank_key], ascending=[True, False],
                                                                          na_position="last").drop(columns="_o")
    return ok({"empty": False, "markets": markets, "market": market, "frequency": freq, "multi_export": multi,
               "rank_key": rank_key, "window": months if freq == "monthly" else weeks,
               "unit": "month" if freq == "monthly" else "week",
               "date_min": t["date"].min(), "date_max": t["date"].max(),
               "exports": sorted(table["export"].unique().tolist()), "rows": table})


@app.get("/api/trends/series")
def trend_series(anime_id: str, query: str, months: int = settings.TREND_WINDOW_MONTHS,
                 start: str | None = None, end: str | None = None):
    t = data.trends()
    s = t[(t["anime_id"] == anime_id) & (t["query"] == query)]
    if start:
        s = s[s["date"] >= pd.Timestamp(start)]
    if end:
        s = s[s["date"] <= pd.Timestamp(end)]
    if s.empty:
        raise HTTPException(404, "No observations for this series")
    s = s.sort_values("date")
    g = series_growth(s, window_months=months)
    return ok({"points": [{"date": d, "value": v} for d, v in zip(s["date"], s["value"])],
               "geo": g.geo, "export": s["batch_id"].iloc[0], "source": s["source"].iloc[0],
               "recent_window": g.recent_window, "baseline_window": g.baseline_window,
               "explanation": explain(g), "reasons": g.reasons, "reliability": g.reliability})


@app.get("/api/trends/quadrant")
def trend_quadrant(export: str, market: str = "India", months: int = settings.TREND_WINDOW_MONTHS):
    t = data.trends()
    sub = t[t["batch_id"] == export]
    table, _ = candidate_table(sub, None, market, window_months=months)
    if table.empty:
        return ok([])
    idx = data.catalog_index()
    q = level_vs_momentum(table[table["reliability"] != "insufficient"])
    q["title"] = [idx.loc[a, "title"] if a in idx.index else a for a in q["anime_id"]]
    return ok(q[["anime_id", "title", "query", "recent_mean", "abs_change", "quadrant"]])


# ----------------------------------------------------------------- audience --
@app.get("/api/aspects")
def aspects():
    return ok([{"aspect": a, "description": v["description"]} for a, v in ASPECT_TAXONOMY.items()])


@app.get("/api/audience/{anime_id}")
def audience(anime_id: str):
    need_catalog()
    rec = record(anime_id)
    if rec is None:
        raise HTTPException(404, "Unknown catalog id")
    reviews_df, evidence = data.reviews()
    r = reviews_df[reviews_df["anime_id"] == anime_id]
    ev = evidence[evidence["anime_id"] == anime_id]
    ov = evidence_overview(r)
    summ = aspect_summary(ev, settings.ASPECT_MIN_MENTIONS)
    out = {"record": rec_dict(rec), "overview": ov, "method": METHOD,
           "min_reviews": settings.REVIEW_MIN_FOR_ANALYSIS, "min_mentions": settings.ASPECT_MIN_MENTIONS,
           "visibility": None if data.visibility().empty else describe_visibility(data.visibility_row(anime_id))}
    try:
        out["ml"] = {"available": True, "prediction": ml_sentiment.predict_reviews(r["text"].dropna().tolist()) if len(r) else None}
    except ml_sentiment.ModelUnavailable as e:
        out["ml"] = {"available": False, "reason": str(e)}
    except Exception as e:  # noqa: BLE001 - show the failure, never a guessed prediction
        out["ml"] = {"available": False, "reason": f"Model prediction failed ({type(e).__name__})."}
    if not len(r):
        return ok(out)
    out["reception"] = r["overall"].value_counts().to_dict()
    sc = r["score_10"].dropna()
    out["score_hist"] = [{"score": int(k), "count": int(v)} for k, v in sc.round().astype(int).value_counts().sort_index().items()]
    out["aspects"] = summ
    ex = {}
    for a in summ["aspect"]:
        fe = ev[ev["aspect"] == a]
        pos = fe[fe["polarity"] == "positive"].sort_values("compound", ascending=False).head(4)
        neg = fe[fe["polarity"] == "negative"].sort_values("compound").head(4)
        ex[a] = {"positive": [{"text": excerpt(x.sentence), "source": x.source, "url": x.source_url, "date": x.date} for x in pos.itertuples()],
                 "negative": [{"text": excerpt(x.sentence), "source": x.source, "url": x.source_url, "date": x.date} for x in neg.itertuples()],
                 "n_pos": int((fe["polarity"] == "positive").sum()), "n_neg": int((fe["polarity"] == "negative").sum())}
    out["excerpts"] = ex
    return ok(out)


@app.post("/api/audience/{anime_id}/themes")
def choose_themes(anime_id: str, themes: list[str] = Body(..., embed=True)):
    """Save chosen themes and the resulting finding (same structure as the Streamlit screen)."""
    rec = record(anime_id)
    if rec is None:
        raise HTTPException(404, "Unknown catalog id")
    reviews_df, evidence = data.reviews()
    r = reviews_df[reviews_df["anime_id"] == anime_id]
    summ = aspect_summary(evidence[evidence["anime_id"] == anime_id], settings.ASPECT_MIN_MENTIONS)
    chosen = [t for t in themes if t in set(summ["aspect"])]
    ov = evidence_overview(r)
    praised = set(summ.loc[summ["stance"] == "mostly praised", "aspect"])
    criticised = set(summ.loc[summ["stance"] == "mostly criticised", "aspect"])
    finding = None
    if chosen:
        finding = {"anime_id": anime_id, "title": rec["title"], "themes": chosen,
                   "praised": [t for t in chosen if t in praised], "criticised": [t for t in chosen if t in criticised],
                   "n_reviews": ov["records"], "sources": ov.get("sources", []),
                   "summary": f"{rec['title']}: " + "; ".join(
                       f"{row.aspect} {row.stance} ({row.positive}+ / {row.negative}−)"
                       for row in summ[summ["aspect"].isin(chosen)].itertuples())
                       + f" — from {ov['records']} reviews ({', '.join(ov.get('sources', []))}); not India-specific."}
    ws = workspace.select_title(anime_id, label(rec))
    ws = workspace.update({"selected_themes": chosen, "selected_finding": finding})
    return ok({"workspace": ws, "ignored": [t for t in themes if t not in chosen]})


# --------------------------------------------------------------- hidden gems --
@app.get("/api/gems")
def gems(aspect: str | None = None, min_reviews: int = settings.REVIEW_MIN_FOR_ANALYSIS, low_visibility: bool = False):
    need_catalog()
    reviews_df, evidence = data.reviews()
    if reviews_df.empty:
        return ok({"empty": True, "candidates": [], "eligible": 0})
    cands = data.gem_candidates(aspect or None, int(min_reviews))
    vis = data.visibility()
    if low_visibility and not vis.empty:
        cands = [c for c in cands if c.anime_id in vis.index and vis.loc[c.anime_id, "peer_percentile"] <= 50]
    eligible = int((reviews_df["anime_id"].value_counts() >= min_reviews).sum())
    trends = data.trends()
    idx = data.catalog_index()
    out = []
    for c in cands[:20]:
        ev = evidence[evidence["anime_id"] == c.anime_id]
        pos = ev[ev["aspect"].isin(c.praised) & (ev["polarity"] == "positive")].sort_values("compound", ascending=False).head(2)
        neg = ev[ev["aspect"].isin(c.criticised + c.divided) & (ev["polarity"] == "negative")].sort_values("compound").head(2)
        tr = trends[(trends["anime_id"] == c.anime_id) & (trends["geo"].fillna("").str.lower() == "india")] if not trends.empty else trends
        rec = idx.loc[c.anime_id] if c.anime_id in idx.index else None
        out.append({"anime_id": c.anime_id, "title": label(rec) if rec is not None else c.anime_id,
                    "n_reviews": c.n_reviews, "praised": c.praised, "criticised": c.criticised, "divided": c.divided,
                    "mixed_share": c.mixed_share, "score_mean": c.score_mean, "score_std": c.score_std,
                    "contrast_index": c.contrast_index, "why": c.why, "limitations": c.limitations, "next_steps": c.next_steps,
                    "catalog_score": None if rec is None else rec["score"],
                    "india_trend": None if tr.empty else {"latest": float(tr.sort_values("date")["value"].iloc[-1]), "date": tr["date"].max()},
                    "visibility": None if vis.empty else describe_visibility(data.visibility_row(c.anime_id)),
                    "praise": [{"text": excerpt(x.sentence), "source": x.source, "url": x.source_url, "date": x.date} for x in pos.itertuples()],
                    "criticism": [{"text": excerpt(x.sentence), "source": x.source, "url": x.source_url, "date": x.date} for x in neg.itertuples()]})
    return ok({"empty": False, "eligible": eligible, "total": len(cands), "candidates": out,
               "visibility_available": not vis.empty})


@app.post("/api/ml/sentiment")
def ml_sentiment_predict(text: str = Body(..., embed=True)):
    """Trained model prediction for one review text (never a made-up answer)."""
    try:
        return ok(ml_sentiment.predict_text(text))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except ml_sentiment.ModelUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Inference failed: {type(e).__name__}")


@app.post("/api/gems/{anime_id}/use")
def use_gem(anime_id: str, praised: list[str] = Body(...), criticised: list[str] = Body(...),
            why: str = Body(...), n_reviews: int = Body(...)):
    rec = record(anime_id)
    if rec is None:
        raise HTTPException(404, "Unknown catalog id")
    workspace.select_title(anime_id, label(rec))
    ws = workspace.update({"selected_themes": praised + criticised, "selected_finding": {
        "anime_id": anime_id, "title": label(rec), "themes": praised + criticised, "praised": praised,
        "criticised": criticised, "n_reviews": n_reviews,
        "summary": f"{label(rec)}: {why} ({n_reviews} reviews; not India-specific)."}})
    return ok(ws)


# ---------------------------------------------------------------- workspace --
@app.get("/api/workspace")
def get_workspace():
    ws = workspace.load()
    rec = record(ws.get("selected_anime_id"))
    return ok({**ws, "selected_label": label(rec) if rec is not None else None})


@app.post("/api/workspace/select")
def select(anime_id: str = Body(..., embed=True)):
    rec = record(anime_id)
    if rec is None:
        raise HTTPException(404, "Unknown catalog id")
    return ok(workspace.select_title(anime_id, label(rec)))


@app.post("/api/workspace")
def patch_workspace(patch: dict = Body(...)):
    return ok(workspace.update(patch))


@app.post("/api/workspace/reset")
def reset_workspace():
    return ok(workspace.reset())


# ------------------------------------------------------------- creative lab --
@app.post("/api/concept")
def concept(themes: list[str] = Body(...), insight: str = Body(""), audience: str = Body(""),
            objective: str = Body("Original series pitch"), direction: str = Body(""), variation: int = Body(0)):
    if not themes:
        raise HTTPException(400, "Select at least one theme")
    ws = workspace.load()
    c = build_concept(themes, insight, audience, objective, direction, variation,
                      criticised=(ws.get("selected_finding") or {}).get("criticised"))
    workspace.update({"concept": c, "concept_variation": variation})
    return ok(c)


@app.post("/api/concept/save")
def save_concept(concept: dict = Body(...)):
    ws = workspace.load()
    saved = [c for c in ws["saved_concepts"] if c.get("working_title") != concept.get("working_title")] + [concept]
    return ok(workspace.update({"concept": concept, "saved_concepts": saved}))


# ---------------------------------------------------------- business planner --
@app.post("/api/calc")
def calc(a: dict = Body(...)):
    fields = Assumptions.__dataclass_fields__
    try:
        assumptions = Assumptions(**{k: (type(fields[k].default)(v) if v is not None else fields[k].default)
                                     for k, v in a.items() if k in fields})
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"Invalid input: {exc}")
    res = calculate(assumptions)
    workspace.update({"assumptions": as_dict(assumptions)})
    return ok({"result": res, "formulas": FORMULAS, "assumptions": as_dict(assumptions)})


@app.get("/api/planner/meta")
def planner_meta():
    return ok({"formulas": FORMULAS, "next_steps": NEXT_STEP_BY_ASPECT})


# -------------------------------------------------------------------- brief --
def _brief() -> tuple[dict, pd.DataFrame, pd.DataFrame, dict | None, dict | None]:
    res = data.catalog_result()
    ws = workspace.load()
    aid = ws.get("selected_anime_id")
    rec = record(aid)
    trend_info, trend_table = None, pd.DataFrame()
    if rec is not None:
        t = data.trends()
        t = t[t["anime_id"] == aid] if not t.empty else t
        if not t.empty:
            trend_table, results = candidate_table(t)
            if results:
                best = sorted(results, key=lambda r: (r.geo != "India", r.reliability != "sufficient"))[0]
                trend_info = {**best.as_row(), "explanation": explain(best)}
    reviews_df, evidence = data.reviews()
    ov, aspects_df = None, pd.DataFrame()
    if rec is not None:
        ov = evidence_overview(reviews_df[reviews_df["anime_id"] == aid])
        aspects_df = aspect_summary(evidence[evidence["anime_id"] == aid], settings.ASPECT_MIN_MENTIONS)
    themes = ws.get("selected_themes") or []
    aspects_for_brief = aspects_df[aspects_df["aspect"].isin(themes)] if themes and not aspects_df.empty else aspects_df
    a = ws.get("assumptions")
    calc_res = calculate(Assumptions(**a)) if a and a.get("target_audience") else None
    finding = ws.get("selected_finding")
    if finding and rec is not None and finding.get("anime_id") not in (None, aid):
        finding = None
    source = res.path.name if res.ok else "not loaded"
    snap = (res.manifest or {}).get("upstream_snapshot_date") or (res.manifest or {}).get("snapshot_date")
    source += f", snapshot {snap}" if snap else ""
    title_dict = None
    if rec is not None:
        title_dict = {k: (None if (not isinstance(rec[k], list) and pd.isna(rec[k])) else rec[k])
                      for k in ("title", "type", "year", "episodes", "status", "score", "tags")}
        if not data.visibility().empty:
            title_dict["visibility"] = describe_visibility(data.visibility_row(aid))
    brief = build_brief(title=title_dict, trend=trend_info, evidence=ov, aspects=aspects_for_brief.to_dict("records"),
                        finding=finding, concept=ws.get("concept"), plan=ws.get("plan"), assumptions=a,
                        calc=calc_res, validation=ws.get("validation_plan"), catalog_source=source)
    return brief, aspects_df, trend_table, a, calc_res


@app.get("/api/brief")
def brief():
    b, *_ = _brief()
    return ok(b)


@app.post("/api/brief/save")
def save_brief():
    b, *_ = _brief()
    ws = workspace.load()
    saved = (ws.get("saved_briefs") or []) + [{"title": b["title"], "generated_at": b["generated_at"], "markdown": to_markdown(b)}]
    return ok(workspace.update({"saved_briefs": saved}))


def _fname(b: dict, ext: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in b["title"])[:60] + ext


@app.get("/api/brief.md")
def brief_md():
    b, *_ = _brief()
    return Response(to_markdown(b).encode("utf-8"), media_type="text/markdown",
                    headers={"Content-Disposition": f'attachment; filename="{_fname(b, ".md")}"'})


@app.get("/api/brief.pdf")
def brief_pdf():
    b, *_ = _brief()
    pdf = brief_to_pdf(b)
    if pdf is None:
        raise HTTPException(501, "PDF export needs reportlab (pip install reportlab)")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_fname(b, ".pdf")}"'})


@app.get("/api/export/{kind}.csv")
def export_csv(kind: str):
    _, aspects_df, trend_table, a, calc_res = _brief()
    if kind == "aspects":
        df = aspects_df
    elif kind == "trends":
        df = trend_table
    elif kind == "assumptions":
        df = pd.DataFrame([{**(a or {}), **{k: v for k, v in (calc_res or {}).items() if k not in ("errors", "warnings")}}]) if a else pd.DataFrame()
    else:
        raise HTTPException(404, "Unknown export")
    if df is None or df.empty:
        raise HTTPException(404, "Nothing to export yet")
    return Response(to_csv_bytes(df), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


# ------------------------------------------------------------------ imports --
@app.post("/api/import/trends")
async def import_trends(file: UploadFile = File(...), geo: str = Form("")):
    df = need_catalog()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / Path(file.filename or "trends.csv").name
        path.write_bytes(await file.read())
        qmap, problems = pipeline.load_query_map(df)
        rep, total, out = pipeline.import_trends_file(path, data.matcher(), default_geo=geo.strip() or None, query_map=qmap)
        report = pipeline.trend_file_report(path, out, rep)
    data.invalidate()
    return ok({"report": report, "store_total": total, "notes": rep.notes, "map_problems": problems})


@app.post("/api/import/reviews")
async def import_reviews(file: UploadFile = File(...), source: str = Form(""), cap: int = Form(30)):
    need_catalog()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / Path(file.filename or "reviews.csv").name
        path.write_bytes(await file.read())
        rep, total = pipeline.import_reviews_file(path, data.matcher(), source.strip() or None, cap or None)
    pipeline.build_analysis_cache()
    data.invalidate()
    return ok({"report": rep.to_dict(), "store_total": total})


# ------------------------------------------------------------------- static --
@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
