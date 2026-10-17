// Canonical implementation: app/queries.py
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
RETURN candidate.movie_id AS movie_id, candidate.title AS title,
candidate.year AS year, [(candidate)-[:IN_GENRE]->(g:Genre) | g.name] AS genres, a.bayesian_rating AS score,
a.vote_count AS support, affinity AS supporting_seeds
ORDER BY supporting_seeds DESC, score DESC, movie_id ASC LIMIT $limit;
