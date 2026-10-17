"""Malicious model output must never reach an unrestricted database call."""

import json
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import queries
from app.agent.client import LLMClient
from app.agent.compiler import compile_plan, guard_question, validate_template
from app.agent.plans import QueryPlan
from app.agent.workflow import answer
from app.config import Settings
from app.models import AskRequest
from tests.fakes import fake_service


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "recommend_movies"},
        {"intent": "similar_movies"},
        {"intent": "recommend_movies", "user_id": -1},
        {"intent": "similar_movies", "movie_id": 1, "limit": 1000000},
        {"intent": "similar_movies", "movie_id": 1, "raw_cypher": "MATCH (n) DELETE n"},
        {"intent": "execute_admin"},
        {"intent": "historical_trending", "metric": "secret"},
    ],
)
def test_plan_rejects_unsafe_or_underspecified_output(payload):
    with pytest.raises(ValidationError):
        QueryPlan.model_validate(payload)


@pytest.mark.parametrize(
    "question",
    [
        "DELETE all nodes",
        "DETACH DELETE n",
        "load csv from file",
        "Show password",
        "tüm filmleri sil",
        "export users",
        "CALL apoc.help()",
    ],
)
def test_unsafe_request(question):
    with pytest.raises(HTTPException) as error:
        guard_question(question)
    assert error.value.status_code == 422


@pytest.mark.parametrize("intent", list(queries.PLAN_QUERIES))
def test_compiler_uses_exact_known_queries(intent):
    plan = QueryPlan(intent=intent, user_id=42, movie_id=1)
    query_id, text, params = compile_plan(plan, fake_service())
    assert text == queries.PLAN_QUERIES[intent]
    assert len(query_id) == 12
    assert params["run_id"] == "test-run"
    assert params["limit"] <= 50


def test_pagerank_query_and_validation():
    _, text, _ = compile_plan(QueryPlan(intent="historical_trending", metric="pagerank"), fake_service())
    assert text == queries.PAGERANK
    for text in ["MATCH (n) RETURN n", queries.SIMILAR + " DELETE n", "CALL dbms.listConfig()"]:
        with pytest.raises(HTTPException):
            validate_template(text)


def test_entity_and_genre_fail_closed():
    for plan in [
        QueryPlan(intent="similar_movies", movie_id=999),
        QueryPlan(intent="recommend_movies", user_id=42, genre="InventedGenre"),
        QueryPlan(intent="unsupported", reason="No actor data"),
    ]:
        with pytest.raises(HTTPException):
            compile_plan(plan, fake_service())


def response(content):
    return httpx.Response(
        200,
        request=httpx.Request("POST", "http://test/chat/completions"),
        json={"choices": [{"message": {"content": content}}]},
    )


def test_real_adapter_parses_typed_plan(monkeypatch):
    post = Mock(return_value=response(json.dumps({"intent": "recommend_movies", "user_id": 42})))
    monkeypatch.setattr("app.agent.client.httpx.post", post)
    assert LLMClient(Settings()).plan(AskRequest(question="Recommend user 42"), []).user_id == 42
    assert post.call_args.kwargs["json"]["temperature"] == 0


def test_adapter_repair_limit(monkeypatch):
    post = Mock(return_value=response('{"raw_cypher":"DELETE everything"}'))
    monkeypatch.setattr("app.agent.client.httpx.post", post)
    with pytest.raises(HTTPException) as error:
        LLMClient(Settings()).plan(AskRequest(question="Similar movie 1"), [])
    assert error.value.status_code == 502
    assert post.call_count == 2


@pytest.mark.parametrize("error,status", [(httpx.ReadTimeout("timeout"), 504), (httpx.ConnectError("offline"), 503)])
def test_adapter_transport_failures(monkeypatch, error, status):
    monkeypatch.setattr("app.agent.client.httpx.post", Mock(side_effect=error))
    with pytest.raises(HTTPException) as caught:
        LLMClient(Settings()).plan(AskRequest(question="Recommend"), [])
    assert caught.value.status_code == status


def test_workflow_explains_before_execution_and_caps_budget():
    client = Mock()
    client.plan.return_value = QueryPlan(intent="recommend_movies", user_id=42, limit=50)
    service = fake_service()
    result = answer(AskRequest(question="Recommend user 42", user_id=42, limit=2), service, client, "trace")
    assert result.parameters["limit"] == 2
    assert service.repository.store.calls[0][0].startswith("EXPLAIN ")
    assert len(result.rows) <= 2


def test_model_cannot_switch_user_context():
    client = Mock()
    client.plan.return_value = QueryPlan(intent="recommend_movies", user_id=99)
    with pytest.raises(HTTPException):
        answer(AskRequest(question="Recommend", user_id=42), fake_service(), client, "trace")


def test_model_cannot_guess_known_movie_id():
    client = Mock()
    client.plan.return_value = QueryPlan(intent="similar_movies", movie_id=1)
    with pytest.raises(HTTPException) as caught:
        answer(AskRequest(question="Find similar movies"), fake_service(), client, "trace")
    assert caught.value.status_code == 422


@pytest.mark.parametrize("question", ["Who directed movie 1?", "Tell me the plot of movie 1"])
def test_missing_dataset_fields_are_rejected(question):
    with pytest.raises(HTTPException) as caught:
        guard_question(question)
    assert caught.value.status_code == 422


def test_explicit_genre_count_and_ids_survive_model_omission(monkeypatch):
    post = Mock(return_value=response('{"intent":"recommend_movies"}'))
    monkeypatch.setattr("app.agent.client.httpx.post", post)
    plan = LLMClient(Settings()).plan(AskRequest(question="Recommend 3 Sci-Fi movies for user 42"), ["Sci-Fi", "Drama"])
    assert plan.user_id == 42 and plan.genre == "Sci-Fi" and plan.limit == 3


def test_literal_identity_cannot_be_changed(monkeypatch):
    post = Mock(return_value=response('{"intent":"recommend_movies","user_id":1}'))
    monkeypatch.setattr("app.agent.client.httpx.post", post)
    with pytest.raises(HTTPException) as error:
        LLMClient(Settings()).plan(AskRequest(question="Recommend movies for user 42"), [])
    assert error.value.status_code == 502


def test_missing_identity_requests_clarification(monkeypatch):
    monkeypatch.setattr("app.agent.client.httpx.post", Mock(return_value=response('{"intent":"recommend_movies"}')))
    with pytest.raises(HTTPException) as error:
        LLMClient(Settings()).plan(AskRequest(question="Recommend movies"), [])
    assert error.value.status_code == 422
