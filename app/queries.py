"""Auditable Cypher templates: model output is never interpolated into these strings."""

MOVIE_FIELDS = """candidate.movie_id AS movie_id, candidate.title AS title,
candidate.year AS year, [(candidate)-[:IN_GENRE]->(g:Genre) | g.name] AS genres"""

SIMILAR = (
    """
MATCH (seed:Movie {movie_id: $movie_id})-[s:SIMILAR_TO]->(candidate:Movie)
WHERE s.run_id = $run_id
  AND ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
RETURN """
    + MOVIE_FIELDS
    + """, s.score AS score, s.support AS support
ORDER BY score DESC, support DESC, movie_id ASC LIMIT $limit
"""
)

DIRECT_SIMILAR = (
    """
MATCH (seed:Movie {movie_id: $movie_id})<-[r1:RATED]-(u:User)-[r2:RATED]->(candidate:Movie)
WHERE r1.score >= 4 AND r2.score >= 4 AND seed <> candidate
WITH seed, candidate, count(DISTINCT u) AS common
WHERE common >= $min_common
CALL { WITH seed MATCH (:User)-[r:RATED]->(seed)
       WHERE r.score >= 4 RETURN count(r) AS left_count }
CALL { WITH candidate MATCH (:User)-[r:RATED]->(candidate)
       WHERE r.score >= 4 RETURN count(r) AS right_count }
RETURN """
    + MOVIE_FIELDS
    + """, common AS support,
toFloat(common)/(left_count+right_count-common)*common/(common+5) AS score
ORDER BY score DESC, support DESC, movie_id ASC LIMIT $limit
"""
)

RECOMMEND = (
    """
MATCH (u:User {user_id: $user_id})-[r:RATED]->(seed:Movie)
WHERE r.score >= 4
WITH u, r, seed ORDER BY r.timestamp DESC, seed.movie_id ASC LIMIT 50
MATCH (seed)-[s:SIMILAR_TO]->(candidate:Movie)
WHERE s.run_id = $run_id AND s.score > 0
  AND NOT EXISTS { MATCH (u)-[:RATED]->(candidate) }
  AND ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
WITH candidate, round(sum(s.score*r.score)/sum(s.score), 8) AS score,
     count(DISTINCT seed) AS supporting_seeds, sum(s.support) AS support
RETURN """
    + MOVIE_FIELDS
    + """, score, support, supporting_seeds
ORDER BY score DESC, supporting_seeds DESC, movie_id ASC LIMIT $limit
"""
)

DISCOVER = (
    """
MATCH (u:User {user_id:$user_id})-[r:RATED]->(seed:Movie)
MATCH (seed)-[membership:ANALYZED_IN]->(run:AnalyticsRun {run_id:$run_id})
WHERE r.score >= 4
WITH u, run, membership.community_id AS community, count(*) AS affinity
ORDER BY affinity DESC, community ASC LIMIT 3
MATCH (candidate:Movie)-[a:ANALYZED_IN]->(run)
WHERE a.community_id = community AND a.vote_count >= 3
  AND ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
  AND NOT EXISTS { MATCH (u)-[:RATED]->(candidate) }
WITH candidate, a, affinity
RETURN """
    + MOVIE_FIELDS
    + """, a.bayesian_rating AS score,
a.vote_count AS support, affinity AS supporting_seeds
ORDER BY supporting_seeds DESC, score DESC, movie_id ASC LIMIT $limit
"""
)

BASELINE = (
    """
MATCH (:SystemState {key:'dataset'})
CALL { MATCH (:User)-[rating:RATED]->(:Movie) RETURN avg(rating.score) AS global_mean }
MATCH (candidate:Movie)
WHERE ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
  AND ($user_id IS NULL OR NOT EXISTS { MATCH (:User {user_id:$user_id})-[:RATED]->(candidate) })
MATCH (:User)-[r:RATED]->(candidate)
WHERE r.timestamp >= $since AND r.timestamp <= $as_of
WITH candidate, global_mean, count(r) AS votes, avg(r.score) AS mean
WHERE votes >= $min_votes
RETURN """
    + MOVIE_FIELDS
    + """, votes AS support,
(votes*mean+20*global_mean)/(votes+20) AS score
ORDER BY score DESC, support DESC, movie_id ASC LIMIT $limit
"""
)

PAGERANK = (
    """
MATCH (candidate:Movie)-[a:ANALYZED_IN]->(:AnalyticsRun {run_id:$run_id})
WHERE a.vote_count >= $min_votes
RETURN """
    + MOVIE_FIELDS
    + """, a.pagerank AS score, a.vote_count AS support
ORDER BY score DESC, movie_id ASC LIMIT $limit
"""
)

EVIDENCE = """
MATCH (u:User {user_id:$user_id})-[r:RATED]->(seed:Movie)
WHERE r.score >= 4
WITH u, r, seed ORDER BY r.timestamp DESC, seed.movie_id ASC LIMIT 50
MATCH (seed)-[s:SIMILAR_TO]->(target:Movie {movie_id:$movie_id})
WHERE s.run_id = $run_id AND s.score > 0
RETURN seed.movie_id AS seed_id, seed.title AS seed_title,
       r.score AS source_rating, r.timestamp AS rating_timestamp,
       s.score AS similarity, s.support AS support,
       s.score*r.score AS numerator
ORDER BY numerator DESC, seed_id ASC
"""

PLAN_QUERIES = {
    "similar_movies": SIMILAR,
    "recommend_movies": RECOMMEND,
    "discover_movies": DISCOVER,
    "historical_trending": BASELINE,
    "explain_recommendation": EVIDENCE,
}
