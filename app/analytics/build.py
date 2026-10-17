"""Real Neo4j GDS jobs with staging, versioned output and atomic activation."""

import hashlib
import json
import time
from collections import defaultdict

from app.config import ROOT, get_settings
from app.database import GraphStore
from app.scoring import bayesian_rating, shrunk_jaccard
from scripts.data import batches, write_json

CONFIG = {"like_threshold": 4.0, "min_common": 3, "beta": 5, "candidate_top_k": 40, "top_k": 20}


def drop_projection(store: GraphStore, name: str):
    """Drop only this job's named graph; never touch another project's projection."""
    store.write("CALL gds.graph.drop($name,false) YIELD graphName RETURN graphName", {"name": name})


def project_likes(store: GraphStore, name: str, cutoff: int):
    """Reverse rating direction so movies, not users, are compared by Node Similarity."""
    return store.write(
        """CALL gds.graph.project.cypher($name,
      'MATCH (n) WHERE n:Movie OR n:User RETURN id(n) AS id',
      'MATCH (u:User)-[r:RATED]->(m:Movie)
       WHERE r.score >= 4 AND r.timestamp <= $cutoff
       RETURN id(m) AS source,id(u) AS target',
      {parameters:{cutoff:$cutoff}})
    YIELD nodeCount,relationshipCount RETURN nodeCount,relationshipCount""",
        {"name": name, "cutoff": cutoff},
    )[0]


def similarity_rows(store: GraphStore, name: str, cutoff: int) -> list[dict]:
    """Combine GDS Jaccard with auditable source support and reliability shrinkage."""
    likes = defaultdict(set)
    for row in store.read(
        """MATCH (u:User)-[r:RATED]->(m:Movie) WHERE r.score>=4 AND r.timestamp<=$cutoff
    RETURN u.user_id AS user_id,m.movie_id AS movie_id""",
        {"cutoff": cutoff},
    ):
        likes[row["movie_id"]].add(row["user_id"])
    raw = store.write(
        """CALL gds.nodeSimilarity.stream($name,
      {topK:40,degreeCutoff:3,similarityCutoff:0.01,similarityMetric:'JACCARD',concurrency:1})
      YIELD node1,node2,similarity
      RETURN gds.util.asNode(node1).movie_id AS source,
             gds.util.asNode(node2).movie_id AS target,similarity""",
        {"name": name},
    )
    neighbors = defaultdict(list)
    for row in raw:
        score, support = shrunk_jaccard(likes[row["source"]], likes[row["target"]])
        if support >= CONFIG["min_common"] and row["source"] != row["target"]:
            neighbors[row["source"]].append(
                {"source": row["source"], "target": row["target"], "score": score, "support": support}
            )
    result = []
    for candidates in neighbors.values():
        result.extend(sorted(candidates, key=lambda item: (-item["score"], -item["support"], item["target"]))[:20])
    return result


def persist_similarity(store: GraphStore, rows: list[dict], run_id: str):
    """Write new edges under a new run ID without invalidating the active run."""
    versioned = [{**row, "run_id": run_id} for row in rows]
    batches(
        store,
        """UNWIND $rows AS row MATCH (a:Movie {movie_id:row.source}),(b:Movie {movie_id:row.target})
      MERGE (a)-[s:SIMILAR_TO {run_id:row.run_id}]->(b)
      SET s.score=row.score,s.support=row.support,s.method='gds_jaccard_shrinkage',s.computed_at=datetime()
      RETURN count(s) AS processed""",
        versioned,
    )


def project_movies(store: GraphStore, name: str, run_id: str) -> dict:
    """Deduplicate both top-K directions before making an undirected weighted projection."""
    return store.write(
        """CALL gds.graph.project.cypher($name,
    'MATCH (m:Movie) RETURN id(m) AS id',
    'MATCH (a:Movie)-[s:SIMILAR_TO]->(b:Movie) WHERE s.run_id=$run_id
     WITH CASE WHEN id(a)<id(b) THEN id(a) ELSE id(b) END AS left_id,
          CASE WHEN id(a)<id(b) THEN id(b) ELSE id(a) END AS right_id,
          max(s.score) AS weight
     UNWIND [[left_id,right_id],[right_id,left_id]] AS pair
     RETURN pair[0] AS source,pair[1] AS target,weight',
    {parameters:{run_id:$run_id}})
    YIELD nodeCount,relationshipCount RETURN nodeCount,relationshipCount""",
        {"name": name, "run_id": run_id},
    )[0]


def graph_algorithms(store: GraphStore, name: str) -> tuple[list[dict], list[dict]]:
    """Execute two real GDS algorithms, not Python substitutes."""
    communities = store.write(
        """CALL gds.louvain.stream($name,
    {relationshipWeightProperty:'weight',concurrency:1}) YIELD nodeId,communityId
    RETURN gds.util.asNode(nodeId).movie_id AS movie_id,communityId AS community_id""",
        {"name": name},
    )
    ranks = store.write(
        """CALL gds.pageRank.stream($name,
    {relationshipWeightProperty:'weight',dampingFactor:0.85,maxIterations:20,concurrency:1})
    YIELD nodeId,score RETURN gds.util.asNode(nodeId).movie_id AS movie_id,score AS pagerank""",
        {"name": name},
    )
    return communities, ranks


def persist_statistics(store: GraphStore, communities: list, ranks: list, run_id: str):
    """Store per-run memberships rather than overwrite active movie properties."""
    stats = store.read(
        """MATCH (m:Movie) OPTIONAL MATCH (:User)-[r:RATED]->(m)
    RETURN m.movie_id AS movie_id,count(r) AS vote_count,coalesce(avg(r.score),0) AS mean"""
    )
    global_mean = store.read("MATCH ()-[r:RATED]->() RETURN avg(r.score) AS mean")[0]["mean"]
    rank_map = {row["movie_id"]: row["pagerank"] for row in ranks}
    community_map = {row["movie_id"]: row["community_id"] for row in communities}
    rows = [
        {
            **row,
            "run_id": run_id,
            "community_id": community_map[row["movie_id"]],
            "pagerank": rank_map[row["movie_id"]],
            "bayesian_rating": bayesian_rating(row["vote_count"], row["mean"], global_mean),
        }
        for row in stats
    ]
    batches(
        store,
        """UNWIND $rows AS row MATCH (m:Movie {movie_id:row.movie_id}),
    (run:AnalyticsRun {run_id:row.run_id}) MERGE (m)-[a:ANALYZED_IN]->(run)
    SET a.community_id=row.community_id,a.pagerank=row.pagerank,
        a.vote_count=row.vote_count,a.bayesian_rating=row.bayesian_rating
    RETURN count(a) AS processed""",
        rows,
    )


def build() -> dict:
    """Publish analytics only after every staging check succeeds."""
    store = GraphStore(get_settings().model_copy(update={"query_timeout_seconds": 300}))
    names = ["moviegraph-job-likes", "moviegraph-job-movies"]
    started = time.monotonic()
    try:
        state = store.read("MATCH (s:SystemState {key:'dataset'}) RETURN properties(s) AS state")[0]["state"]
        code_hash = hashlib.sha256(
            (ROOT / "app/analytics/build.py").read_bytes() + (ROOT / "app/scoring.py").read_bytes()
        ).hexdigest()
        signature = json.dumps({"dataset": state["data_version"], "config": CONFIG, "code": code_hash}, sort_keys=True)
        run_id = "gds-" + hashlib.sha256(signature.encode()).hexdigest()[:16]
        if state.get("active_run_id") == run_id:
            print(f"Already active: {run_id}")
            return {"run_id": run_id, "reused": True}
        gds_version = store.read("RETURN gds.version() AS version")[0]["version"]
        for name in names:
            drop_projection(store, name)
        store.write(
            """MERGE (r:AnalyticsRun {run_id:$run_id})
        SET r.status='staging',r.dataset_hash=$dataset,r.cutoff=$cutoff,r.gds_version=$gds""",
            {"run_id": run_id, "dataset": state["data_version"], "cutoff": state["as_of"], "gds": gds_version},
        )
        likes_info = project_likes(store, names[0], state["as_of"])
        estimate = store.write(
            """CALL gds.nodeSimilarity.stream.estimate($name,{topK:40,degreeCutoff:3})
        YIELD requiredMemory,bytesMin,bytesMax RETURN requiredMemory,bytesMin,bytesMax""",
            {"name": names[0]},
        )[0]
        similarities = similarity_rows(store, names[0], state["as_of"])
        if not similarities:
            raise ValueError("No supported similarity edges; refusing to activate an empty run")
        persist_similarity(store, similarities, run_id)
        movie_info = project_movies(store, names[1], run_id)
        communities, ranks = graph_algorithms(store, names[1])
        persist_statistics(store, communities, ranks, run_id)
        self_edges = store.read(
            "MATCH (m)-[s:SIMILAR_TO]->(m) WHERE s.run_id=$run_id RETURN count(s) AS n", {"run_id": run_id}
        )[0]["n"]
        if self_edges or len(communities) != movie_info["nodeCount"]:
            raise ValueError("Analytics invariant failed")
        store.write(
            """MATCH (s:SystemState {key:'dataset'}),(r:AnalyticsRun {run_id:$run_id})
        SET r.status='active',r.activated_at=datetime(),s.active_run_id=$run_id""",
            {"run_id": run_id},
        )
        connected_movies = {row[key] for row in similarities for key in ("source", "target")}
        report = {
            "run_id": run_id,
            "data_version": state["data_version"],
            "cutoff": state["as_of"],
            "gds_version": gds_version,
            "config": CONFIG,
            "code_sha256": code_hash,
            "likes_projection": likes_info,
            "movie_projection": movie_info,
            "memory_estimate": estimate,
            "similarity_edges": len(similarities),
            "communities": len({row["community_id"] for row in communities}),
            "connected_movies": len(connected_movies),
            "non_isolated_communities": len(
                {row["community_id"] for row in communities if row["movie_id"] in connected_movies}
            ),
            "duration_seconds": round(time.monotonic() - started, 3),
            "limitations": [
                "Top-40 raw Jaccard candidates are shrunk and truncated to top-20; not exhaustive",
                "Louvain IDs are run-specific; deterministic partition is not guaranteed",
            ],
        }
        write_json(ROOT / "artifacts/reports/gds.json", report)
        print(json.dumps(report, indent=2))
        return report
    finally:
        for name in names:
            drop_projection(store, name)
        store.close()


if __name__ == "__main__":
    build()
