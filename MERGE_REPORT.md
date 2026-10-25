# AniScope AI — Design Merge Report

**Launch:** `pip install -r requirements.txt` then `python run_web.py` → http://127.0.0.1:8000

## 1. Integration approach and why

The final design is one self-contained HTML/CSS/JS page with a full-screen intro, custom cursor, modals and toasts driven by inline scripts. Streamlit cannot host it faithfully:

- `st.markdown` strips `<script>`.
- `components.html` runs in a sandboxed iframe that cannot drive Streamlit widgets.

So the merge keeps **all Python analytics unchanged** in `src/` and serves the design as the front end through a thin FastAPI layer. Every endpoint calls the same functions the Streamlit screens use:

- `candidate_table`, `series_growth`, `explain`
- `evidence_overview`, `aspect_summary`, `find_candidates`
- `build_concept`, `calculate`, `build_brief`
- the export functions and the ingest pipeline

No trend, sentiment, aspect or candidate logic was rewritten in JavaScript. The Streamlit app still runs (`streamlit run app.py`) and shares the same data and workspace file.

## 2. Design preservation

| Design element | Status |
| --- | --- |
| CSS variables, gradients, typography, cards, radii, shadows, hover glows, responsive rules | `web/design.css` is lines 11–875 of `final_design.html`, **byte-for-byte** |
| Intro (curtains, hand-sign panels, kanji stamp + shadow-clone split, title slam, chips, flashes, particles), 3.7 s timeline | `web/design-engine.js` is the design's script, **verbatim**. Intro text changed only: KIZUNA → ANISCOPE, 絆 → 観, chips → AniScope capabilities |
| Sound engine, sound toggle, skip (button + Esc), replay button | Verbatim; replay sits in the nav as before |
| Custom cursor, card spotlight, toasts, modal open/close | Verbatim |
| Nav, hero, stat boxes, rotated ticker, map / merch / flow / scanner / partners card layouts | Same markup classes, repurposed for AniScope content (section 4) |

New components (tables, charts, forms, Shinigami, quotes) live in `web/aniscope.css` and are built only from the design's variables and effects.

## 3. Feature inventory (previous app → merged app)

| Feature | Previous implementation | Data | Works before | Where it is now |
| --- | --- | --- | --- | --- |
| Catalog search (titles + alternate titles, 41,537 records) | `catalog_service.search` | catalog CSV | Yes | Command → Evidence Lookup; Audience title search; `/api/search` |
| Title detail (metadata, ids, sources, visibility, coverage) | `widgets.catalog_card`, `visibility.describe` | catalog, `animes.csv` | Yes | "Details" modal on every screen |
| Data coverage / status | `app_data.coverage`, sidebar | all stores | Yes | Hero stat boxes, "Data Status" modal, Data & Methods |
| Trending Radar: market, window, date filters, candidates, reliability, % ranking across exports | `trend_analysis` | `trend_observations.csv` | Yes | Radar screen (table, filters) |
| Trend chart with baseline/recent bands + explanation | Plotly + `explain` | trends | Yes | Radar + Command "India Search Pulse" (SVG in design style) |
| Multi-series compare with cross-export warning | Plotly multiselect | trends | Yes | Radar → Compare |
| Visibility vs momentum quadrant per export | `level_vs_momentum` | trends | Yes | Radar → quadrant with export selector |
| Trend CSV import + validation report | `pipeline.import_trends_file` | upload | Yes | Radar → Import card (`/api/import/trends`) |
| Audience overview, reception, aspect stances, excerpts with source links | `review_analysis`, `theme_extraction` | review store + analysis cache | Yes | Audience screen |
| Reviewer score distribution | (scores were shown as mean/sd) | review store | Partly | Audience → histogram (added from the same `score_10` field) |
| Theme selection → workspace finding | Streamlit multiselect | — | Yes | Audience → "Save selected themes" |
| Small review CSV import | `pipeline.import_reviews_file` | upload | Yes | Audience → Import card |
| Hidden Gems: min reviews, element filter, low-visibility filter, candidate cards, use-finding | `opportunity_engine.find_candidates` | reviews, visibility, trends | Yes | Gems screen |
| Creative Lab: themes, objective, insight, build, variation, edit, save, send to planner, evidence trail | `concept_builder` | workspace | Yes | Lab screen |
| Planner: start point, hypothesis, 4 areas + notes, calculator, demo assumptions, formulas, validation plan + suggest | `business_calculator` | workspace | Yes | Planner screen |
| Opportunity Brief, Markdown/PDF/CSV exports, save, print | `brief_generator`, `export_service` | all | Yes | Brief screen |
| Shinigami: Guide / Discovery / Caution from real conditions | `components/Shinigami.py` | per screen | Yes | Floating companion (click to minimise), same rules |
| Workspace persistence, reset, recent titles | `src/state.py` | `workspace.json` | Yes | `server/workspace.py`, same file and fields |
| Large `reviews.csv` ingest, MAL audit, status | `scripts/ingest.py` | raw files | Yes | Unchanged CLI; commands shown on Data & Methods |

## 4. Kizuna content replaced

| Design section | Kizuna content (removed) | AniScope content (now) |
| --- | --- | --- |
| Map card | 8 Indian cities with invented demand numbers | **India Search Pulse**: tracked titles with measured % change, trend chart, latest index, reliability |
| Merch card | Prices, "rights holder verified" claims, UPI checkout | **Rising in India**: top measured risers (sufficient data only) with Investigate / Details |
| Creator patronage board | Invented pledges, escrow and UPI payouts | **Evidence Coverage**: tracked titles with / without linked reviews, plus your workspace |
| Tag scanner | Fake authenticity certificates | **Evidence Lookup**: real catalog search showing exactly which evidence a title has |
| Partners bar | JETRO, Bandai etc. as "official network" | **Data sources** (Anime Offline Database, Google Trends, MAL 2020, VADER), no partner claims |
| Hero stats | "8 Metros", "100% Verified", "₹1,840+", "JETRO & Bandai" | Live counts: catalog records, India-tracked titles, reviews, visibility titles |
| Ticker | Static title names | Tracked titles with their measured % change |
| Wallet button / modals | UPI connect, checkout, payment success | "Data Status" modal (real file and coverage report), title detail modal |

## 5. Data and identifiers

- **Catalog:** 41,537 records keyed by `aniscope_catalog_id`. Trend observations already use these IDs. All 25 tracked titles resolve to catalog records in the running app, labelled e.g. "Sousou no Frieren (TV, 2023)".
- **Your review store was not available in this workspace.** Your note mentions ~48,105 reviews across 3,451 titles, with 13 of the 25 tracked titles linked. That store was not uploaded, so I could not confirm those figures.
- **What the app does with it:** reads `data/processed/review_evidence.csv` and the analysis cache from your machine through the unchanged pipeline. Titles without linked reviews show the "No linked review evidence" state, and the Evidence Coverage board counts them; nothing is filled in.
- **How review screens were checked:** with a clearly-labelled synthetic store in a separate scratch folder (the source shows as "SYNTHETIC scale test"). It is not in the package.

## 6. Tests

`python -m pytest -q` → **36 passed**:

- 30 existing tests: data validation, trends, calculator, brief, pipeline, Streamlit screens.
- 6 new API tests in `tests/test_web_api.py`: status counts, monthly growth matching `src/`, honest empty review state, gems → workspace → concept → calculator → brief → exports, invalid calculator input, unknown title.

Browser checks with headless Chromium:

- On the real catalog and Trends: the intro is active at 2.9 s and finished by 6.4 s, all eight screens rendered, and no JavaScript errors were raised.
- On the synthetic review store: Audience and Hidden Gems rendered. Saving themes showed its toast only after the server confirmed, and a concept built from the saved theme.

## 7. Files

**Added:**
- `run_web.py`
- `server/` (`api.py`, `data.py`, `workspace.py`)
- `web/index.html`, `web/design.css`, `web/design-engine.js`, `web/aniscope.css`, `web/app.js`
- `tests/test_web_api.py`
- `MERGE_REPORT.md`

**Modified:** `requirements.txt` (fastapi, uvicorn, python-multipart, httpx), `README.md` (launch command).

**Unchanged:** everything in `src/`, `config/`, `scripts/`, `views/`, `components/`, and the data stores.

## 8. Limitations

- Fonts load from Google Fonts. Offline, the browser falls back to system fonts; the layout still works.
- The intro's sound starts after the first click or keypress, as the browser's autoplay policy requires. This is the design's own behaviour.
- The intro still shows the design's 影分身の術 / "SHADOW CLONE TECHNIQUE" banner and hand-sign panels. Only the product name, kanji mark and chips were rebranded.
- The web app is single-user: the workspace is one local JSON file, as in the Streamlit version.
- Browser verification of review screens used synthetic data. Please open Audience and Hidden Gems once with your real store.
