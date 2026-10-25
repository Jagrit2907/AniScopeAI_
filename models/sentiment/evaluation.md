# Sentiment model evaluation — tfidf-logreg-20261024-2324

TF-IDF (word 1-2 grams) + logistic regression (class_weight=balanced). Trained 2026-10-24T23:24:18+00:00.

> Labels come from reviewers' own 1-10 scores (negative 1-4, mixed 5-6, positive 7-10). The model predicts that rating-derived category from text; it is not a verified human sentiment label.

**Data:** reviews.csv — 192,112 rows read, 130,347 usable from 8,110 titles. Dropped: invalid/missing score 2, missing/short text 1, duplicate id 61,593, duplicate text 169.

**Split:** by title (anime_uid), seeded hash (seed 42, 20% of titles held out) — train 101,328 reviews / 6,517 titles, test 29,019 reviews / 1,593 titles.
Train classes {'negative': 13563, 'mixed': 16224, 'positive': 71541} · test classes {'negative': 4097, 'mixed': 4759, 'positive': 20163}.

## Held-out test results

| | Accuracy | Macro F1 |
|---|---|---|
| Trained model | 0.784 | 0.683 |
| Majority baseline (always 'positive') | 0.695 | 0.273 |

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| negative | 0.634 | 0.708 | 0.669 | 4,097 |
| mixed | 0.439 | 0.553 | 0.490 | 4,759 |
| positive | 0.933 | 0.854 | 0.892 | 20,163 |

Confusion matrix (rows = true, columns = predicted):

| | negative | mixed | positive |
|---|---|---|---|
| negative | 2,899 | 988 | 210 |
| mixed | 1,108 | 2,632 | 1,019 |
| positive | 566 | 2,373 | 17,224 |

## Limitations
- Rating-derived labels, not human sentiment annotations.
- Title-level split; near-duplicate texts across titles are not detected.
- International MyAnimeList reviews with unknown reviewer location: not Indian audience sentiment.
- Bag-of-words: no sarcasm, cross-sentence negation or aspect awareness.
