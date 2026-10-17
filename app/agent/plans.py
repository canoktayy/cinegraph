"""A narrow query language that an LLM cannot expand into arbitrary Cypher."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueryPlan(BaseModel):
    """Validated intermediate representation for natural language to Cypher."""

    model_config = ConfigDict(extra="forbid")
    intent: Literal[
        "similar_movies",
        "recommend_movies",
        "discover_movies",
        "historical_trending",
        "explain_recommendation",
        "unsupported",
    ]
    user_id: int | None = Field(default=None, gt=0)
    movie_id: int | None = Field(default=None, gt=0)
    genre: str | None = Field(default=None, max_length=40)
    limit: int = Field(default=10, ge=1, le=50)
    metric: Literal["rating", "pagerank"] = "rating"
    window_days: int = Field(default=365, ge=1, le=36500)
    reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def required_entities(self):
        """A supported intent cannot invent missing user context."""
        if self.intent in {"recommend_movies", "discover_movies", "explain_recommendation"} and not self.user_id:
            raise ValueError("This intent requires an explicit user_id")
        if self.intent in {"similar_movies", "explain_recommendation"} and not self.movie_id:
            raise ValueError("This intent requires an explicit movie_id")
        return self
