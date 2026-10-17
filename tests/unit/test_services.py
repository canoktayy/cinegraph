"""Ranking policy, cold-start paths and honest explanation rendering."""

import pytest
from fastapi import HTTPException

from tests.fakes import fake_service


def test_personalized_and_fallback():
    service = fake_service()
    assert service.recommendations(42).method == "item_cf"
    service.repository.empty.add("recommend_movies")
    result = service.recommendations(42)
    assert result.method == "bayesian_popularity"
    assert result.fallback_reason


def test_discovery_and_similarity_fallback():
    service = fake_service()
    assert service.discover(42).method == "louvain_discovery"
    assert service.similar(1).method == "gds_item_similarity"
    service.repository.empty.update({"discover_movies", "similar_movies"})
    assert service.discover(42).fallback_reason
    assert service.similar(1).method == "direct_graph_similarity"


def test_unknown_user_is_not_cold_start():
    with pytest.raises(HTTPException) as caught:
        fake_service().recommendations(999)
    assert caught.value.status_code == 404


def test_historical_trending_and_pagerank():
    service = fake_service()
    assert service.trending({"metric": "rating"}).method == "historical_activity"
    assert service.trending({"metric": "pagerank"}).score_type == "centrality"


def test_evidence_contribution_matches_source_score():
    service = fake_service()
    result = service.explanation(42, 2)
    assert result.recommended
    assert result.evidence[0].contribution == pytest.approx(4.5)
    assert result.evidence[0].path[0]["user_id"] == 42
    service.repository.store.rated = True
    assert not service.explanation(42, 2).recommended
    service.repository.store.rated = False
    service.repository.empty.add("explain_recommendation")
    assert not service.explanation(42, 2).evidence
