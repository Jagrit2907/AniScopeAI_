# AniScope AI — Data Integration Report

Run on 24 Oct 2026 against the files you uploaded. Machine-readable figures are in
`data/processed/integration_report.json`; every import is also in `data/processed/import_log.json`.

## 1. Files received

| File | Status | Used for |
| --- | --- | --- |
| `anime_catalog_all_titles.csv` (41,537 rows) | Received, integrated | Master catalog; key = your `aniscope_catalog_id` |
| `anime_catalog_all_titles.jsonl` | Received, not used | Raw upstream records without `aniscope_catalog_id`; the CSV is preferred so evidence links to your IDs |
| `dataset_manifest.json` | Received, integrated | Snapshot date, licence shown in the app |
| `animes.csv` (Kaggle MAL, 2020) | Received, integrated | 2020 visibility snapshot (MAL members, peer percentile) |
| `trends_india_batch_1…5.csv` | Received, integrated | Trending Radar |
| `profiles.csv` | Received, **deliberately not used** | Contains usernames, gender and birthdays; has no analytic link without reviews, so personal data is not loaded |
| Evidence templates | Received | Headers only (no rows); their column names are now auto-mapped |
| **`reviews.csv` (~651 MB)** | **NOT received** | Needed for Audience Intelligence and Hidden Gems — see section 5 |

All originals were only read. SHA-256 checksums taken before and after processing match for all 11 files.

## 2. Google Trends validation (all five files)

| File | Titles | Dates | Valid / read | Missing | Zeros |
| --- | --- | --- | --- | --- | --- |
| batch_1 | Naruto: Shippuden, Attack on Titan, Demon Slayer, Bleach, One Piece | 2021-10-01 → 2026-10-01 | 305 / 305 | 0 | 0 |
| batch_2 | Dragon Ball Z, Hunter × Hunter, Jujutsu Kaisen, Chainsaw Man, My Hero Academia | same | 305 / 305 | 0 | 15 |
| batch_3 | Blue Lock, Haikyu!!, Wind Breaker, Kuroko's Basketball, Blue Box | same | 305 / 305 | 0 | 82 |
| batch_4 | Frieren, The Apothecary Diaries, Oshi no Ko, Dandadan, Solo Leveling | same | 305 / 305 | 0 | 139 |
| batch_5 | Spy × Family, Mob Psycho 100, Dr. Stone, Vinland Saga, Your Name. | same | 305 / 305 | 0 | 46 |

Total: **1,525 valid monthly observations, 25 titles, 0 rejected rows.**

Findings that change how the data may be read:

- **No geography in the files.** The headers are plain terms ("Time","Naruto: Shippuden",…), not "Naruto: (India)". The *India* label comes from your statement and the file names, supplied explicitly at import (`--geo India`). It does not come from the data.
- **Monthly data**, not weekly. Growth now compares the last 6 months with the 6 before (adjustable).
- **Five independent 0–100 scales with no shared anchor title.** Index levels are not comparable between batches. The app ranks by % change within each series and only compares levels inside one batch.
- **Not known from the files:** whether each column was a Topic or a plain search term.

## 3. Linking Trends titles to the catalog

Exact-title matching was tested and **rejected**: it silently picked wrong records for "Haikyu!!", "Frieren", "Blue Box" and "My Hero Academia". Links now come from `data/mappings/trend_query_map.csv`, which holds 25 rows keyed by MyAnimeList id.

Every id was verified to resolve to exactly one catalog record whose title or synonyms contain the query. Franchise searches (e.g. "Attack on Titan") are linked to the first TV season. That is a stated simplification: the search interest is for the franchise. Edit the CSV to change any link.

## 4. MyAnimeList ↔ catalog mapping (`animes.csv` uid vs catalog `myanimelist_id`)

| Check | Result |
| --- | --- |
| Unique uids in animes.csv (after removing duplicate rows) | 16,216 |
| uids matching exactly one catalog record | 16,036 (98.9%) |
| uids matching several catalog records | 0 |
| uids not in the catalog | 180 |
| Title agreement for matched ids | 99.46% |

The remaining 0.54% are naming variants, not different works (e.g. "Hataraku Saibou (TV)" vs "Hataraku Saibou"). So the ids are treated as the same key, but only through the catalog's `myanimelist_id` column. Nothing is joined on titles.

## 5. Reviews — built, tested at scale, not yet run on your file

`reviews.csv` did not reach this workspace. The chunked importer is ready:

```powershell
# put the file at  data\raw\reviews.csv  (or your ANISCOPE_DATA_DIR folder)
python scripts\ingest.py reviews-kaggle data\raw\reviews.csv --cap 20 --min-reviews 5
```

What it does:

- Reads the file twice in 5,000-row chunks and never loads it whole.
- Never reads the `profile` (username) column.
- Matches `anime_uid` against `animes.csv` `uid`, then against the catalog via MAL id. It prints both match rates, which are also saved in the report.
- Keeps the review link (`source_url`), a source label, and an id per review.
- Leaves geography empty, so the app labels these as international reviews, never Indian sentiment.
- Keeps the 20 longest reviews per title, skips titles with fewer than 5 usable reviews, then runs the sentiment/aspect analysis once and caches it.

**Synthetic scale test** (178 MB file in the same layout; not your data):

| Step | Result |
| --- | --- |
| Import | 42,005 rows in 35 s; peak memory 954 MB (406 MB of that is the catalog) |
| Analysis | 40,423 reviews in 138 s |
| Hidden Gems screening | 15 s worst case, then cached |

Expect roughly 2–3 minutes of import on the real 651 MB file. Its real match rate is **unknown until you run it**.

## 6. What works now with your real data

- Catalog: 41,537 records with your IDs, searchable, filterable.
- Trending Radar: 25 India-labelled titles, monthly growth, reliability flags, per-export comparisons, charts, explanations.
- Visibility: 16,036 titles carry 2020 MAL membership and a same-format/same-year percentile (global, not India). It appears in the catalog card, the brief and the Hidden Gems filter.
- Opportunity Brief: includes real trend results and visibility for the selected title.

## 7. Still incomplete

1. **Audience Intelligence and Hidden Gems have no real review data** until you run step 5.
2. **India labels on Trends rest on your statement**; the files carry no geography.
3. **Cross-batch level comparisons are not valid.** Re-export with one shared anchor title in every batch if you need them.
4. **`animes.csv` is a 2020 snapshot** with no stated licence, scraped from MyAnimeList. Treat it as research-only. Titles released after 2020 (e.g. Frieren, Dandadan) have no visibility figure.
5. **No Indian reviewer data exists in any supplied file.**

## 8. Tests

30 automated tests pass (`python -m pytest -q`). They cover validation, monthly and weekly growth, the query map, the chunked importer (match rates, cap, no usernames stored), the MAL audit, the calculator, the brief, and all screens rendering with and without data.

Separately, the app was run in a browser on the real catalog, real Trends and `animes.csv`, and no screen raised an error.
