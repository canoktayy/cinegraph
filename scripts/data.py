"""Download, profile and idempotently import the documented MovieLens snapshot."""

import argparse
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

import httpx
import pandas as pd

from app.config import ROOT, get_settings
from app.database import GraphStore
from app.scoring import normalize_tag, parse_year, validate_rating

DATA = ROOT / "data" / "ml-latest-small"
REPORTS = ROOT / "artifacts" / "reports"
SOURCE = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
FILES = ("movies.csv", "ratings.csv", "tags.csv", "links.csv")


def write_json(path, content):
    """Persist human-readable metrics and provenance, never runtime credentials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2, default=str) + "\n")


def download():
    """Extract only expected basenames, preventing zip path traversal."""
    DATA.mkdir(parents=True, exist_ok=True)
    if all((DATA / name).exists() for name in (*FILES, "README.txt")):
        print("Existing MovieLens snapshot preserved")
        return
    response = httpx.get(SOURCE, timeout=90, follow_redirects=True)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for name in (*FILES, "README.txt"):
            (DATA / name).write_bytes(archive.read("ml-latest-small/" + name))
    write_json(
        DATA / "download.json",
        {
            "url": SOURCE,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "archive_sha256": hashlib.sha256(response.content).hexdigest(),
        },
    )
    print("Downloaded documented MovieLens snapshot")


def load_frames() -> dict[str, pd.DataFrame]:
    """Validate source types and preserve identifiers before normalization."""
    frames = {name.split(".", maxsplit=1)[0]: pd.read_csv(DATA / name) for name in FILES}
    ratings = frames["ratings"]
    ratings["rating"] = ratings["rating"].map(validate_rating)
    known = set(frames["movies"].movieId)
    for name in ("ratings", "tags", "links"):
        if not set(frames[name].movieId).issubset(known):
            raise ValueError(f"Unresolved movie references in {name}; import aborted")
    for name in ("ratings", "tags"):
        if frames[name][["userId", "movieId", "timestamp"]].isna().any().any():
            raise ValueError(f"Missing required IDs or timestamps in {name}")
    duplicates = ratings[ratings.duplicated(["userId", "movieId", "timestamp"], keep=False)]
    if not duplicates.empty and duplicates.groupby(["userId", "movieId", "timestamp"]).rating.nunique().max() > 1:
        raise ValueError("Conflicting rating values at identical timestamps")
    frames["ratings"] = ratings.sort_values("timestamp").drop_duplicates(["userId", "movieId"], keep="last")
    frames["tags"] = frames["tags"].drop_duplicates()
    return frames


def profile() -> dict:
    """Create a source manifest and auditable quality summary before import."""
    frames = load_frames()
    hashes = {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest() for name in FILES}
    data_version = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    manifest = {
        "source": SOURCE,
        "data_version": data_version,
        "files_sha256": hashes,
        "normalization_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(DATA / "manifest.json", manifest)
    ratings = frames["ratings"]
    report = {
        "data_version": data_version,
        "movies": len(frames["movies"]),
        "ratings": len(ratings),
        "tag_applications": len(frames["tags"]),
        "users": len(set(ratings.userId) | set(frames["tags"].userId)),
        "rating_min": float(ratings.rating.min()),
        "rating_max": float(ratings.rating.max()),
        "as_of": int(ratings.timestamp.max()),
        "first_rating": int(ratings.timestamp.min()),
        "rating_distribution": ratings.rating.value_counts().sort_index().to_dict(),
        "quarantined": 0,
        "duplicate_policy": "latest rating per user/movie; identical tags deduplicated",
        "license": "MovieLens README terms apply; research/educational use; attribution required",
    }
    write_json(REPORTS / "data_quality.json", report)
    print(json.dumps({key: report[key] for key in ("users", "movies", "ratings", "tag_applications")}))
    return report


def create_schema(store: GraphStore):
    """Portable Neo4j Community uniqueness constraints and useful indexes."""
    for label, field in (
        ("User", "user_id"),
        ("Movie", "movie_id"),
        ("Genre", "name"),
        ("Tag", "key"),
        ("TagApplication", "application_id"),
        ("SystemState", "key"),
        ("AnalyticsRun", "run_id"),
    ):
        store.write(
            f"CREATE CONSTRAINT {label.lower()}_identity IF NOT EXISTS FOR (n:{label}) REQUIRE n.{field} IS UNIQUE"
        )
    store.write("CREATE RANGE INDEX movie_year IF NOT EXISTS FOR (m:Movie) ON (m.year)")
    store.write("CREATE FULLTEXT INDEX movie_title IF NOT EXISTS FOR (m:Movie) ON EACH [m.title]")
    store.write("CALL db.awaitIndexes(120)")


def batches(store: GraphStore, query: str, rows: list[dict]):
    """Check processed-row counts so missing MATCH references never silently disappear."""
    for start in range(0, len(rows), 1000):
        batch = rows[start : start + 1000]
        processed = store.write(query, {"rows": batch})[0]["processed"]
        if processed != len(batch):
            raise ValueError(f"Import lost rows: submitted {len(batch)}, processed {processed}")


def import_movies(store: GraphStore, frames: dict):
    """Preserve raw titles, controlled genres and optional external identity fields."""
    rows = []
    links = frames["links"].set_index("movieId")
    for row in frames["movies"].itertuples():
        link = links.loc[row.movieId]
        genres = [genre for genre in str(row.genres).split("|") if genre != "(no genres listed)"]
        rows.append(
            {
                "movie_id": int(row.movieId),
                "title": row.title,
                "year": parse_year(row.title),
                "genres": genres,
                "imdb_id": f"{int(link.imdbId):07d}" if pd.notna(link.imdbId) else None,
                "tmdb_id": int(link.tmdbId) if pd.notna(link.tmdbId) else None,
            }
        )
    batches(
        store,
        """UNWIND $rows AS row
    MERGE (m:Movie {movie_id:row.movie_id}) SET m.title=row.title,m.year=row.year,
      m.imdb_id=row.imdb_id,m.tmdb_id=row.tmdb_id
    FOREACH (genre IN row.genres | MERGE (g:Genre {name:genre}) MERGE (m)-[:IN_GENRE]->(g))
    RETURN count(m) AS processed""",
        rows,
    )


def import_ratings(store: GraphStore, frame: pd.DataFrame):
    """A rating is a relationship because score/time describe a user-film pair."""
    rows = [
        {
            "user_id": int(row.userId),
            "movie_id": int(row.movieId),
            "score": float(row.rating),
            "timestamp": int(row.timestamp),
        }
        for row in frame.itertuples()
    ]
    batches(
        store,
        """UNWIND $rows AS row MERGE (u:User {user_id:row.user_id})
    WITH u,row MATCH (m:Movie {movie_id:row.movie_id}) MERGE (u)-[r:RATED]->(m)
    SET r.score=row.score,r.timestamp=row.timestamp,r.source='MovieLens'
    RETURN count(r) AS processed""",
        rows,
    )


def import_tags(store: GraphStore, frame: pd.DataFrame):
    """Retain the user/movie/tag triple and original wording as a provenance event."""
    rows = []
    for row in frame.itertuples():
        raw = str(row.tag)
        payload = [int(row.userId), int(row.movieId), raw, int(row.timestamp)]
        rows.append(
            {
                "user_id": payload[0],
                "movie_id": payload[1],
                "raw": raw,
                "timestamp": payload[3],
                "key": normalize_tag(raw),
                "id": hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest(),
            }
        )
    batches(
        store,
        """UNWIND $rows AS row MERGE (u:User {user_id:row.user_id})
    MERGE (t:Tag {key:row.key}) ON CREATE SET t.display_name=row.raw
    MERGE (a:TagApplication {application_id:row.id})
    SET a.raw_text=row.raw,a.timestamp=row.timestamp,a.source='MovieLens'
    WITH u,t,a,row MATCH (m:Movie {movie_id:row.movie_id})
    MERGE (u)-[:APPLIED]->(a) MERGE (a)-[:ON_MOVIE]->(m) MERGE (a)-[:WITH_TAG]->(t)
    RETURN count(a) AS processed""",
        rows,
    )


def seed():
    """Load a frozen snapshot; refuse an incompatible replacement in the same DB."""
    report = profile()
    frames = load_frames()
    store = GraphStore(get_settings())
    try:
        create_schema(store)
        previous = store.read("MATCH (s:SystemState {key:'dataset'}) RETURN s.data_version AS version")
        if previous and previous[0]["version"] != report["data_version"]:
            raise ValueError("Different snapshot already loaded; use a separate clean database, not a partial MERGE")
        import_movies(store, frames)
        import_ratings(store, frames["ratings"])
        import_tags(store, frames["tags"])
        store.write(
            """MERGE (s:SystemState {key:'dataset'})
        SET s.data_version=$data_version,s.as_of=$as_of,s.source='MovieLens small'""",
            {"data_version": report["data_version"], "as_of": report["as_of"]},
        )
        print("Seed completed; checking graph invariants")
        validate(store)
    finally:
        store.close()


def validate(store: GraphStore | None = None):
    """Check actual source counts, unique relationships and event cardinalities."""
    own_store = store is None
    store = store or GraphStore(get_settings())
    expected = json.loads((REPORTS / "data_quality.json").read_text())
    try:
        for label, key in (("Movie", "movies"), ("User", "users"), ("TagApplication", "tag_applications")):
            count = store.read(f"MATCH (n:{label}) RETURN count(n) AS count")[0]["count"]
            if count != expected[key]:
                raise ValueError(f"{label}: expected {expected[key]}, got {count}")
        count = store.read("MATCH ()-[r:RATED]->() RETURN count(r) AS count")[0]["count"]
        if count != expected["ratings"]:
            raise ValueError("Rating count mismatch")
        duplicates = store.read(
            """MATCH (u:User)-[r:RATED]->(m:Movie)
        WITH u,m,count(r) AS n WHERE n<>1 RETURN count(*) AS count"""
        )[0]["count"]
        invalid_events = store.read(
            """MATCH (a:TagApplication)
        WHERE size([(u:User)-[:APPLIED]->(a) | u])<>1
        OR size([(a)-[:ON_MOVIE]->(m:Movie) | m])<>1
        OR size([(a)-[:WITH_TAG]->(t:Tag) | t])<>1 RETURN count(a) AS count"""
        )[0]["count"]
        if duplicates or invalid_events:
            raise ValueError("Duplicate rating or invalid tag-event cardinality")
        print("Graph counts, rating uniqueness and tag-event cardinalities verified")
    finally:
        if own_store:
            store.close()


def main():
    """Expose explicit commands instead of destructive automatic initialization."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("download", "profile", "seed", "validate"))
    command = parser.parse_args().command
    {"download": download, "profile": profile, "seed": seed, "validate": validate}[command]()


if __name__ == "__main__":
    main()
