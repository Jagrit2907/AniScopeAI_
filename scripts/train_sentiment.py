"""Train and evaluate AniScope's review-sentiment model (TF-IDF + logistic regression).

    python scripts/train_sentiment.py                  # train on data/raw/reviews.csv
    python scripts/train_sentiment.py --reviews PATH   # another file with the same columns
    python scripts/train_sentiment.py evaluate         # print the saved evaluation report

The CSV is streamed in chunks and never modified. Output: models/sentiment/
(model.joblib, metadata.json, evaluation.md). The app only loads the saved model.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from src import ml_sentiment as ml  # noqa: E402


def train(a) -> int:
    path = Path(a.reviews)
    if not path.exists():
        print(f"Review file not found: {path}\nExpected the Kaggle reviews.csv (uid, profile, anime_uid, text, score, scores, link). "
              "No model was trained and no metrics were produced.")
        return 2
    t0 = time.time()
    print(f"Reading {path} in chunks of {a.chunksize:,} rows …")
    frame, stats = ml.load_training_data(path, a.chunksize, progress=lambda n: print(f"  {n:,} rows read", end="\r"))
    print(f"\nUsable reviews: {stats['usable']:,} from {stats['titles']:,} titles · labels {stats['label_distribution']}")
    if not stats["usable"]:
        print("Nothing usable to train on. No model was saved.")
        return 2
    try:
        model, meta = ml.train_and_evaluate(frame, a.seed, a.test_share, a.min_df)
    except ValueError as e:
        print(f"Training failed: {e}\nNo model was saved.")
        return 2
    meta["data"] = {"file": path.name, **stats}
    out = ml.save(model, meta, Path(a.out) if a.out else None)
    print("\n" + ml.report_markdown(meta))
    print(f"Saved model and report to {out} ({time.time() - t0:,.0f}s).")
    return 0


def evaluate(a) -> int:
    f = (Path(a.out) if a.out else settings.ML_MODEL_DIR) / ml.REPORT_FILE
    if not f.exists():
        print(f"No evaluation report at {f}. Train first: python scripts/train_sentiment.py")
        return 2
    print(f.read_text(encoding="utf-8"))
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):        # Windows consoles: never crash on non-ASCII characters
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", default="train", choices=["train", "evaluate"])
    p.add_argument("--reviews", default=str(settings.RAW_DATA_DIR / "reviews.csv"))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--test-share", type=float, default=0.2, help="share of TITLES held out for testing")
    p.add_argument("--min-df", type=int, default=3)
    p.add_argument("--chunksize", type=int, default=5000)
    p.add_argument("--out", default=None, help="model directory (default models/sentiment)")
    a = p.parse_args(argv)
    return train(a) if a.command == "train" else evaluate(a)


if __name__ == "__main__":
    raise SystemExit(main())
