"""Explainable ranking policy and graceful cold-start behavior."""

from fastapi import HTTPException

from app import queries
from app.models import Evidence, ExplanationResponse, RankingResponse
from app.repository import CatalogRepository


class RecommendationService:
    """Compose bounded graph queries into domain-level responses."""

    def __init__(self, repository: CatalogRepository):
        self.repository = repository

    def require(self, kind: str, identifier: int):
        """Distinguish an unknown identity from an empty recommendation list."""
        if not self.repository.exists(kind, identifier):
            raise HTTPException(404, f"Unknown {kind} ID: {identifier}")

    def parameters(self, overrides: dict | None = None) -> dict:
        """Create safe defaults bound to the current active dataset snapshot."""
        state = self.repository.state()
        return {
            "run_id": state.get("active_run_id"),
            "as_of": state.get("as_of", 0),
            "since": 0,
            "limit": 10,
            "genre": None,
            "user_id": None,
            "min_votes": 3,
            **(overrides or {}),
        }

    def envelope(self, rows: list[dict], method: str, score_type: str, fallback: str | None = None):
        """Attach provenance without claiming a score is a confidence probability."""
        state = self.repository.state()
        return RankingResponse(
            items=rows,
            method=method,
            score_type=score_type,
            fallback_reason=fallback,
            data_version=state.get("data_version"),
            analytics_run_id=state.get("active_run_id"),
            as_of=state.get("as_of"),
        )

    def similar(self, movie_id: int, limit: int = 10):
        """Use precomputed GDS neighbors, then an explicit small-data traversal fallback."""
        self.require("movie", movie_id)
        params = self.parameters({"movie_id": movie_id, "limit": limit, "min_common": 3})
        rows = self.repository.execute("similar_movies", params)
        if rows:
            return self.envelope(rows, "gds_item_similarity", "shrunk_jaccard")
        rows = self.repository.store.read(queries.DIRECT_SIMILAR, params)
        return self.envelope(rows, "direct_graph_similarity", "shrunk_jaccard", "No precomputed neighbors")

    def recommendations(self, user_id: int, limit: int = 10, genre: str | None = None):
        """Recommend unrated candidates and label sparse-history fallback explicitly."""
        self.require("user", user_id)
        params = self.parameters({"user_id": user_id, "limit": limit, "genre": genre})
        rows = self.repository.execute("recommend_movies", params)
        if rows:
            return self.envelope(rows, "item_cf", "weighted_rating")
        rows = self.repository.execute("historical_trending", params)
        return self.envelope(rows, "bayesian_popularity", "bayesian_rating", "Sparse history or analytics unavailable")

    def favourites(self, user_id: int, limit: int = 8):
        """Show the observed high ratings that item-CF recommendations start from."""
        self.require("user", user_id)
        rows = self.repository.store.read(
            queries.USER_FAVOURITES, self.parameters({"user_id": user_id, "limit": limit})
        )
        return self.envelope(rows, "observed_ratings", "rating")

    def discover(self, user_id: int, limit: int = 10):
        """Discover unrated films from the user's dominant Louvain communities."""
        self.require("user", user_id)
        params = self.parameters({"user_id": user_id, "limit": limit})
        rows = self.repository.execute("discover_movies", params)
        if rows:
            return self.envelope(rows, "louvain_discovery", "bayesian_rating")
        response = self.recommendations(user_id, limit)
        response.fallback_reason = "No community candidates; " + (response.fallback_reason or "using item CF")
        return response

    def trending(self, filters: dict):
        """Use the dataset's last timestamp, never imply a live market-style trend."""
        params = self.parameters(filters)
        params["since"] = max(0, params["as_of"] - filters.get("window_days", 365) * 86400)
        if filters.get("metric") == "pagerank":
            rows = self.repository.store.read(queries.PAGERANK, params)
            return self.envelope(rows, "graph_pagerank", "centrality")
        rows = self.repository.execute("historical_trending", params)
        return self.envelope(rows, "historical_activity", "bayesian_rating")

    def explanation(self, user_id: int, movie_id: int):
        """Render precise path evidence for the actual item-CF calculation."""
        self.require("user", user_id)
        self.require("movie", movie_id)
        params = self.parameters({"user_id": user_id, "movie_id": movie_id})
        rated = self.repository.store.read(
            "MATCH (:User {user_id:$user_id})-[r:RATED]->(:Movie {movie_id:$movie_id}) RETURN r.score AS score",
            params,
        )
        rows = self.repository.execute("explain_recommendation", params) if not rated else []
        denominator = sum(row["similarity"] for row in rows)
        evidence = [self._evidence(row, params, denominator, index) for index, row in enumerate(rows[:3], 1)]
        if rated:
            text = "This movie is already rated by the user and is excluded from new recommendations."
        elif evidence:
            seeds = "; ".join(
                f'{row["seed_title"]} (rating {row["source_rating"]:g}, similarity {row["similarity"]:.3f}, '
                f'{row["support"]} shared positive raters)'
                for row in rows[:3]
            )
            text = f"Supported by movies in your rating history: {seeds}. Evidence shows graph affinity, not certainty."
        else:
            text = (
                "No item-CF evidence path exists in the active run. A popularity fallback is not personalized evidence."
            )
        return ExplanationResponse(
            user_id=user_id,
            movie_id=movie_id,
            recommended=bool(rows),
            explanation=text,
            evidence=evidence,
            analytics_run_id=params["run_id"],
        )

    @staticmethod
    def _evidence(row: dict, params: dict, denominator: float, index: int):
        """Serialize stable domain identities, not internal Neo4j node IDs."""
        return Evidence(
            evidence_id=f"ev-{params['run_id']}-{index}",
            type="collaborative_path",
            path=[
                {"label": "User", "user_id": params["user_id"]},
                {"relationship": "RATED", "score": row["source_rating"]},
                {"label": "Movie", "movie_id": row["seed_id"], "title": row["seed_title"]},
                {"relationship": "SIMILAR_TO", "score": row["similarity"]},
                {"label": "Movie", "movie_id": params["movie_id"]},
            ],
            source_rating=row["source_rating"],
            similarity=row["similarity"],
            support=row["support"],
            contribution=row["numerator"] / denominator,
            run_id=params["run_id"],
            provenance="derived",
        )
