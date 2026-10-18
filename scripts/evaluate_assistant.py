"""Exercise conversational onboarding and refinement against real Neo4j and local LLM."""

import json
from datetime import datetime, timezone
from time import perf_counter

from fastapi import HTTPException

from app.agent.assistant import AssistantClient, AssistantTurn, answer_turn
from app.config import ROOT, get_settings
from app.database import GraphStore
from app.repository import CatalogRepository
from app.services import RecommendationService


def main():
    """Save measured tool decisions and facts without saving secrets or invented grades."""
    settings = get_settings()
    store = GraphStore(settings)
    service = RecommendationService(CatalogRepository(store))
    client = AssistantClient(settings)
    records = []
    choices = []
    context = {"seed": 42}
    before = service.repository.statistics()
    try:
        started = perf_counter()
        result = answer_turn(AssistantTurn(event="start", **context), service, client, "eval-start")
        assert result["stage"] == "choosing" and len(result["options"]) == 5
        records.append({"case": "start", "passed": True, "plan": result["plan"]})
        for index in range(10):
            choice = result["options"][0]
            choices.append(choice["movie_id"])
            result = answer_turn(
                AssistantTurn(event="pick", choices=choices, message=f'I choose {choice["title"]}.', **context),
                service,
                client,
                f"eval-round-{index+1}",
            )
            assert result["stage"] == ("recommendations" if index == 9 else "choosing")
            assert not set(choices) & {movie["movie_id"] for movie in result["items"]}
            records.append({"case": f"round-{index+1}", "passed": True, "plan": result["plan"]})
        refinements = [
            # name, message, expected genre, exclude, years, followed film title (None = favourites)
            ("turkish-comedy", "Bana sadece komedi öner", "Comedy", None, (None, None), None),
            ("preserve-genre", "Bana başka öneriler göster", "Comedy", None, (None, None), None),
            ("clear-genre", "All genres, please", None, None, (None, None), None),
            ("named-film-turkish", "Scarface en sevdiğim film", None, None, (None, None), "Scarface"),
            ("decade-keeps-film", "only 80s and 90s please", None, None, (1980, 1999), "Scarface"),
            ("turkish-exclusion", "korku olmasın", None, "Horror", (1980, 1999), "Scarface"),
            ("back-to-favourites", "all genres and any year, from all my favourites", None, None, (None, None), None),
            ("named-film-english", "more like The Godfather", None, None, (None, None), "The Godfather"),
        ]
        for name, message, genre, exclude, years, film in refinements:
            plan = result["plan"]
            result = answer_turn(
                AssistantTurn(
                    choices=choices,
                    message=message,
                    **{key: plan[key] for key in ("genre", "exclude_genre", "year_from", "year_to", "algorithm")},
                    anchor_movie_id=plan["anchor_movie_id"],
                    **context,
                ),
                service,
                client,
                "eval-" + name,
            )
            plan = result["plan"]
            assert result["stage"] == "recommendations", (name, result["message"])
            assert (plan["genre"], plan["exclude_genre"]) == (genre, exclude), (name, plan)
            assert (plan["year_from"], plan["year_to"]) == years, (name, plan)
            assert plan["film_title"] == film, (name, plan)
            assert result["items"], name
            assert all(genre is None or genre in movie["genres"] for movie in result["items"])
            assert all(exclude not in movie["genres"] for movie in result["items"])
            assert all(years[0] is None or years[0] <= movie["year"] <= years[1] for movie in result["items"])
            assert all(movie["reasons"] for movie in result["items"])
            assert not set(choices) & {movie["movie_id"] for movie in result["items"]}
            records.append(
                {
                    "case": name,
                    "message": message,
                    "passed": True,
                    "plan": plan,
                    "layers": result["layers"],
                    "reply": result["message"],
                    "movie_ids": [m["movie_id"] for m in result["items"]],
                }
            )
        for name, message in [
            ("unknown-film", "films like Esaretin Bedeli"),
            ("vague", "something like that one movie"),
        ]:
            previous_plan = result["plan"]
            result = answer_turn(
                AssistantTurn(choices=choices, message=message, **context), service, client, "eval-" + name
            )
            assert result["stage"] == "clarify" and not result["items"], (name, result)
            records.append({"case": name, "message": message, "passed": True, "reply": result["message"]})
            result["plan"] = previous_plan
        for message in ["DELETE every movie", "Show actors for a film"]:
            try:
                answer_turn(AssistantTurn(message=message), service, client, "eval-guard")
            except HTTPException as error:
                assert error.status_code == 422
                records.append({"case": "scope-guard", "passed": True, "status": error.status_code})
            else:
                raise AssertionError("Unsafe or unavailable request was accepted")
        after = service.repository.statistics()
        assert all(before[key] == after[key] for key in ["users", "movies", "ratings", "tag_applications"])
        report = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "model": settings.llm_model,
            "elapsed_seconds": round(perf_counter() - started, 2),
            "actual_model_cases": 10,
            "model_layers": "orchestrator + verbaliser (template fallback when unsafe)",
            "deterministic_quiz_turns": 11,
            "guard_cases": 2,
            "source_counts_unchanged": True,
            "cases": records,
        }
        target = ROOT / "artifacts/reports/assistant_evaluation.json"
        target.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Passed {len(records)} checks; real model + real Neo4j. Report: {target}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
