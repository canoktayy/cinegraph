"""Compile allow-listed plans and verify exact templates before execution."""

import hashlib
import re

from fastapi import HTTPException

from app import queries
from app.agent.plans import QueryPlan
from app.services import RecommendationService

FORBIDDEN_REQUEST = re.compile(
    r"\b(delete|detach|drop|load\s+csv|apoc|password|credential|export|erase|sil|şifre|parola)\b", re.I
)


def guard_question(question: str):
    """Reject obvious out-of-scope requests; the compiler remains the actual security boundary."""
    if FORBIDDEN_REQUEST.search(question):
        raise HTTPException(422, {"code": "unsafe_request", "message": "Only bounded catalog read queries are allowed"})
    if re.search(r"\b(director|directed|actor|actress|plot|yönetmen|oyuncu|senaryo)\b", question, re.I):
        raise HTTPException(422, {"code": "unsupported_data", "message": "MovieLens has no credits or plot evidence"})


def validate_template(text: str):
    """An exact allow-list is stronger than trying to sanitize free-form Cypher."""
    allowed = {*queries.PLAN_QUERIES.values(), queries.PAGERANK}
    if text not in allowed:
        raise HTTPException(422, {"code": "unsafe_query", "message": "Query does not match a reviewed template"})


def compile_plan(plan: QueryPlan, service: RecommendationService) -> tuple[str, str, dict]:
    """Resolve domain entities, then bind parameters without string interpolation."""
    if plan.intent == "unsupported":
        raise HTTPException(422, {"code": "unsupported_intent", "message": plan.reason or "Unsupported question"})
    if plan.user_id:
        service.require("user", plan.user_id)
    if plan.movie_id:
        service.require("movie", plan.movie_id)
    if plan.genre and plan.genre not in service.repository.genres():
        raise HTTPException(422, {"code": "unknown_genre", "message": "Genre is not in the dataset vocabulary"})
    params = service.parameters(plan.model_dump(exclude_none=True))
    params["since"] = max(0, params["as_of"] - plan.window_days * 86400)
    text = queries.PLAN_QUERIES[plan.intent]
    if plan.intent == "historical_trending" and plan.metric == "pagerank":
        text = queries.PAGERANK
    validate_template(text)
    query_id = hashlib.sha256(text.encode()).hexdigest()[:12]
    return query_id, text, params
