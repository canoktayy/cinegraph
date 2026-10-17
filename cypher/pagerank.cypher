// Canonical implementation: app/queries.py
MATCH (candidate:Movie)-[a:ANALYZED_IN]->(:AnalyticsRun {run_id:$run_id})
WHERE a.vote_count >= $min_votes
RETURN candidate.movie_id AS movie_id, candidate.title AS title,
candidate.year AS year, [(candidate)-[:IN_GENRE]->(g:Genre) | g.name] AS genres, a.pagerank AS score, a.vote_count AS support
ORDER BY score DESC, movie_id ASC LIMIT $limit;
