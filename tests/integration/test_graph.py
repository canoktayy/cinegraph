"""These tests connect to the real seeded Neo4j/GDS instance; no mocks or skips."""

import json
from uuid import uuid4

import pytest
from neo4j.exceptions import ConstraintError

from app import queries
from app.analytics.build import drop_projection, graph_algorithms, project_likes, project_movies, similarity_rows
from app.config import ROOT, get_settings
from app.database import GraphStore
from app.repository import CatalogRepository
from app.services import RecommendationService

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def store():
    # GDS projection jobs run here; like `make analytics`, they need more than the API's 5 s budget on slow CI runners.
    database = GraphStore(get_settings().model_copy(update={"query_timeout_seconds": 120}))
    database.healthy()
    yield database
    database.close()


def test_real_source_counts(store):
    expected = json.loads((ROOT / "artifacts/reports/data_quality.json").read_text())
    actual = CatalogRepository(store).statistics()
    for key in ["movies", "users", "ratings", "tag_applications"]:
        assert actual[key] == expected[key]


def test_constraints_and_index_lookup(store):
    assert len(store.read("SHOW CONSTRAINTS")) >= 5
    with pytest.raises(ConstraintError):
        store.write("CREATE (:Movie {movie_id:1})")
    assert store.read("MATCH (m:Movie {movie_id:1}) RETURN count(m) AS n")[0]["n"] == 1


def test_recommendations_exclude_rated_and_are_stable(store):
    service = RecommendationService(CatalogRepository(store))
    first = service.recommendations(42)
    assert first.items and first.method == "item_cf"
    seen = {
        row["movie_id"] for row in store.read("MATCH (:User {user_id:42})-[:RATED]->(m) RETURN m.movie_id AS movie_id")
    }
    assert not seen & {movie.movie_id for movie in first.items}
    assert first == service.recommendations(42)
    explanation = service.explanation(42, first.items[0].movie_id)
    assert explanation.evidence and explanation.recommended
    assert all(row.support >= 3 for row in explanation.evidence)


def test_gds_outputs_and_community(store):
    service = RecommendationService(CatalogRepository(store))
    assert store.read("RETURN gds.version() AS version")[0]["version"].startswith("2.13")
    assert service.similar(1).method == "gds_item_similarity"
    assert service.discover(42).method == "louvain_discovery"
    assert service.trending({"metric": "pagerank"}).items
    assert not store.read("MATCH (m)-[s:SIMILAR_TO]->(m) RETURN s LIMIT 1")


def test_cypher_common_support_matches_source(store):
    service = RecommendationService(CatalogRepository(store))
    candidate = service.similar(1).items[0]
    common = store.read(
        """MATCH (:Movie {movie_id:1})<-[a:RATED]-(u:User)-[b:RATED]->(:Movie {movie_id:$candidate})
    WHERE a.score>=4 AND b.score>=4 RETURN count(DISTINCT u) AS n""",
        {"candidate": candidate.movie_id},
    )[0]["n"]
    assert common == candidate.support
    rows = store.read(queries.DIRECT_SIMILAR, {"movie_id": 1, "min_common": 3, "limit": 5})
    assert len(rows) == 5


def test_natural_language_explanation_excludes_already_rated_target(store):
    row = store.read("MATCH (:User {user_id:42})-[:RATED]->(m:Movie) RETURN m.movie_id AS movie_id LIMIT 1")[0]
    params = RecommendationService(CatalogRepository(store)).parameters({"user_id": 42, "movie_id": row["movie_id"]})
    assert store.read(queries.EVIDENCE, params) == []


def test_fulltext_and_tag_provenance(store):
    repo = CatalogRepository(store)
    assert any(row["movie_id"] == 1 for row in repo.search({"q": "Toy Story"}))
    invalid = store.read(
        """MATCH (a:TagApplication) WHERE
    size([(u:User)-[:APPLIED]->(a)|u])<>1 OR size([(a)-[:ON_MOVIE]->(m)|m])<>1
    OR size([(a)-[:WITH_TAG]->(t)|t])<>1 RETURN count(a) AS n"""
    )[0]["n"]
    assert invalid == 0


def test_real_projection_direction_and_algorithm_jobs(store):
    """Exercise real projection/job code without mutating the serving source graph."""
    state = CatalogRepository(store).state()
    name = "moviegraph-test-" + uuid4().hex
    try:
        info = project_likes(store, name, state["as_of"])
        assert info["relationshipCount"] > 0
        rows = similarity_rows(store, name, state["as_of"])
        assert rows and all(row["source"] != row["target"] and row["support"] >= 3 for row in rows)
    finally:
        drop_projection(store, name)
    name = "moviegraph-test-" + uuid4().hex
    try:
        info = project_movies(store, name, state["active_run_id"])
        communities, ranks = graph_algorithms(store, name)
        assert len(communities) == info["nodeCount"]
        assert len(ranks) == info["nodeCount"]
        assert all(row["pagerank"] >= 0 for row in ranks)
    finally:
        drop_projection(store, name)


def test_visitor_taste_rounds_and_actual_graph_evidence(store):
    """Visitor ranking excludes picks and conserves actual similarity contributions."""
    from app.taste import TasteRequest, recommend, rounds

    service = RecommendationService(CatalogRepository(store))
    before = service.repository.statistics()
    options = rounds(service, 123)
    picks = [group[0]["movie_id"] for group in options["rounds"]]
    result = recommend(service, TasteRequest(movie_ids=picks))
    assert result["items"]
    assert not set(picks) & {row["movie_id"] for row in result["items"]}
    for movie in result["items"]:
        assert movie["score"] == pytest.approx(sum(reason["similarity"] for reason in movie["reasons"]) / len(picks))
        assert all(reason["seed_id"] in picks and reason["support"] >= 3 for reason in movie["reasons"])
    filtered = recommend(service, TasteRequest(movie_ids=picks, genre="Sci-Fi"))
    assert all("Sci-Fi" in movie["genres"] for movie in filtered["items"])
    assert before == service.repository.statistics()


def test_assistant_filters_and_named_film_use_real_graph(store):
    """Only the two model layers are controlled; title lookup, filters and reasons execute in Neo4j."""
    from unittest.mock import Mock
    from fastapi import HTTPException
    from app.agent.assistant import AssistantIntent, AssistantTurn, answer_turn
    from app.taste import rounds

    service = RecommendationService(CatalogRepository(store))
    choices = [group[0]["movie_id"] for group in rounds(service, 42)["rounds"]]
    neutral = {"film_title": None, "exclude_genre": None, "year_from": None, "year_to": None, "clarify_reason": None}
    adapter = Mock()
    adapter.verbalise.side_effect = HTTPException(503, "offline")  # The factual template speaks instead.
    adapter.plan.return_value = AssistantIntent(
        **neutral | {"action": "recommend", "source": "favourites", "genre": None}
    )
    result = answer_turn(AssistantTurn(choices=choices, message="Only comedies from the 90s"), service, adapter, "it")
    assert result["items"] and result["plan"]["genre"] == "Comedy"
    assert all("Comedy" in row["genres"] and 1990 <= row["year"] <= 1999 for row in result["items"])
    assert all(row["movie_id"] not in choices for row in result["items"])
    assert all(reason["seed_id"] in choices for row in result["items"] for reason in row["reasons"])
    adapter.plan.return_value = AssistantIntent(
        **neutral | {"action": "recommend", "source": "film", "film_title": "Scarface", "genre": None}
    )
    result = answer_turn(
        AssistantTurn(choices=choices, message="Scarface is my favourite film"), service, adapter, "it"
    )
    scarface = store.read("MATCH (m:Movie {title:'Scarface (1983)'}) RETURN m.movie_id AS id")[0]["id"]
    assert result["plan"]["anchor_movie_id"] == scarface and result["items"]
    assert all(reason["seed_id"] == scarface for row in result["items"] for reason in row["reasons"])


def test_rater_favourites_are_their_own_high_ratings_in_order(store):
    service = RecommendationService(CatalogRepository(store))
    items = service.favourites(42, 8).items
    rated = {
        row["movie_id"]: row["score"]
        for row in store.read(
            "MATCH (:User {user_id:42})-[r:RATED]->(m) RETURN m.movie_id AS movie_id, r.score AS score"
        )
    }
    assert items and all(rated[movie.movie_id] == movie.score >= 4 for movie in items)
    assert [movie.score for movie in items] == sorted((movie.score for movie in items), reverse=True)


def test_shortest_path_between_two_films_uses_real_similarity_links(store):
    service = RecommendationService(CatalogRepository(store))
    path = service.path(4262, 1, max_hops=6)  # Scarface (1983) to Toy Story
    assert path.found and 1 <= path.hops <= 6
    assert [path.films[0].movie_id, path.films[-1].movie_id] == [4262, 1]
    assert len(path.links) == path.hops and all(link.support >= 3 for link in path.links)
    for left, right in zip(path.films, path.films[1:]):
        linked = store.read(
            "MATCH (:Movie {movie_id:$a})-[s:SIMILAR_TO]-(:Movie {movie_id:$b}) RETURN count(s) AS n",
            {"a": left.movie_id, "b": right.movie_id},
        )[0]["n"]
        assert linked >= 1
    assert not service.path(4262, 1, max_hops=1).found
