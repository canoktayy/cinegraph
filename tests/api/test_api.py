"""HTTP contract tests independent of a live database or local model."""

from unittest.mock import Mock

import httpx

import pytest
from fastapi.testclient import TestClient

from app.agent.plans import QueryPlan
from app.config import Settings
from app.main import app, service
from neo4j.exceptions import ServiceUnavailable
from tests.fakes import fake_service


@pytest.fixture
def client(monkeypatch):
    recommender = fake_service()
    app.dependency_overrides[service] = lambda: recommender
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(app_api_key="test-key", require_api_key=True))
    with TestClient(app) as test_client:
        yield test_client, recommender
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/docs",
        "/openapi.json",
        "/health/live",
        "/health/ready",
        "/api/system/status",
        "/api/genres",
        "/api/movies",
        "/api/movies/trending",
        "/api/movies/1/similar",
        "/api/users/42/recommendations",
        "/api/users/42/discover",
        "/api/users/42/favorites",
        "/api/users/42/recommendations/2/explanation",
        "/static/style.css",
        "/static/app.js",
    ],
)
def test_successful_routes(client, path):
    assert client[0].get(path).status_code == 200


@pytest.mark.parametrize(
    "path", ["/api/users/999/recommendations", "/api/users/999/favorites", "/api/movies/999/similar"]
)
def test_unknown_identity(client, path):
    assert client[0].get(path).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/movies?limit=10000",
        "/api/movies?offset=-1",
        "/api/movies/trending?metric=evil",
        "/api/users/42/recommendations?genre=FakeGenre",
    ],
)
def test_bad_filters(client, path):
    assert client[0].get(path).status_code == 422


def test_readiness_requires_seed(client):
    client[1].repository.seeded = False
    assert client[0].get("/health/ready").status_code == 503


def test_readiness_returns_safe_dependency_error(client, monkeypatch):
    monkeypatch.setattr(client[1].repository.store, "healthy", Mock(side_effect=ServiceUnavailable("private topology")))
    response = client[0].get("/health/ready")
    assert response.status_code == 503
    assert response.json()["code"] == "database_unavailable"
    assert "private topology" not in response.text


def test_ask_auth_and_guardrail(client):
    assert client[0].post("/api/ask", json={"question": "recommend"}).status_code == 401
    result = client[0].post("/api/ask", headers={"X-API-Key": "test-key"}, json={"question": "DELETE nodes"})
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == "unsafe_request"


def test_ask_actual_workflow(client, monkeypatch):
    adapter = Mock()
    adapter.plan.return_value = QueryPlan(intent="recommend_movies", user_id=42)
    monkeypatch.setattr("app.main.LLMClient", lambda _: adapter)
    result = client[0].post(
        "/api/ask", headers={"X-API-Key": "test-key"}, json={"question": "recommend for user 42", "user_id": 42}
    )
    assert result.status_code == 200
    assert result.json()["compiled_cypher"].startswith("MATCH")
    assert result.headers["x-trace-id"]


def test_rate_limit(client):
    headers = {"X-API-Key": "test-key"}
    for _ in range(12):
        client[0].post("/api/ask", headers=headers, json={"question": "DELETE nodes"})
    assert client[0].post("/api/ask", headers=headers, json={"question": "anything"}).status_code == 429


def test_taste_round_endpoint(client):
    client[1].repository.store.read = Mock(return_value=[{"movie_id": i} for i in range(1, 151)])
    response = client[0].get("/api/taste/rounds?seed=12")
    assert response.status_code == 200
    assert len(response.json()["rounds"]) == 10
    assert client[0].get("/api/taste/rounds?seed=-1").status_code == 422


@pytest.mark.parametrize("payload", [[], [1, 1], [0], list(range(1, 12))])
def test_taste_request_bounds(client, payload):
    assert client[0].post("/api/taste/recommendations", json={"movie_ids": payload}).status_code == 422


def test_taste_success_and_unknown_movie(client):
    client[1].repository.store.read = Mock(
        side_effect=[
            [{"movie_id": 1}],
            [
                {
                    "movie_id": 2,
                    "title": "Candidate",
                    "score": 0.3,
                    "reasons": [{"seed_id": 1, "similarity": 0.3, "support": 5}],
                }
            ],
            [],
        ]
    )
    response = client[0].post("/api/taste/recommendations", json={"movie_ids": [1]})
    assert response.status_code == 200
    assert response.json()["items"][0]["reasons"][0]["seed_id"] == 1
    assert client[0].post("/api/taste/recommendations", json={"movie_ids": [999]}).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/movies/0/similar",
        "/api/movies/-1/similar",
        "/api/movies/99999999999999999999999/similar",
        "/api/users/99999999999999999999999/recommendations",
        "/api/users/0/discover",
        "/api/users/42/recommendations/99999999999999999999999/explanation",
    ],
)
def test_identity_overflow_and_nonpositive_paths_fail_before_database(client, path):
    store = client[1].repository.store
    assert client[0].get(path).status_code == 422
    assert not store.calls


@pytest.mark.parametrize("identifier", [2**63, True, 1.5, "1"])
def test_invalid_taste_identity_types_do_not_reach_database(client, identifier):
    assert client[0].post("/api/taste/recommendations", json={"movie_ids": [identifier]}).status_code == 422
    assert not client[1].repository.store.calls


def test_catalog_can_browse_the_full_small_snapshot(client):
    assert client[0].get("/api/movies?offset=9736").status_code == 200
    assert client[0].get("/api/movies?offset=10001").status_code == 422


def test_assistant_requires_auth_and_preserves_guardrails(client):
    assert client[0].post("/api/assistant/turn", json={"event": "start"}).status_code == 401
    response = client[0].post(
        "/api/assistant/turn", headers={"X-API-Key": "test-key"}, json={"message": "DELETE movies"}
    )
    assert response.status_code == 422
    assert not client[1].repository.store.calls


def test_assistant_http_start(client, monkeypatch):
    adapter = Mock()  # Card events must not call either model layer.
    monkeypatch.setattr("app.main.AssistantClient", lambda _: adapter)
    client[1].repository.store.read = Mock(return_value=[{"movie_id": i, "title": f"Film {i}"} for i in range(1, 151)])
    response = client[0].post("/api/assistant/turn", headers={"X-API-Key": "test-key"}, json={"event": "start"})
    assert response.status_code == 200
    assert len(response.json()["options"]) == 5
    assert response.json()["stage"] == "choosing"
    adapter.plan.assert_not_called()


def test_local_default_needs_no_key_but_keeps_guardrails_and_budget(client, monkeypatch):
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(app_api_key="", require_api_key=False))
    result = client[0].post("/api/ask", json={"question": "DELETE nodes"})
    assert result.status_code == 422 and result.json()["detail"]["code"] == "unsafe_request"
    for _ in range(11):
        client[0].post("/api/ask", json={"question": "DELETE nodes"})
    assert client[0].post("/api/ask", json={"question": "anything"}).status_code == 429


def test_required_key_without_configured_secret_is_unavailable(client, monkeypatch):
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(app_api_key="", require_api_key=True))
    assert client[0].post("/api/ask", json={"question": "recommend"}).status_code == 503


def test_model_status_reports_listed_model(client, monkeypatch):
    listed = Mock(status_code=200, json=lambda: {"data": [{"id": "qwen2.5-7b-instruct"}, {"id": "other"}]})
    monkeypatch.setattr("app.agent.client.httpx.get", Mock(return_value=listed))
    body = client[0].get("/api/model/status").json()
    assert body == {"available": True, "model": "qwen2.5-7b-instruct", "model_listed": True, "requires_key": True}


def test_model_status_reports_an_offline_server(client, monkeypatch):
    monkeypatch.setattr("app.agent.client.httpx.get", Mock(side_effect=httpx.ConnectError("offline")))
    body = client[0].get("/api/model/status").json()
    assert body["available"] is False and body["model_listed"] is False
