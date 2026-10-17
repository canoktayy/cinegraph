"""Stateless visitor taste discovery over the existing versioned movie graph."""

from random import Random

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app import queries


class TasteRequest(BaseModel):
    """Positive selections only: unchosen alternatives are not negative ratings."""

    model_config = ConfigDict(extra="forbid")
    movie_ids: list[int] = Field(min_length=1, max_length=10)
    genre: str | None = None
    limit: int = Field(default=8, ge=1, le=20)

    @model_validator(mode="after")
    def unique_ids(self):
        """Reject duplicate/nonpositive identities before querying the graph."""
        if any(identifier <= 0 for identifier in self.movie_ids) or len(set(self.movie_ids)) != len(self.movie_ids):
            raise ValueError("Choose distinct positive movie IDs")
        return self


ROUND_POOL = (
    """
MATCH (candidate:Movie)-[a:ANALYZED_IN]->(:AnalyticsRun {run_id:$run_id})
WHERE a.vote_count >= 40 AND EXISTS { MATCH (candidate)-[s:SIMILAR_TO]->() WHERE s.run_id=$run_id }
RETURN """
    + queries.MOVIE_FIELDS
    + """, a.vote_count AS votes
ORDER BY votes DESC, movie_id ASC LIMIT 150
"""
)

TASTE_RANKING = (
    """
UNWIND $movie_ids AS seed_id
MATCH (seed:Movie {movie_id:seed_id})-[s:SIMILAR_TO]->(candidate:Movie)
WHERE s.run_id=$run_id AND s.score>0 AND NOT candidate.movie_id IN $movie_ids
AND ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
WITH candidate, sum(s.score)/size($movie_ids) AS score,
count(DISTINCT seed) AS supporting_seeds, sum(s.support) AS support,
collect({seed_id:seed.movie_id, seed_title:seed.title, similarity:s.score, support:s.support}) AS reasons
RETURN """
    + queries.MOVIE_FIELDS
    + """, score, supporting_seeds, support, reasons
ORDER BY score DESC, supporting_seeds DESC, movie_id ASC LIMIT $limit
"""
)


def rounds(recommender, seed: int):
    """Distribute fifty distinct, well-supported films across ten seeded rounds."""
    params = recommender.parameters()
    pool = list(recommender.repository.store.read(ROUND_POOL, params))
    if len(pool) < 50:
        raise HTTPException(503, "Taste discovery needs an active analysis with at least 50 supported movies")
    Random(seed).shuffle(pool)
    chosen = pool[:50]
    return {"rounds": [chosen[index : index + 5] for index in range(0, 50, 5)], "analytics_run_id": params["run_id"]}


def recommend(recommender, body: TasteRequest):
    """Compute graph affinity without writing invented users or source ratings."""
    if body.genre and body.genre not in recommender.repository.genres():
        raise HTTPException(422, "Unknown genre")
    params = recommender.parameters(body.model_dump())
    found = recommender.repository.store.read(
        "MATCH (m:Movie) WHERE m.movie_id IN $movie_ids RETURN m.movie_id AS movie_id", params
    )
    if {row["movie_id"] for row in found} != set(body.movie_ids):
        raise HTTPException(404, "One or more selected movies do not exist")
    if not params["run_id"]:
        raise HTTPException(503, "Build graph analytics before requesting personal recommendations")
    rows = recommender.repository.store.read(TASTE_RANKING, params)
    for row in rows:
        row["reasons"] = sorted(row["reasons"], key=lambda reason: (-reason["similarity"], reason["seed_id"]))
    return {
        "items": rows,
        "method": "visitor_graph_affinity",
        "score_type": "mean_selected_seed_similarity",
        "selected_movie_ids": body.movie_ids,
        "analytics_run_id": params["run_id"],
        "note": "Based on your selections and shared positive MovieLens raters. Unchosen films are not dislikes. "
        "Affinity is not a probability or predicted star rating. No visitor account or source rating is stored.",
    }
