"""One traceable model-planning and database-tool execution workflow."""

from fastapi import HTTPException

from app.agent.client import LLMClient, explicit_entities
from app.agent.compiler import compile_plan, guard_question, validate_template
from app.models import AskRequest, AskResponse
from app.services import RecommendationService


def answer(request: AskRequest, service: RecommendationService, client: LLMClient, trace_id: str):
    """Plan, validate, EXPLAIN, execute and render only verified result counts."""
    guard_question(request.question)
    supplied = explicit_entities(request)
    plan = client.plan(request, service.repository.genres())
    # The caller's requested result budget cannot be expanded by the model.
    plan.limit = min(plan.limit, request.limit)
    if plan.movie_id and plan.movie_id != supplied.get("movie_id"):
        raise HTTPException(
            422, "Movie identity must be explicitly provided; title resolution needs a catalog selection"
        )
    if plan.user_id and plan.user_id != supplied.get("user_id"):
        raise HTTPException(422, "User identity was not supplied in the question or context")
    if request.user_id and plan.user_id and request.user_id != plan.user_id:
        raise HTTPException(422, "Model changed the explicitly supplied user context")
    query_id, text, params = compile_plan(plan, service)
    validate_template(text)
    service.repository.store.read("EXPLAIN " + text, params)
    rows = service.repository.store.read(text, params)[: plan.limit]
    warnings = [] if rows else ["No matching facts in the active graph; no result was invented."]
    if plan.intent == "historical_trending":
        warnings.append("Historical dataset snapshot; this is not today's live popularity.")
    titles = ", ".join(str(row.get("title", row.get("seed_title", "Evidence"))) for row in rows[:5])
    return AskResponse(
        status="ok",
        interpreted_intent=plan.model_dump(),
        query_id=query_id,
        compiled_cypher=text.strip(),
        parameters=params,
        rows=rows,
        explanation=(
            f"Verified graph results: {titles}." if rows else "No matching evidence was found in the active graph."
        ),
        warnings=warnings,
        trace_id=trace_id,
    )
