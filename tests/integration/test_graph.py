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
    database = GraphStore(get_settings())
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
