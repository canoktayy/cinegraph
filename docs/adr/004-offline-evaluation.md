# ADR 004: Freeze feature history before every target label

Status: accepted.

Chronological blocks are approximately 60% G0 history, 20% model-training labels, 10% validation labels and 10% test labels. Identical timestamps never cross boundaries. Every feature is computed from G0 only; no serving GDS artifact or future tag is read. Offline graph features are calculated from a separate in-memory sparse representation of the same historical user/movie edges. They are not mislabeled as production Neo4j GDS results.

Labels are high observed ratings ≥4 versus low observed ratings ≤3; 3.5 is excluded. Unrated pairs are not supervised negatives. The scaler/imputer fit training examples only. C is selected by validation average precision; test is reserved for final reporting. LogisticRegression is intentionally small and inspectable. The classifier remains an experiment, not an unverified calibrated serving probability.

Global time splitting yields substantial cold-start users in this dataset. Warm/cold counts and separate metrics must accompany the aggregate. Full-catalog ranking compares a Bayesian baseline with frozen-history item CF, reports candidate recall and includes cold users via fallback. Unknown relevance is not verified dislike. Low Recall@10 is a meaningful result, not grounds to leak future data or cherry-pick users.

Movie/genre metadata is treated as a static catalog. The experiment does not simulate historical release-time availability; future rating edges and tag events are excluded. This transductive catalog assumption is separate from the strict rating-label cutoff.
