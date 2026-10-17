"""Measure actual query plans and the trade-off of precomputed bounded neighbors."""

import json
import hashlib
import platform
import random
import statistics
import subprocess
from time import perf_counter

import numpy as np

from app import queries
from app.config import ROOT, get_settings
from app.database import GraphStore
from app.repository import CatalogRepository
from scripts.data import write_json


def timed(store, text, params):
    """Time materialized query results, not lazy result construction."""
    started = perf_counter()
    rows = store.read(text, params)
    return (perf_counter() - started) * 1000, rows


def capture_plan(store, text, params):
    """Keep PROFILE overhead separate from normal latency measurements."""
    with store.driver.session(database=store.settings.neo4j_database) as session:
        result = session.run("PROFILE " + text, params)
        result.data()
        return result.consume().profile


def summarize(values):
    """Return descriptive workload statistics with explicit units."""
    return {
        "samples": len(values),
        "p50_ms": round(statistics.median(values), 3),
        "p95_ms": round(float(np.percentile(values, 95)), 3),
        "min_ms": round(min(values), 3),
    }


def main():
    """Benchmark the same movie IDs and record ranking differences, not just speed."""
    store = GraphStore(get_settings().model_copy(update={"query_timeout_seconds": 30}))
    try:
        state = CatalogRepository(store).state()
        candidates = store.read(
            """MATCH (m:Movie)-[s:SIMILAR_TO]->() WHERE s.run_id=$run_id
        WITH m,count(s) AS degree WHERE degree>=10 RETURN m.movie_id AS movie_id ORDER BY movie_id""",
            {"run_id": state["active_run_id"]},
        )
        ids = random.Random(42).sample([row["movie_id"] for row in candidates], min(30, len(candidates)))
        before, after, overlaps = [], [], []
        for movie_id in ids[:5]:
            params = {"movie_id": movie_id, "run_id": state["active_run_id"], "min_common": 3, "limit": 10}
            timed(store, queries.DIRECT_SIMILAR, params)
            timed(store, queries.SIMILAR, params)
        for movie_id in ids:
            params = {"movie_id": movie_id, "run_id": state["active_run_id"], "min_common": 3, "limit": 10}
            elapsed, direct = timed(store, queries.DIRECT_SIMILAR, params)
            before.append(elapsed)
            elapsed, cached = timed(store, queries.SIMILAR, params)
            after.append(elapsed)
            left = {row["movie_id"] for row in direct}
            right = {row["movie_id"] for row in cached}
            overlaps.append(len(left & right) / max(1, len(left)))
        params = {"movie_id": 1, "run_id": state["active_run_id"], "min_common": 3, "limit": 10}
        report = {
            "query_source_sha256": hashlib.sha256((ROOT / "app/queries.py").read_bytes()).hexdigest(),
            "dataset_hash": state["data_version"],
            "analytics_run_id": state["active_run_id"],
            "platform": platform.platform(),
            "seed": 42,
            "workload_ids": ids,
            "warmup_queries": 5,
            "direct_graph": summarize(before),
            "precomputed_gds": summarize(after),
            "mean_top10_overlap": float(np.mean(overlaps)),
            "notes": [
                "Sequential local client workload; not a concurrent load or SLA test",
                "Precomputed top-40 raw Jaccard candidates can differ from exhaustive shrunk ranking",
            ],
        }
        try:
            report["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        except subprocess.CalledProcessError:
            report["commit"] = None
        write_json(ROOT / "artifacts/reports/benchmark.json", report)
        write_json(ROOT / "docs/evidence/profile-direct.json", capture_plan(store, queries.DIRECT_SIMILAR, params))
        write_json(ROOT / "docs/evidence/profile-precomputed.json", capture_plan(store, queries.SIMILAR, params))
        write_json(
            ROOT / "docs/evidence/profile-index.json",
            capture_plan(store, "MATCH (m:Movie {movie_id:$movie_id}) RETURN m.title AS title", {"movie_id": 1}),
        )
        print(json.dumps(report, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
