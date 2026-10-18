"""Two-layer assistant: the orchestrator decides, the server checks and runs, the verbaliser only describes."""

from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.agent.assistant import (
    AssistantClient,
    AssistantIntent,
    AssistantTurn,
    answer_turn,
    display_title,
    explicit_filters,
    grounded,
    turkish,
)
from app.config import Settings
from app.taste import FILM_LOOKUP, ROUND_POOL, TASTE_RANKING, rounds
from tests.fakes import fake_service

GENRES = ["Comedy", "Crime", "Drama", "Horror", "Romance", "Sci-Fi", "Thriller", "War"]
CATALOG = {
    "scarface": [
        {"movie_id": 4262, "title": "Scarface (1983)", "votes": 80, "score": 3.1},
        {"movie_id": 25788, "title": "Scarface (1932)", "votes": 3, "score": 3.1},
    ],
    "star wars": [
        {"movie_id": 79702, "title": "Star Wars: The Clone Wars (2008)", "votes": 6, "score": 2.6},
        {"movie_id": 260, "title": "Star Wars: Episode IV - A New Hope (1977)", "votes": 251, "score": 2.0},
    ],
}


def intent(**fields):
    """A complete orchestrator answer with neutral defaults."""
    base = {
        "action": "recommend",
        "source": "favourites",
        "film_title": None,
        "genre": None,
        "exclude_genre": None,
        "year_from": None,
        "year_to": None,
        "clarify_reason": None,
    }
    return AssistantIntent(**(base | fields))


@pytest.fixture
def fixture():
    service = fake_service()
    pool = [{"movie_id": i, "title": f"Film {i} (2000)", "genres": ["Drama"]} for i in range(1, 151)]
    service.repository.genres = Mock(return_value=GENRES)
    service.repository.exists = Mock(return_value=True)

    def read(text, params):
        if text == ROUND_POOL:
            return pool
        if text == FILM_LOOKUP:
            typed = params["search"].replace('"', "").replace(" AND ", " ").casefold()
            return CATALOG.get(typed, [])
        if text == TASTE_RANKING:
            seed = params["movie_ids"][0]
            return [
                {
                    "movie_id": 999,
                    "title": "Goodfellas (1990)",
                    "genres": ["Crime"],
                    "score": 0.4,
                    "reasons": [{"seed_id": seed, "seed_title": "Seed", "similarity": 0.4, "support": 8}],
                }
            ]
        if "$id" in text:
            return [{"movie_id": params["id"], "title": "Scarface (1983)"}]
        return [{"movie_id": identifier} for identifier in params["movie_ids"]]

    service.repository.store.read = Mock(side_effect=read)
    adapter = Mock()
    adapter.plan.return_value = intent()
    adapter.verbalise.return_value = "Films for you: Goodfellas."
    offered = rounds(service, 42)["rounds"]
    return service, adapter, [group[0]["movie_id"] for group in offered]


def ranking_calls(service):
    """Parameters of every recommendation query that actually ran."""
    return [call.args[1] for call in service.repository.store.read.call_args_list if call.args[0] == TASTE_RANKING]


def test_card_events_never_call_either_model_layer(fixture):
    service, adapter, choices = fixture
    start = answer_turn(AssistantTurn(event="start"), service, adapter, "trace")
    picked = answer_turn(AssistantTurn(event="pick", choices=choices[:1]), service, adapter, "trace")
    skipped = answer_turn(AssistantTurn(event="pick", choices=[*choices[:1], None]), service, adapter, "trace")
    adapter.plan.assert_not_called()
    adapter.verbalise.assert_not_called()
    assert start["stage"] == picked["stage"] == "choosing" and len(start["options"]) == 5
    assert "Film" in picked["message"] and "Round 2" in picked["message"]
    assert skipped["message"].startswith("Skipped") and skipped["round"] == 3
    assert start["layers"] == {"orchestrator": "none", "verbaliser": "none"}


def test_tenth_card_recommends_with_preserved_filters(fixture):
    service, adapter, choices = fixture
    result = answer_turn(
        AssistantTurn(event="pick", choices=choices, genre="Crime", year_from=1980), service, adapter, "trace"
    )
    adapter.plan.assert_not_called()
    assert result["stage"] == "recommendations"
    assert ranking_calls(service)[-1]["genre"] == "Crime" and ranking_calls(service)[-1]["year_from"] == 1980


def test_scarface_regression_follows_the_named_film_not_a_selected_one(fixture):
    """Logged bug: 'Scarface is my favourite' produced films similar to The Lion King."""
    service, adapter, choices = fixture
    adapter.plan.return_value = intent(source="film", film_title="Scarface")
    adapter.verbalise.return_value = "Scarface'e benzeyen filmler: Goodfellas."
    result = answer_turn(
        AssistantTurn(choices=choices[:6], message="Scarface en sevdiğim film"), service, adapter, "trace"
    )
    assert ranking_calls(service)[-1]["movie_ids"] == [4262], "the 1983 film with most ratings"
    assert result["plan"]["film_title"] == "Scarface" and result["plan"]["anchor_movie_id"] == 4262
    assert result["layers"] == {"orchestrator": "model", "verbaliser": "model"}


def test_a_film_the_visitor_did_not_name_is_never_used(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value = intent(source="film", film_title="The Lion King")
    result = answer_turn(AssistantTurn(choices=choices, message="Scarface is my favourite"), service, adapter, "trace")
    assert result["stage"] == "clarify" and "Which film" in result["message"]
    assert not ranking_calls(service)


def test_film_titles_resolve_to_the_most_rated_matching_title(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value = intent(source="film", film_title="Star Wars")
    answer_turn(AssistantTurn(choices=choices[:2], message="more like Star Wars"), service, adapter, "trace")
    assert ranking_calls(service)[-1]["movie_ids"] == [260]


def test_unknown_film_asks_in_the_visitors_language(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value = intent(source="film", film_title="Esaretin Bedeli")
    result = answer_turn(
        AssistantTurn(choices=choices, message="Esaretin Bedeli gibi filmler istiyorum"), service, adapter, "trace"
    )
    assert result["stage"] == "clarify" and "katalogda bulamadım" in result["message"]
    adapter.verbalise.assert_not_called()


def test_written_filters_beat_a_flipped_model_reading(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value = intent(genre="Comedy")  # The model misread "no comedy".
    result = answer_turn(
        AssistantTurn(choices=choices, message="no comedy, only 80s and 90s", genre="Drama"), service, adapter, "trace"
    )
    assert result["plan"]["exclude_genre"] == "Comedy"
    assert result["plan"]["genre"] == "Drama", "filters the visitor did not mention stay as they were"
    assert (result["plan"]["year_from"], result["plan"]["year_to"]) == (1980, 1999)


def test_a_clarifying_turn_changes_nothing(fixture):
    service, adapter, choices = fixture
    adapter.plan.return_value = intent(action="clarify", genre="Horror", clarify_reason="Which one?")
    result = answer_turn(
        AssistantTurn(
            choices=choices, message="that one", genre="Drama", anchor_movie_id=4262, algorithm="similar_movies"
        ),
        service,
        adapter,
        "trace",
    )
    assert result["stage"] == "clarify"
    assert result["plan"]["genre"] == "Drama" and result["plan"]["anchor_movie_id"] == 4262
    assert not ranking_calls(service)


def test_filter_refinement_keeps_the_followed_film(fixture):
    service, adapter, choices = fixture
    result = answer_turn(
        AssistantTurn(choices=choices, message="no horror please", anchor_movie_id=4262, algorithm="similar_movies"),
        service,
        adapter,
        "trace",
    )
    assert ranking_calls(service)[-1]["movie_ids"] == [4262]
    assert ranking_calls(service)[-1]["exclude_genre"] == "Horror"
    assert result["plan"]["film_title"] == "Scarface"


def test_asking_for_favourites_leaves_the_followed_film(fixture):
    service, adapter, choices = fixture
    answer_turn(
        AssistantTurn(
            choices=choices[:3], message="from all my favourites", anchor_movie_id=4262, algorithm="similar_movies"
        ),
        service,
        adapter,
        "trace",
    )
    assert ranking_calls(service)[-1]["movie_ids"] == choices[:3]


@pytest.mark.parametrize(
    "spoken",
    [
        "Films like “The Lion King”: Goodfellas.",
        "Is this what you wanted?",
        "x" * 300,
        "Senin için filmler: Goodfellas.",
    ],
)
def test_unsafe_verbaliser_output_falls_back_to_facts(fixture, spoken):
    service, adapter, choices = fixture
    adapter.verbalise.return_value = spoken
    result = answer_turn(AssistantTurn(choices=choices, message="recommend now"), service, adapter, "trace")
    assert result["layers"]["verbaliser"] == "template" and "Goodfellas" in result["message"]


def test_verbaliser_outage_still_returns_the_graph_results(fixture):
    service, adapter, choices = fixture
    adapter.verbalise.side_effect = HTTPException(503, "offline")
    result = answer_turn(AssistantTurn(choices=choices, message="recommend now"), service, adapter, "trace")
    assert result["stage"] == "recommendations" and result["items"]
    assert result["layers"]["verbaliser"] == "template"


def test_forged_card_is_rejected_before_any_model_call(fixture):
    service, adapter, _ = fixture
    with pytest.raises(HTTPException) as error:
        answer_turn(AssistantTurn(choices=[999]), service, adapter, "trace")
    assert error.value.status_code == 422
    adapter.plan.assert_not_called()


def test_mutation_is_blocked_before_any_model_call(fixture):
    service, adapter, _ = fixture
    with pytest.raises(HTTPException):
        answer_turn(AssistantTurn(message="DELETE every movie"), service, adapter, "trace")
    adapter.plan.assert_not_called()


def test_no_seed_asks_for_a_favourite_or_a_film(fixture):
    service, adapter, _ = fixture
    result = answer_turn(AssistantTurn(choices=[None] * 3, message="recommend now"), service, adapter, "trace")
    assert result["stage"] == "clarify" and not ranking_calls(service)


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [True]},
        {"choices": ["1"]},
        {"choices": [1] * 11},
        {"seed": True},
        {"message": "x" * 1001},
        {"algorithm": "execute_cypher"},
        {"year_from": 1500},
    ],
)
def test_input_bounds(body):
    with pytest.raises(ValidationError):
        AssistantTurn(**body)


@pytest.mark.parametrize(
    "message,expected",
    [
        ("no comedy", {"exclude_genre": "Comedy"}),
        ("korku olmasın", {"exclude_genre": "Horror"}),
        ("Bana sadece komedi öner", {"genre": "Comedy"}),
        ("only 80s and 90s please", {"year_from": 1980, "year_to": 1999}),
        ("90lar gerilim", {"genre": "Thriller", "year_from": 1990, "year_to": 1999}),
        ("romantik filmler 2000 öncesi", {"genre": "Romance", "year_to": 1999}),
        ("all genres", {"genre": None, "exclude_genre": None}),
        ("Scarface en sevdiğim film", {}),
    ],
)
def test_explicit_filters(message, expected):
    assert explicit_filters(message, GENRES) == expected


def test_film_titles_are_not_read_as_genres():
    assert explicit_filters("more like Star Wars", GENRES, "Star Wars") == {}


def test_grounding_and_language_detection():
    assert grounded("Scarface", "Scarface en sevdiğim film")
    assert not grounded("The Lion King", "Scarface en sevdiğim film")
    assert not grounded("that one movie", "something like that one movie")
    assert grounded("Se7en", "films like Se7en") and grounded("Up", "more like Up please")
    assert turkish("korku olmasın") and turkish("bana sadece komedi") and not turkish("only comedies please")


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
