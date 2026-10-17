"""Temporal grouping and invariants of frozen-history graph features."""

import numpy as np
import pandas as pd
import pytest

from app.ml.experiment import FrozenGraph, chronological_split, classification_metrics


def fixture_ratings():
    return pd.DataFrame(
        {
            "userId": [1, 1, 2, 2, 3, 3, 4, 4, 5, 5],
            "movieId": [1, 2, 1, 3, 2, 3, 1, 4, 3, 4],
            "rating": [4, 5, 4, 2, 5, 4, 2, 4, 3, 5],
            "timestamp": list(range(10)),
        }
    )


def test_chronological_targets_are_disjoint():
    blocks, bounds = chronological_split(fixture_ratings())
    assert max(blocks[0].timestamp) <= bounds[0] < min(blocks[1].timestamp)
    assert sum(map(len, blocks)) == 10
    for left, right in zip(blocks, blocks[1:]):
        assert set(left.timestamp).isdisjoint(set(right.timestamp))


def test_split_rejects_indivisible_times():
    frame = fixture_ratings()
    frame.timestamp = 1
    with pytest.raises(ValueError):
        chronological_split(frame)


def test_frozen_features_do_not_read_future_labels():
    movies = pd.DataFrame({"movieId": [1, 2, 3, 4], "genres": ["Drama", "Drama", "Action", "Action"]})
    history = fixture_ratings().iloc[:6]
    graph = FrozenGraph(history, movies)
    target = fixture_ratings().iloc[6:].copy()
    before = graph.features(target)
    target.rating = 0.5
    target.timestamp = 9999999
    np.testing.assert_array_equal(before, graph.features(target))
    assert (before[:, -2] == 1).all()


def test_metrics_report_imbalance_and_counts():
    metrics = classification_metrics(np.array([0, 1, 1]), np.array([0.1, 0.9, 0.8]))
    assert metrics["n"] == 3
    assert metrics["f1"] == 1
    assert metrics["confusion_matrix"] == [[1, 0], [0, 2]]
