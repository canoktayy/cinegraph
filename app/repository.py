"""Domain queries over observed graph facts and versioned analytics."""

import re

from app import queries
from app.database import GraphStore


class CatalogRepository:
    """Keep all API database operations parameterized and bounded."""

    def __init__(self, store: GraphStore):
        self.store = store
        self._snapshot = None

    def state(self) -> dict:
        """Return snapshot identity and the atomically selected analytics run."""
        if self._snapshot is None:
            rows = self.store.read("MATCH (s:SystemState {key:'dataset'}) RETURN properties(s) AS state")
            self._snapshot = rows[0]["state"] if rows else {}
        return self._snapshot.copy()

    def exists(self, kind: str, identifier: int) -> bool:
        """Resolve only hard-coded domain identities, never arbitrary labels."""
        statements = {
            "user": "MATCH (u:User {user_id:$identifier}) RETURN count(u) AS count",
            "movie": "MATCH (m:Movie {movie_id:$identifier}) RETURN count(m) AS count",
        }
        return self.store.read(statements[kind], {"identifier": identifier})[0]["count"] > 0

    def genres(self) -> list[str]:
        """Get the canonical genre vocabulary for filtering and entity validation."""
        return [row["name"] for row in self.store.read("MATCH (g:Genre) RETURN g.name AS name ORDER BY name")]

    def search(self, filters: dict) -> list[dict]:
        """Search title tokens through the full-text index, or browse by stable ID."""
        params = {"q": "", "genre": None, "year": None, "offset": 0, "limit": 20, **filters}
        tokens = re.findall(r"[\w]+", params["q"], flags=re.UNICODE)
        if params["q"] and not tokens:
            return []
        params["search"] = " AND ".join(f'"{token}"' for token in tokens)
        prefix = (
            "CALL db.index.fulltext.queryNodes('movie_title',$search) YIELD node AS candidate, score "
            if tokens
            else "MATCH (candidate:Movie) "
        )
        query = (
            prefix
            + """
        WHERE ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
        AND ($year IS NULL OR candidate.year=$year)
        RETURN """
            + queries.MOVIE_FIELDS
            + " ORDER BY movie_id SKIP $offset LIMIT $limit"
        )
        return self.store.read(query, params)

    def execute(self, intent: str, params: dict) -> list[dict]:
        """Execute only a named, application-owned query."""
        return self.store.read(queries.PLAN_QUERIES[intent], params)

    def statistics(self) -> dict:
        """Return actual domain counts and algorithm availability."""
        rows = self.store.read(
            """CALL { MATCH (u:User) RETURN count(u) AS users }
            CALL { MATCH (m:Movie) RETURN count(m) AS movies }
            CALL { MATCH ()-[r:RATED]->() RETURN count(r) AS ratings }
            CALL { MATCH (a:TagApplication) RETURN count(a) AS tag_applications }
            CALL { MATCH (g:Genre) RETURN count(g) AS genres }
            RETURN users,movies,ratings,tag_applications,genres"""
        )
        return {**rows[0], **self.state()}
