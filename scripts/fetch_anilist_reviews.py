"""Fetch public reviews from the AniList GraphQL API into AniScope's review CSV format.

AniList API terms (https://docs.anilist.co/guide/terms-of-use): free for
non-commercial use; mass collection / hoarding is prohibited; commercial use
above US$150/month needs a licence. Keep pulls small (a few dozen titles) and
do not redistribute the review text.

Usage (Windows PowerShell):
    python scripts/fetch_anilist_reviews.py --ids 154587 21 --per-title 25 --out data/raw/anilist_reviews.csv
Then import the CSV in Audience Intelligence → "Import review evidence".

AniList ids are the numbers in https://anilist.co/anime/<id>; the catalog's
sources column contains them. Rate limit: the script waits ~2.2 s between calls
(AniList currently allows ~30 requests/minute).

NOTE: written against AniList's documented schema (Review: id, body, summary,
score, rating, ratingAmount, createdAt, siteUrl). It could not be run in the
build environment (network blocked), so run it once on a single id first.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request

API = "https://graphql.anilist.co"
QUERY = """
query ($id: Int, $page: Int, $perPage: Int) {
  Media(id: $id, type: ANIME) {
    id idMal title { romaji english }
    reviews(page: $page, perPage: $perPage, sort: RATING_DESC) {
      pageInfo { hasNextPage }
      nodes { id summary body(asHtml: false) score rating ratingAmount createdAt siteUrl }
    }
  }
}"""


def fetch(media_id: int, per_title: int) -> list[dict]:
    rows, page = [], 1
    while len(rows) < per_title:
        payload = json.dumps({"query": QUERY, "variables": {"id": media_id, "page": page,
                                                          "perPage": min(25, per_title)}}).encode()
        req = urllib.request.Request(API, data=payload, headers={"Content-Type": "application/json",
                                                                  "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        media = (data.get("data") or {}).get("Media")
        if not media:
            print(f"  id {media_id}: not found or API error: {data.get('errors')}")
            break
        for n in media["reviews"]["nodes"]:
            rows.append({"review_id": n["id"], "anilist_id": media["id"], "mal_id": media.get("idMal"),
                         "title": media["title"]["romaji"], "source": "AniList", "source_url": n.get("siteUrl"),
                         "date": n.get("createdAt"), "text": n.get("body") or "", "score": n.get("score"),
                         "language": "", "geography": "", "helpful_count": n.get("rating")})
        if not media["reviews"]["pageInfo"]["hasNextPage"]:
            break
        page += 1
        time.sleep(2.2)
    return rows[:per_title]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", type=int, nargs="+", required=True, help="AniList anime ids")
    ap.add_argument("--per-title", type=int, default=25)
    ap.add_argument("--out", default="data/raw/anilist_reviews.csv")
    args = ap.parse_args()
    all_rows = []
    for mid in args.ids:
        rows = fetch(mid, args.per_title)
        print(f"  id {mid}: {len(rows)} reviews")
        all_rows += rows
        time.sleep(2.2)
    if not all_rows:
        print("No reviews fetched.")
        return
    with open(args.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    print(f"Wrote {len(all_rows)} reviews to {args.out}")


if __name__ == "__main__":
    main()
