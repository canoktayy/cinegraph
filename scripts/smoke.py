"""Probe real HTTP services and store safe demonstration evidence."""

import json

import httpx

from app.config import ROOT
from scripts.data import write_json


def main():
    """Check the four main features, documentation and bounded error behavior."""
    paths = [
        "/health/live",
        "/health/ready",
        "/docs",
        "/openapi.json",
        "/api/system/status",
        "/api/movies/1/similar",
        "/api/users/42/recommendations",
        "/api/users/42/discover",
        "/api/movies/trending",
        "/api/movies?limit=99999",
        "/api/users/999999/recommendations",
    ]
    results = []
    with httpx.Client(base_url="http://127.0.0.1:18080", timeout=15) as client:
        for path in paths:
            response = client.get(path)
            expected = 422 if "99999" in path and "limit" in path else (404 if "/users/999999/" in path else 200)
            results.append(
                {
                    "path": path,
                    "status": response.status_code,
                    "expected": expected,
                    "passed": response.status_code == expected,
                }
            )
        recommendations = client.get("/api/users/42/recommendations").json()
        if recommendations.get("items"):
            movie_id = recommendations["items"][0]["movie_id"]
            response = client.get(f"/api/users/42/recommendations/{movie_id}/explanation")
            write_json(ROOT / "docs/evidence/explanation.json", response.json())
        write_json(ROOT / "docs/evidence/recommendations.json", recommendations)
    write_json(ROOT / "artifacts/reports/http_smoke.json", results)
    print(json.dumps(results, indent=2))
    if not all(item["passed"] for item in results):
        raise SystemExit("HTTP smoke checks failed")


if __name__ == "__main__":
    main()
