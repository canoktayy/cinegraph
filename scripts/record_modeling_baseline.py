"""Capture an actual baseline from the same movie-project brief, without editing its output."""

from datetime import datetime, timezone

import httpx

from app.config import ROOT, get_settings
from scripts.data import write_json

PROMPT = """Movie Recommender in Production. Build a production-grade recommendation service over a
user/movie bipartite graph using Neo4j and MovieLens small. Example:
(:User)-[:RATED]->(:Movie), (:Movie)-[:IN_GENRE]->(:Genre).
Consider genres as nodes, properties, or both. Features: similar movies, personalized recommendations,
community-based discovery, popularity/centrality ranking. Include NL-to-Cypher and an explanation
endpoint relying on real graph paths. Propose a basic graph schema with identities, relationships,
properties and a short modeling rationale. Use only fields actually present in MovieLens small.
"""


def main():
    """Keep the prompt, model identity, timestamp and complete returned text."""
    settings = get_settings()
    response = httpx.post(
        settings.llm_base_url.rstrip("/") + "/chat/completions",
        json={
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0,
            "max_tokens": 900,
        },
        timeout=90,
    )
    response.raise_for_status()
    record = {
        "model": settings.llm_model,
        "provider": "LM Studio local model",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "prompt": PROMPT,
        "output": response.json()["choices"][0]["message"]["content"],
    }
    write_json(ROOT / "docs/evidence/modeling-baseline.json", record)
    print("Recorded actual unedited baseline output")


if __name__ == "__main__":
    main()
