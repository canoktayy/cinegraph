"""Small auditable domain fixtures; integration tests never use these doubles."""

from app.services import RecommendationService

ITEM = {
    "movie_id": 2,
    "title": "Candidate (2001)",
    "year": 2001,
    "genres": ["Drama"],
    "score": 4.25,
    "support": 8,
    "supporting_seeds": 2,
}


class FakeStore:
    """Record query calls and support controlled failure-path fixtures."""

    def __init__(self):
        self.calls = []
        self.rated = False

    def healthy(self):
        return True

    def read(self, text, parameters=None):
        self.calls.append((text, parameters))
        if text.startswith("EXPLAIN"):
            return []
        if "RETURN r.score AS score" in text:
            return [{"score": 4}] if self.rated else []
        return [ITEM.copy()]


class FakeRepository:
    """A fixture with one user, two movies and one verified evidence path."""

    def __init__(self):
        self.store = FakeStore()
        self.empty = set()
        self.seeded = True

    def state(self):
        return {"active_run_id": "test-run", "data_version": "hash", "as_of": 1500000000} if self.seeded else {}

    def exists(self, kind, identifier):
        return identifier in ({42} if kind == "user" else {1, 2})

    def genres(self):
        return ["Drama", "Sci-Fi"]

    def search(self, filters):
        return [ITEM.copy()][: filters["limit"]]

    def statistics(self):
        return {"users": 1, "movies": 2, "ratings": 1, **self.state()}

    def execute(self, intent, params):
        if intent in self.empty:
            return []
        if intent == "explain_recommendation":
            return [
                {
                    "seed_id": 1,
                    "seed_title": "Seed",
                    "source_rating": 4.5,
                    "rating_timestamp": 1,
                    "similarity": 0.4,
                    "support": 8,
                    "numerator": 1.8,
                }
            ]
        return [ITEM.copy()]


def fake_service():
    return RecommendationService(FakeRepository())
