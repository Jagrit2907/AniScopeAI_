"""AniScope backend CLI — validate and import evidence without the UI.

Run from the project folder with the venv active. Original files are only read, never modified.

    python scripts/ingest.py status
    python scripts/ingest.py trends data/raw/trends_india_batch_*.csv --geo India
    python scripts/ingest.py audit-mal                       # how animes.csv uids map to the catalog
    python scripts/ingest.py reviews-kaggle data/raw/reviews.csv --cap 20 --min-reviews 5
    python scripts/ingest.py reviews data/raw/anilist_reviews.csv          # small CSVs (any layout)
    python scripts/ingest.py analyse                          # rebuild sentiment/aspect cache

Every command appends a section to data/processed/integration_report.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from src import evidence_store, pipeline  # noqa: E402
from src.data_loader import catalog_summary, load_catalog  # noqa: E402
from src.data_validation import TitleMatcher  # noqa: E402

REPORT = settings.PROCESSED_DIR / "integration_report.json"


def _catalog():
    res = load_catalog()
    if not res.ok:
        sys.exit(f"Catalog not loaded from {settings.RAW_DATA_DIR}: {res.error}")
    return res


def _record(section: str, payload) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data[section] = {"at": datetime.now().isoformat(timespec="seconds"), "result": payload}
    REPORT.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")


def _animes_path():
    p = settings.RAW_DATA_DIR / "animes.csv"
    return p if p.exists() else None


def cmd_status(_):
    res = load_catalog()
    print(f"Data folder: {settings.RAW_DATA_DIR}")
    print(f"Catalog: {res.path.name if res.path else '—'} · " + (str(catalog_summary(res.df)) if res.ok else res.error))
    for name in ("animes.csv", "reviews.csv", "dataset_manifest.json"):
        p = settings.RAW_DATA_DIR / name
        print(f"{name}: " + (f"present ({p.stat().st_size / 1e6:.1f} MB)" if p.exists() else f"MISSING — expected at {p}"))
    tr, rv = evidence_store.load_trends(), evidence_store.load_reviews()
    print(f"Trend store: {len(tr):,} observations for {tr['anime_id'].nunique():,} titles")
    print(f"Review store: {len(rv):,} reviews for {rv['anime_id'].nunique():,} titles")
    print("Analysis cache: " + ("up to date" if pipeline.load_analysis_cache() is not None else "missing or stale (run: analyse)"))


def cmd_trends(args):
    res = _catalog()
    qmap, problems = pipeline.load_query_map(res.df)
    for p in problems:
        print(f"  ⚠ query map: {p}")
    files = sorted({f for pattern in args.files for f in glob.glob(str(pattern))})
    if not files:
        sys.exit("No trend files matched.")
    m = TitleMatcher(res.df)
    reports = []
    for f in files:
        path = Path(f)
        rep, total, out = pipeline.import_trends_file(path, m, default_geo=args.geo, query_map=qmap)
        r = pipeline.trend_file_report(path, out, rep)
        reports.append(r)
        print(f"\n{path.name}: {r['valid']}/{r['rows_read']} valid · {r['date_min']} → {r['date_max']} · "
              f"missing {r['missing_values']} · zeros {r['zeros']}")
        print(f"  titles: {', '.join(r['titles'])}")
        for reason, n in r["rejected"].items():
            print(f"  ✗ {n}: {reason}")
        if r["unmatched"] or r["ambiguous"]:
            print(f"  unlinked: {r['unmatched'] + r['ambiguous']}")
    geo_note = (f"Geography '{args.geo}' was supplied on the command line (the files contain no geography column)."
                if args.geo else "No geography supplied; observations are NOT labelled India.")
    print(f"\n{geo_note}\nStore now holds {len(evidence_store.load_trends()):,} observations.")
    _record("trends", {"files": reports, "geo_note": geo_note, "query_map_problems": problems})


def cmd_audit(_):
    res = _catalog()
    a = _animes_path()
    if not a:
        sys.exit(f"animes.csv not found at {settings.RAW_DATA_DIR / 'animes.csv'}")
    r = pipeline.mal_mapping_audit(res.df, a)
    for k, v in r.items():
        print(f"  {k}: {v}")
    _record("mal_mapping_audit", r)


def cmd_reviews_kaggle(args):
    res = _catalog()
    if not args.file.exists():
        sys.exit(f"File not found: {args.file}\nCopy reviews.csv to {settings.RAW_DATA_DIR / 'reviews.csv'} and retry.")
    t0 = time.time()

    def progress(stage, n):
        print(f"\r  {'Pass 1 (scan)' if stage == 'scan' else 'Pass 2 (write)'}: {n:,} rows", end="", flush=True)
    stats = pipeline.import_reviews_chunked(args.file, res.df, _animes_path(), args.source, args.cap or None,
                                            args.min_reviews, progress=progress)
    print(f"\n  done in {time.time() - t0:.0f}s")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    _record("reviews_kaggle", stats)
    if not args.no_analyse:
        cmd_analyse(args)


def cmd_reviews(args):
    res = _catalog()
    rep, total = pipeline.import_reviews_file(args.file, TitleMatcher(res.df), args.source, args.cap or None)
    print(f"  read {rep.rows_read:,} · valid {rep.rows_valid:,} · rejected {rep.rows_rejected:,}")
    for reason, n in rep.rejected.items():
        print(f"    ✗ {n:,}: {reason}")
    for note in rep.notes:
        print(f"    ℹ {note}")
    _record(f"reviews:{args.file.name}", rep.to_dict())
    cmd_analyse(args)


def cmd_analyse(_):
    t0 = time.time()

    def progress(frac, msg):
        print(f"\r  {msg} ({frac:.0%})", end="", flush=True)
    scored, ev = pipeline.build_analysis_cache(progress)
    print(f"\n  analysed {len(scored):,} reviews → {len(ev):,} aspect mentions in {time.time() - t0:.0f}s")
    _record("analysis", {"reviews": len(scored), "aspect_mentions": len(ev),
                         "titles": int(scored["anime_id"].nunique()) if len(scored) else 0})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    t = sub.add_parser("trends", help="Import one or more Google Trends CSVs")
    t.add_argument("files", nargs="+")
    t.add_argument("--geo", default=None, help="Market the exports cover, e.g. India (files without a geography column)")
    t.set_defaults(fn=cmd_trends)
    sub.add_parser("audit-mal", help="Check animes.csv uid ↔ catalog MAL id mapping").set_defaults(fn=cmd_audit)
    k = sub.add_parser("reviews-kaggle", help="Stream the large Kaggle reviews.csv")
    k.add_argument("file", type=Path)
    k.add_argument("--source", default="MyAnimeList reviews (Kaggle 2020 snapshot)")
    k.add_argument("--cap", type=int, default=20, help="Max reviews per title (longest kept); 0 = all")
    k.add_argument("--min-reviews", type=int, default=5, help="Skip titles with fewer usable reviews")
    k.add_argument("--no-analyse", action="store_true")
    k.set_defaults(fn=cmd_reviews_kaggle)
    r = sub.add_parser("reviews", help="Import a small review CSV (column names auto-mapped)")
    r.add_argument("file", type=Path)
    r.add_argument("--source", default=None)
    r.add_argument("--cap", type=int, default=30)
    r.set_defaults(fn=cmd_reviews)
    sub.add_parser("analyse").set_defaults(fn=cmd_analyse)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
