"""Frozen-history graph features, supervised preference prediction and honest ranking evaluation."""

import hashlib
import json
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, ndcg_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.config import ROOT
from scripts.data import DATA, load_frames, write_json

FEATURES = [
    "user_count",
    "user_mean",
    "movie_count",
    "movie_mean",
    "genre_affinity",
    "graph_rating",
    "supporting_seeds",
    "cold_user",
    "cold_movie",
]


def chronological_split(ratings: pd.DataFrame) -> tuple[list[pd.DataFrame], list[int]]:
    """Keep identical timestamp groups together and separate feature edges from all target labels."""
    ordered = ratings.sort_values(["timestamp", "userId", "movieId"])
    bounds = [
        int(ordered.timestamp.iloc[max(0, min(len(ordered) - 1, int(len(ordered) * quantile) - 1))])
        for quantile in (0.6, 0.8, 0.9)
    ]
    times = ordered.timestamp
    masks = [
        times <= bounds[0],
        (times > bounds[0]) & (times <= bounds[1]),
        (times > bounds[1]) & (times <= bounds[2]),
        times > bounds[2],
    ]
    blocks = [ordered[mask].copy() for mask in masks]
    if any(frame.empty for frame in blocks) or not bounds[0] < bounds[1] < bounds[2]:
        raise ValueError("Timestamp groups do not permit four nonempty chronological blocks")
    return blocks, bounds


@dataclass
class FrozenGraph:
    """A mathematical view of only G0 rating edges; no production GDS output is read."""

    ratings: pd.DataFrame
    movies: pd.DataFrame

    def __post_init__(self):
        """Build frozen aggregate and sparse adjacency features once."""
        self.movie_ids = self.movies.movieId.astype(int).to_numpy()
        self.user_ids = np.sort(self.ratings.userId.unique())
        self.movie_index = {value: index for index, value in enumerate(self.movie_ids)}
        self.user_index = {value: index for index, value in enumerate(self.user_ids)}
        self.user_stats = self.ratings.groupby("userId").rating.agg(["count", "mean"])
        self.movie_stats = self.ratings.groupby("movieId").rating.agg(["count", "mean"])
        self.global_mean = float(self.ratings.rating.mean())
        self.genre_sets = {
            int(row.movieId): set(str(row.genres).split("|")) - {"(no genres listed)"}
            for row in self.movies.itertuples()
        }
        self._build_scores()

    def _build_scores(self):
        """Compute bounded neighbors from the G0 bipartite graph; keep no future edges."""
        shape = (len(self.user_ids), len(self.movie_ids))
        liked = self.ratings[self.ratings.rating >= 4]
        user_rows = liked.userId.map(self.user_index).to_numpy()
        movie_columns = liked.movieId.map(self.movie_index).to_numpy()
        adjacency = csr_matrix((np.ones(len(liked), dtype=np.float32), (user_rows, movie_columns)), shape=shape)
        common = (adjacency.T @ adjacency).tocoo()
        degree = np.asarray(adjacency.sum(axis=0)).ravel()
        valid = (common.data >= 3) & (common.row != common.col)
        left, right, support = common.row[valid], common.col[valid], common.data[valid]
        weight = support / (degree[left] + degree[right] - support) * support / (support + 5)
        candidates = pd.DataFrame({"left": left, "right": right, "weight": weight})
        candidates = candidates.sort_values(["left", "weight", "right"], ascending=[True, False, True])
        candidates = candidates.groupby("left", sort=False).head(20)
        similarity = csr_matrix(
            (candidates.weight, (candidates.left, candidates.right)), shape=(len(self.movie_ids), len(self.movie_ids))
        )
        positive_ratings = csr_matrix(
            (liked.rating.to_numpy(dtype=np.float32), (user_rows, movie_columns)), shape=shape
        )
        numerator = (positive_ratings @ similarity).toarray()
        denominator = (adjacency @ similarity).toarray()
        self.graph_scores = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 0)
        self.seed_counts = (adjacency @ (similarity > 0)).toarray()
        genre_vocab = sorted(set().union(*self.genre_sets.values()))
        genre_matrix = np.array(
            [[genre in self.genre_sets[movie] for genre in genre_vocab] for movie in self.movie_ids], dtype=np.float32
        )
        genre_counts = adjacency @ genre_matrix
        totals = np.maximum(np.asarray(adjacency.sum(axis=1)), 1)
        affinity = genre_counts / totals
        self.genre_affinity = affinity @ genre_matrix.T / np.maximum(genre_matrix.sum(axis=1), 1)

    def features(self, examples: pd.DataFrame) -> np.ndarray:
        """Extract only historical graph features for each future observed rating."""
        rows = []
        for row in examples.itertuples():
            user_pos = self.user_index.get(row.userId)
            movie_pos = self.movie_index.get(row.movieId)
            user_stats = self.user_stats.loc[row.userId] if row.userId in self.user_stats.index else None
            movie_stats = self.movie_stats.loc[row.movieId] if row.movieId in self.movie_stats.index else None
            connected = user_pos is not None and movie_pos is not None
            rows.append(
                [
                    float(user_stats["count"]) if user_stats is not None else 0,
                    float(user_stats["mean"]) if user_stats is not None else self.global_mean,
                    float(movie_stats["count"]) if movie_stats is not None else 0,
                    float(movie_stats["mean"]) if movie_stats is not None else self.global_mean,
                    float(self.genre_affinity[user_pos, movie_pos]) if connected else 0,
                    float(self.graph_scores[user_pos, movie_pos]) if connected else 0,
                    float(self.seed_counts[user_pos, movie_pos]) if connected else 0,
                    int(user_stats is None),
                    int(movie_stats is None),
                ]
            )
        return np.asarray(rows, dtype=np.float64)


def classification_metrics(labels, scores, threshold: float = 0.5) -> dict:
    """Report imbalance-aware metrics, not accuracy alone."""
    predictions = np.asarray(scores) >= threshold
    return {
        "n": len(labels),
        "positive_rate": float(np.mean(labels)),
        "average_precision": float(average_precision_score(labels, scores)),
        "roc_auc": float(roc_auc_score(labels, scores)) if len(np.unique(labels)) == 2 else None,
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
    }


def evaluate_ranking(graph: FrozenGraph, test: pd.DataFrame) -> dict:
    """Full-catalog ranking for all eligible test users with explicitly observed relevance."""
    seen = graph.ratings.groupby("userId").movieId.apply(set).to_dict()
    positives = test[test.rating >= 4].groupby("userId").movieId.apply(set).to_dict()
    popular = np.array(
        [
            graph.movie_stats.loc[mid, "mean"] if mid in graph.movie_stats.index else graph.global_mean
            for mid in graph.movie_ids
        ]
    )
    counts = np.array(
        [graph.movie_stats.loc[mid, "count"] if mid in graph.movie_stats.index else 0 for mid in graph.movie_ids]
    )
    baseline = (counts * popular + 20 * graph.global_mean) / (counts + 20)
    reports = {}
    for method in ("bayesian_popularity", "item_cf"):
        recalls, ndcgs, candidate_recalls = [], [], []
        recommended = set()
        warm_users = 0
        for user, relevant in positives.items():
            candidates = np.array([mid not in seen.get(user, set()) for mid in graph.movie_ids])
            relevant = relevant - seen.get(user, set())
            if not relevant:
                continue
            user_pos = graph.user_index.get(user)
            scores = baseline.copy()
            if method == "item_cf" and user_pos is not None:
                graph_values = graph.graph_scores[user_pos]
                scores = np.where(graph_values > 0, graph_values, baseline - 5)
                candidate_recalls.append(
                    len({int(graph.movie_ids[index]) for index in np.flatnonzero(graph_values > 0)} & relevant)
                    / len(relevant)
                )
                warm_users += 1
            scores[~candidates] = -np.inf
            order = np.lexsort((graph.movie_ids, -scores))[:10]
            chosen = set(graph.movie_ids[order])
            recommended |= chosen
            recalls.append(len(chosen & relevant) / len(relevant))
            gains = np.array([float(mid in relevant) for mid in graph.movie_ids[candidates]])
            candidate_scores = scores[candidates]
            ndcgs.append(float(ndcg_score(gains[None, :], candidate_scores[None, :], k=10)))
        reports[method] = {
            "users_evaluated": len(recalls),
            "warm_users": warm_users,
            "recall_at_10": float(np.mean(recalls)),
            "ndcg_at_10": float(np.mean(ndcgs)),
            "catalog_coverage": len(recommended) / len(graph.movie_ids),
            "candidate_recall": float(np.mean(candidate_recalls)) if candidate_recalls else None,
        }
    return reports


def run():
    """Train on future observed interactions using a completely frozen feature graph."""
    frames = load_frames()
    blocks, bounds = chronological_split(frames["ratings"])
    history, training, validation, test = blocks
    if history.timestamp.max() > bounds[0] or min(training.timestamp) <= bounds[0]:
        raise ValueError("Temporal leakage invariant failed")
    target_pairs = set(zip(pd.concat(blocks[1:]).userId, pd.concat(blocks[1:]).movieId))
    if target_pairs & set(zip(history.userId, history.movieId)):
        raise ValueError("A target pair already exists in the frozen graph")
    graph = FrozenGraph(history, frames["movies"])
    examples = [frame[frame.rating != 3.5] for frame in (training, validation, test)]
    features = [graph.features(frame) for frame in examples]
    labels = [(frame.rating >= 4).astype(int).to_numpy() for frame in examples]
    trials = []
    best = (-np.inf, None, 0.0)
    for strength in (0.1, 1.0, 10.0):
        model = make_pipeline(
            SimpleImputer(), StandardScaler(), LogisticRegression(C=strength, max_iter=1000, random_state=42)
        )
        model.fit(features[0], labels[0])
        metric = average_precision_score(labels[1], model.predict_proba(features[1])[:, 1])
        trials.append({"C": strength, "validation_average_precision": float(metric)})
        if metric > best[0]:
            best = (metric, model, strength)
    model = best[1]
    dummy = DummyClassifier(strategy="prior").fit(features[0], labels[0])
    scores = model.predict_proba(features[2])[:, 1]
    manifest = json.loads((DATA / "manifest.json").read_text())
    split_hash = hashlib.sha256(history[["userId", "movieId", "timestamp"]].to_csv(index=False).encode()).hexdigest()
    report = {
        "experiment_code_sha256": hashlib.sha256((ROOT / "app/ml/experiment.py").read_bytes()).hexdigest(),
        "task": "Predict high future observed ratings; unrated pairs are not negative training labels",
        "dataset_hash": manifest["data_version"],
        "feature_graph_hash": split_hash,
        "cutoffs": bounds,
        "block_sizes": [len(frame) for frame in blocks],
        "supervised_sizes": [len(frame) for frame in examples],
        "features": FEATURES,
        "seed": 42,
        "trials": trials,
        "selected_C": best[2],
        "test": classification_metrics(labels[2], scores),
        "dummy_test": classification_metrics(labels[2], dummy.predict_proba(features[2])[:, 1]),
        "movie_mean_test": classification_metrics(labels[2], features[2][:, 3] / 5),
        "ranking": evaluate_ranking(graph, test),
        "cold_user_test_count": int(np.sum(features[2][:, -2])),
        "cold_movie_test_count": int(np.sum(features[2][:, -1])),
        "limitations": [
            "All feature aggregates are frozen at T0; no rolling update",
            "Observed future ratings are selection-biased, not exposure-controlled labels",
            "The classifier is an offline experiment, not a calibrated serving probability",
            "Ranking treats unknown relevance as unobserved, not verified dislike",
        ],
    }
    for label, mask in (("warm", features[2][:, -2] == 0), ("cold", features[2][:, -2] == 1)):
        if mask.any():
            report[label + "_test"] = classification_metrics(labels[2][mask], scores[mask])
    write_json(ROOT / "artifacts/reports/ml_metrics.json", report)
    write_json(
        ROOT / "artifacts/reports/split_manifest.json",
        {key: report[key] for key in ("dataset_hash", "feature_graph_hash", "cutoffs", "block_sizes", "seed")},
    )
    model_dir = ROOT / "artifacts/models"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_dir / "preference_pipeline.joblib")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
