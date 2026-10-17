"""Join public display-only poster metadata by both TMDB and IMDb source identities."""

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import httpx

from app.config import get_settings
from app.database import GraphStore

SOURCE = (
    "https://www.kaggle.com/api/v1/datasets/download/"
    "asaniczka/tmdb-movies-dataset-2023-930k-movies/TMDB_movie_dataset_v11.csv"
)
SOURCE_PAGE = "https://www.kaggle.com/datasets/asaniczka/tmdb-movies-dataset-2023-930k-movies"
EXPECTED_SHA256 = "f629bccb91ab3e8871f6baabfc02b0b496ab61ffe389daee26e5ee92ef4688d6"
OUTPUT = Path("app/static/posters.json")


def match_posters(movies, metadata):
    """Require matching independent film IDs and a strictly validated poster path."""
    wanted = {(movie["tmdb_id"], "tt" + (movie["imdb_id"] or "")) for movie in movies}
    lookup = {}
    for row in metadata:
        identifier = row.get("id") or ""
        if not identifier.isdigit():
            continue
        key = (int(identifier), row.get("imdb_id"))
        if key in wanted and re.fullmatch(r"/[A-Za-z0-9]+\.(jpg|png)", row.get("poster_path") or ""):
            lookup[key] = row
    found = {}
    for movie in movies:
        row = lookup.get((movie["tmdb_id"], "tt" + (movie["imdb_id"] or "")))
        if row:
            # Compact [file name, TMDB ID]: the browser builds sized image URLs and the TMDB page link.
            found[str(movie["movie_id"])] = [row["poster_path"].lstrip("/"), movie["tmdb_id"]]
    return found


def main():
    """Download one metadata archive, pin its bytes, and publish only image references."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=Path("data/poster_metadata.csv"))
    path = parser.parse_args().metadata
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".partial")
        with httpx.stream("GET", SOURCE, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with partial.open("wb") as target:
                for chunk in response.iter_bytes():
                    target.write(chunk)
        partial.replace(path)
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Poster metadata snapshot changed; review source before accepting a new checksum")
    store = GraphStore(get_settings())
    try:
        movies = store.read(
            """MATCH (m:Movie) RETURN m.movie_id AS movie_id,m.title AS title,
                              m.imdb_id AS imdb_id,m.tmdb_id AS tmdb_id"""
        )
    finally:
        store.close()
    with path.open(encoding="utf-8", newline="") as source:
        found = match_posters(movies, csv.DictReader(source))
    OUTPUT.write_text(json.dumps(found, separators=(",", ":")) + "\n", encoding="utf-8")
    report = {
        "source": SOURCE_PAGE,
        "download": SOURCE,
        "metadata_sha256": digest,
        "catalog_movies": len(movies),
        "matched_posters": len(found),
        "unmatched_movies": len(movies) - len(found),
        "join": "exact TMDB ID AND IMDb ID",
        "image_binaries_stored": False,
        "format": "{movie_id: [poster file name, tmdb_id]}",
        "provider": "TMDB",
        "limitation": "Historical references can be unavailable; the UI retains a designed fallback.",
    }
    Path("artifacts/reports/posters.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
