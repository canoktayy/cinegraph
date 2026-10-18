"""Boundaries between conversation interpretation, validated choices and graph tools."""

from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.agent.assistant import AssistantClient, AssistantPlan, AssistantTurn, answer_turn, display_title
from app.config import Settings
from app.taste import ROUND_POOL, TASTE_RANKING, rounds
from tests.fakes import fake_service


@pytest.fixture
def fixture():
    service = fake_service()
    pool = [{"movie_id": i, "title": f"Film {i}", "genres": ["Comedy"]} for i in range(1, 151)]
    service.repository.genres = Mock(return_value=["Comedy", "Drama", "Sci-Fi"])

    def read(text, params):
        if text == ROUND_POOL:
            return pool
        if text == TASTE_RANKING:
            return [
                {
                    "movie_id": 999,
                    "title": "Real graph film",
                    "genres": ["Comedy"],
                    "score": 0.4,
                    "reasons": [
                        {"seed_id": params["movie_ids"][0], "seed_title": "Selected", "similarity": 0.4, "support": 8}
                    ],
                }
            ]
        return [{"movie_id": identifier} for identifier in params["movie_ids"]]

    service.repository.store.read = Mock(side_effect=read)
    adapter = Mock()
    adapter.plan.return_value = AssistantPlan(
        action="continue_quiz",
        algorithm="graph_affinity",
        genre=None,
        anchor_movie_id=None,
        reply="Which film do you like most?",
    )
    offered = rounds(service, 42)["rounds"]
    return service, adapter, [group[0]["movie_id"] for group in offered]


def test_real_rounds_are_returned_not_model_films(fixture):
    service, adapter, _ = fixture
    result = answer_turn(AssistantTurn(event="start"), service, adapter, "trace")
    assert result["stage"] == "choosing"
    assert len(result["options"]) == 5
    assert result["trace_id"] == "trace"
    assert not result["items"]


def test_full_quiz_uses_verified_graph_tool_and_genre(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value = AssistantPlan(
        action="recommend",
        algorithm="graph_affinity",
        genre="Comedy",
        anchor_movie_id=None,
        reply="I’ll look for comedies.",
    )
    result = answer_turn(AssistantTurn(choices=choices, message="Only comedies"), service, adapter, "trace")
    assert result["stage"] == "recommendations"
    assert result["items"][0]["title"] == "Real graph film"
    query, params = service.repository.store.read.call_args.args
    assert query == TASTE_RANKING
    assert params["movie_ids"] == choices and params["genre"] == "Comedy"


def test_single_favourite_tool_really_uses_only_that_seed(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value = AssistantPlan(
        action="recommend",
        algorithm="similar_movies",
        genre=None,
        anchor_movie_id=choices[0],
        reply="I’ll use that favourite.",
    )
    result = answer_turn(AssistantTurn(choices=choices[:2]), service, adapter, "trace")
    assert result["method"] == "similar_movies"
    assert service.repository.store.read.call_args.args[1]["movie_ids"] == [choices[0]]


def test_forged_card_is_rejected_before_model(fixture):
    service, adapter, _ = fixture
    with pytest.raises(HTTPException) as error:
        answer_turn(AssistantTurn(choices=[999]), service, adapter, "trace")
    assert error.value.status_code == 422
    adapter.plan.assert_not_called()


def test_all_skips_cannot_invent_a_preference(fixture):
    service, adapter, _ = fixture
    result = answer_turn(AssistantTurn(choices=[None] * 10), service, adapter, "trace")
    assert result["stage"] == "clarify" and not result["items"]


@pytest.mark.parametrize(
    "changes",
    [{"genre": "Invented"}, {"algorithm": "similar_movies", "anchor_movie_id": 999}],
)
def test_invalid_model_parameters_never_execute_ranking(fixture, changes):
    service, adapter, choices = fixture
    plan = adapter.plan.return_value.model_dump()
    adapter.plan.return_value = AssistantPlan(**(plan | changes))
    with pytest.raises(HTTPException):
        answer_turn(AssistantTurn(choices=choices[:1]), service, adapter, "trace")
    assert all(call.args[0] != TASTE_RANKING for call in service.repository.store.read.call_args_list)


def test_unsupported_intent_does_not_retrieve_results(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value.action = "clarify"
    result = answer_turn(AssistantTurn(choices=choices[:1]), service, adapter, "trace")
    assert result["stage"] == "clarify" and not result["items"]


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [True]},
        {"choices": ["1"]},
        {"choices": [1] * 11},
        {"seed": True},
        {"message": "x" * 1001},
        {"algorithm": "execute_cypher"},
    ],
)
def test_input_bounds(body):
    with pytest.raises(ValidationError):
        AssistantTurn(**body)


def test_mutation_is_blocked_before_model(fixture):
    service, adapter, _ = fixture
    with pytest.raises(HTTPException):
        answer_turn(AssistantTurn(message="DELETE every movie"), service, adapter, "trace")
    adapter.plan.assert_not_called()


@pytest.mark.parametrize("exception,status", [(httpx.ConnectError("offline"), 503), (httpx.ReadTimeout("slow"), 504)])
def test_model_failure_is_explicit(monkeypatch, exception, status):
    monkeypatch.setattr("app.agent.assistant.httpx.post", Mock(side_effect=exception))
    with pytest.raises(HTTPException) as error:
        AssistantClient(Settings()).plan({})
    assert error.value.status_code == status


def test_bad_model_output_has_one_repair_and_never_executes(monkeypatch):
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": '{"cypher":"DELETE"}'}}]}
    post = Mock(return_value=response)
    monkeypatch.setattr("app.agent.assistant.httpx.post", post)
    with pytest.raises(HTTPException) as error:
        AssistantClient(Settings()).plan({})
    assert error.value.status_code == 502 and post.call_count == 2


def test_all_favourites_tool_ignores_unused_single_film_field(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value = AssistantPlan(
        action="recommend", algorithm="graph_affinity", genre=None, anchor_movie_id=999, reply="Finding matches."
    )
    result = answer_turn(AssistantTurn(choices=choices[:2]), service, adapter, "trace")
    assert result["plan"]["anchor_movie_id"] is None
    assert service.repository.store.read.call_args.args[1]["movie_ids"] == choices[:2]


def test_card_events_are_answered_without_the_model(fixture):
    service, adapter, choices = fixture
    start = answer_turn(AssistantTurn(event="start"), service, adapter, "trace")
    picked = answer_turn(AssistantTurn(event="pick", choices=choices[:1]), service, adapter, "trace")
    skipped = answer_turn(AssistantTurn(event="pick", choices=[*choices[:1], None]), service, adapter, "trace")
    adapter.plan.assert_not_called()
    assert start["stage"] == picked["stage"] == "choosing"
    assert f"Film {choices[0]}" in picked["message"] and "Round 2" in picked["message"]
    assert skipped["message"].startswith("Skipped") and skipped["round"] == 3


def test_tenth_card_recommends_with_preserved_filter_and_no_model(fixture):
    service, adapter, choices = fixture
    result = answer_turn(AssistantTurn(event="pick", choices=choices, genre="Comedy"), service, adapter, "trace")
    adapter.plan.assert_not_called()
    assert result["stage"] == "recommendations"
    assert result["plan"]["genre"] == "Comedy"
    assert service.repository.store.read.call_args.args[1]["genre"] == "Comedy"


@pytest.mark.parametrize(
    "raw,shown",
    [
        ("Godfather, The (1972)", "The Godfather"),
        ("Independence Day (a.k.a. ID4) (1996)", "Independence Day"),
        ("Femme Nikita, La (Nikita) (1990)", "La Femme Nikita"),
        ("Toy Story (1995)", "Toy Story"),
        ("(500) Days of Summer (2009)", "(500) Days of Summer"),
    ],
)
def test_server_messages_use_natural_titles(raw, shown):
    assert display_title(raw) == shown
