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
            ("turkish-comedy", "Bana sadece komedi öner", "Comedy", "graph_affinity"),
            ("preserve-genre", "Bana başka öneriler göster", "Comedy", "graph_affinity"),
            ("clear-genre", "All genres, please", None, "graph_affinity"),
            (
                "single-favourite",
                f'Find films similar to {result["selected_movies"][0]["title"]}',
                None,
                "similar_movies",
            ),
        ]
        for name, message, genre, algorithm in refinements:
            plan = result["plan"]
            result = answer_turn(
                AssistantTurn(
                    choices=choices,
                    message=message,
                    genre=plan["genre"],
                    algorithm=plan["algorithm"],
                    anchor_movie_id=plan["anchor_movie_id"],
                    **context,
                ),
                service,
                client,
                "eval-" + name,
            )
            assert result["stage"] == "recommendations", result
            assert result["plan"]["genre"] == genre and result["method"] == algorithm, result["plan"]
            assert result["items"] and all(genre is None or genre in movie["genres"] for movie in result["items"])
            assert all(movie["reasons"] for movie in result["items"])
            assert not set(choices) & {movie["movie_id"] for movie in result["items"]}
            records.append(
                {
                    "case": name,
                    "passed": True,
                    "plan": result["plan"],
                    "movie_ids": [m["movie_id"] for m in result["items"]],
                }
            )
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
            "actual_model_cases": 4,
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
