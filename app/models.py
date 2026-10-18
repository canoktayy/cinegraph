"""Public API contracts; generated or derived facts carry provenance."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


MAX_GRAPH_ID = 2**63 - 1


class Movie(BaseModel):
    """Catalog identity independent of a possibly ambiguous film title."""

    movie_id: int
    title: str
    year: int | None = None
    genres: list[str] = Field(default_factory=list)


class RankedMovie(Movie):
    """Ranked item with interpretable score semantics."""

    score: float
    support: int = 0
    supporting_seeds: int = 0


class RankingResponse(BaseModel):
    """Stable list envelope, including snapshot and fallback information."""

    items: list[RankedMovie]
    method: str
    data_version: str | None = None
    analytics_run_id: str | None = None
    as_of: int | None = None
    fallback_reason: str | None = None
    score_type: str


class Evidence(BaseModel):
    """Verifiable explanation path; analytical edges are explicitly derived."""

    evidence_id: str
    type: str
    path: list[dict[str, Any]]
    source_rating: float | None = None
    similarity: float | None = None
    support: int | None = None
    contribution: float | None = None
    run_id: str | None = None
    provenance: Literal["observed", "derived"]


class ExplanationResponse(BaseModel):
    """Deterministic evidence rendering never invents plot or credits."""

    user_id: int
    movie_id: int
    recommended: bool
    explanation: str
    evidence: list[Evidence]
    analytics_run_id: str | None = None
    note: str = "A recommendation is not a guarantee of future preference."


class AskRequest(BaseModel):
    """Untrusted natural-language input with a small explicit budget."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)
    # "template": the model picks a plan mapped to reviewed Cypher. "generated": the model writes Cypher, then it is checked.
    mode: Literal["template", "generated"] = "template"
    user_id: int | None = Field(default=None, gt=0, le=MAX_GRAPH_ID, strict=True)
    limit: int = Field(default=10, ge=1, le=50)


class AskResponse(BaseModel):
    """Expose interpretation, executed query and actual graph results."""

    status: str
    interpreted_intent: dict
    query_id: str
    compiled_cypher: str
    parameters: dict
    rows: list[dict]
    explanation: str
    trace_id: str
    warnings: list[str] = Field(default_factory=list)


class PathStep(BaseModel):
    """One link of a path: how strongly two neighbouring films are connected."""

    score: float
    support: int


class PathResponse(BaseModel):
    """Shortest chain of similarity links between two films; `found` is false beyond the hop limit."""

    found: bool
    hops: int | None = None
    films: list[Movie] = Field(default_factory=list)
    links: list[PathStep] = Field(default_factory=list)
    max_hops: int
    analytics_run_id: str | None = None
    note: str = "Each link means many people rated both films 4 stars or more. It is a connection, not a guarantee."
