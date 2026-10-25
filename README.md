# AniScope AI

**Anime audience intelligence and commercial-opportunity platform** — a B2B decision-support tool for Japanese entertainment companies investigating opportunities in India.

Built for the challenge *"Converting Japanese Pop Culture & Content Fandom into Sustainable Revenue in India."*

Workflow: **Discover attention → Understand audience responses → Find an underexplored angle → Shape a localized offer → Explore commercialization → Plan validation → Brief the team.**

AniScope separates **observed data**, **calculated** metrics, **interpretations**, **hypotheses** and **user assumptions**, and labels each on screen. It never invents trends, reviews, Indian market statistics or revenue.

---

## 1. Run it on Windows (VS Code)

Requires **Python 3.10–3.13** ([python.org](https://www.python.org/downloads/); tick "Add python.exe to PATH").

Open the `AniScopeAI` folder in VS Code, then open a terminal (**Terminal → New Terminal**, PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**Put your data in place.** Copy these files from your dataset builder output into `data\raw\`:

- `anime_catalog_all_titles.csv` (or `.jsonl` — both work; `.jsonl` is preferred if present)
- `dataset_manifest.json`
- `trend_observations_template.csv`, `review_evidence_template.csv`

Or leave them where they are and point AniScope at that folder: copy `.env.example` to `.env` and set

```
ANISCOPE_DATA_DIR=C:\Users\Jagrit mittal\AppData\Local\Programs\Microsoft VS Code\aniscope_data
```

**Integrate your evidence (once):**

```powershell
python scripts\ingest.py status
python scripts\ingest.py trends "data\raw\trends_india_batch_*.csv" --geo India
python scripts\ingest.py audit-mal
python scripts\ingest.py reviews-kaggle data\raw\reviews.csv --cap 20 --min-reviews 5
```

Also place `animes.csv` (2020 MAL snapshot) in `data\raw\` for the visibility layer. The 25 Trends titles are linked through `data\mappings\trend_query_map.csv` (MyAnimeList ids, verified). This zip already contains the processed Trends store, so Trending Radar works immediately. See `INTEGRATION_REPORT.md`.

**Launch the app (final design):**

```powershell
python run_web.py
```

Opens http://127.0.0.1:8000 with the cinematic intro, then the six AniScope screens. The original Streamlit interface still works with `streamlit run app.py` — both use the same data, analytics and workspace. See `MERGE_REPORT.md`.

**Launch the Streamlit interface (original layout):**

```powershell
streamlit run app.py
```

The app opens at http://localhost:8501. If the catalog is missing, the Command Center explains where to put it instead of crashing.

**Tests:** `python -m pytest -q`

## 2. Screens

| Screen | What it does | Needs |
| --- | --- | --- |
| Command Center | Search all catalog records (titles + alternate titles), filter the full catalog, data-coverage counts, Shinigami, recent activity | Catalog |
| Trending Radar | Import Google Trends CSVs (native format auto-detected), validate, link to catalog, growth vs level, charts, plain-language explanations | Trend observations |
| Audience Intelligence | Import reviews, evidence overview, aspect praise/criticism with verbatim excerpts, **Hidden Gems & Mixed-Response Analyzer** | Review evidence |
| Creative Opportunity Lab | Rules-based, editable concept drafts traced to selected themes | Optional finding |
| Business Opportunity Planner | Localization, monetization & merchandise, distribution, retention; transparent calculator; editable validation plan | User assumptions |
| Opportunity Brief | 9-section brief assembled from the workspace; Markdown, PDF and CSV export; print-friendly | Whatever exists; gaps are listed |
| Data & Methods | Files found, column mapping, import log, methods, licences | — |

Selections flow between screens (title, themes, finding, concept, plan, assumptions, validation plan) and are saved to `data/database/workspace.json`.

## 3. Importing evidence

### Trend observations (Google Trends)
1. Google Trends → Explore. Region **India**, range **Past 5 years**.
2. Compare up to 5 titles; keep **one fixed anchor title in every export** so separate exports can be compared. Prefer the *Topic* suggestion over a plain term.
3. Download the **Interest over time** CSV.
4. Trending Radar → **Import trend data** → upload. Titles are matched to the catalog by exact title or alternate title; ambiguous or unmatched titles must be linked by you before import.

Any other CSV with date, value and title (or `anime_id`) columns also works through the column-mapping form. Values must be 0–100 indices. `<1` is stored as 0 and flagged.

### Review evidence
Use a source whose terms permit it. The included helper uses the AniList API (free for non-commercial use; no mass collection):

```powershell
python scripts\fetch_anilist_reviews.py --ids 154587 21 --per-title 25 --out data\raw\anilist_reviews.csv
```

AniList ids are in the catalog's `anilist.co/anime/<id>` source links. Then Audience Intelligence → **Import review evidence**. Reviews link to the catalog by `anime_id`, MAL id, AniList id, or exact title. *This script could not be run in the build environment (network blocked) — try it on one id first.*

## 4. Methods (what the numbers mean)

- **Trend momentum** — recent window = last 12 weeks (adjustable) before the latest observation; baseline = the 12 weeks before. Change = mean(recent) − mean(baseline); % only when baseline > 0. Fewer than 6 observations in a window → *insufficient*, not ranked. Missing weeks are never filled.
- **Visibility vs momentum** — level = recent mean; quadrants split at the median of the compared series. Only meaningful for series on a shared scale.
- **Sentiment** — VADER (Hutto & Gilbert 2014), a published rule-based English lexicon, used as-is. Not trained or evaluated by this project; no accuracy is claimed. Whole-review labels prefer the reviewer's own score when present.
- **Aspects** — sentence-level keyword taxonomy (14 aspects, editable in `src/theme_extraction.py`) + sentence sentiment. A stance needs ≥3 polar mentions.
- **Hidden Gems candidates** — ≥5 reviews, ≥1 mostly-praised aspect, and either a criticised/divided aspect or ≥30% mixed/negative reviews. The *contrast index* is experimental and unvalidated. Candidates are things to investigate, never "underrated" verdicts.
- **Creative concepts** — rules-based (theme → design levers + seeded generic genre blocks). No external AI service is used.
- **Calculator** — target audience × reach rate → reached × conversion → customers; revenue, variable cost, contribution, result after fixed costs, break-even. All outputs are illustrative estimates from user-entered assumptions.

## 5. Data sources and licences

- **Anime catalog:** [Anime Offline Database](https://github.com/manami-project/anime-offline-database) (manami-project), snapshot 2026-07-04, licensed under the **Open Data Commons Open Database License (ODbL) v1.0** and **Database Contents License (DbCL) v1.0**. Keep this attribution. A redistributed derived database must also be shared under the ODbL. Catalog scores are cross-site averages from global users without vote counts — not Indian data.
- **Google Trends:** relative, sampled 0–100 indices; not search volumes, viewers or buyers.
- **AniList API:** [terms](https://docs.anilist.co/guide/terms-of-use) — free for non-commercial use, no hoarding, commercial use over $150/month needs a licence.
- **MyAnimeList:** its terms restrict aggregating site content; AniScope does not scrape it.

## 6. Project structure

```
app.py                 navigation, theme, sidebar status
config/settings.py     paths (env/.env), thresholds
src/                   data_loader, data_validation, evidence_store, catalog_service, app_data (caching),
                       trend_analysis, review_analysis, theme_extraction, opportunity_engine,
                       concept_builder, business_calculator, brief_generator, export_service, state
views/                 the six screens + Data & Methods
components/            styles (design system), Shinigami (companion), widgets
scripts/               build_catalog_from_aod.py, fetch_anilist_reviews.py
tests/                 unit tests + Streamlit AppTest smoke/workflow tests (synthetic test data only)
```
