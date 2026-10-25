"""Rebuild the AniScope catalog files from an Anime Offline Database release.

Only needed if your existing export is missing or unreadable. Usage:

    python scripts/build_catalog_from_aod.py path/to/anime-offline-database.json data/raw

Accepts the .json release file (decompress .zst first, e.g. with 7-Zip).
Writes anime_catalog_all_titles.csv/.jsonl, empty evidence templates and a
dataset_manifest.json that records the upstream licence (ODbL v1.0 + DbCL v1.0).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def main(src: Path, out_dir: Path) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    records = payload["data"]
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "anime_catalog_all_titles.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    fields = ["title", "type", "episodes", "status", "season", "year", "score",
              "synonyms", "tags", "studios", "sources", "picture"]
    with (out_dir / "anime_catalog_all_titles.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in records:
            season = r.get("animeSeason") or {}
            score = r.get("score") or {}
            w.writerow({
                "title": r.get("title"), "type": r.get("type"), "episodes": r.get("episodes"),
                "status": r.get("status"), "season": season.get("season"), "year": season.get("year"),
                "score": score.get("arithmeticMean") if isinstance(score, dict) else score,
                "synonyms": " | ".join(r.get("synonyms", [])), "tags": " | ".join(r.get("tags", [])),
                "studios": " | ".join(r.get("studios", [])), "sources": " | ".join(r.get("sources", [])),
                "picture": r.get("picture"),
            })

    (out_dir / "trend_observations_template.csv").write_text(
        "anime_id,query,geo,date,value,source\n", encoding="utf-8")
    (out_dir / "review_evidence_template.csv").write_text(
        "anime_id,title,source,source_url,date,text,score,language,geography\n", encoding="utf-8")
    manifest = {
        "source": "Anime Offline Database (manami-project)",
        "repository": payload.get("repository"),
        "snapshot_date": payload.get("lastUpdate"),
        "license": payload.get("license"),
        "total_records": len(records),
        "unique_titles": len({r.get("title") for r in records}),
    }
    (out_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} records to {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
