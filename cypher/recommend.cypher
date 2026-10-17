// Canonical implementation: app/queries.py
MATCH (u:User {user_id: $user_id})-[r:RATED]->(seed:Movie)
WHERE r.score >= 4
WITH u, r, seed ORDER BY r.timestamp DESC, seed.movie_id ASC LIMIT 50
MATCH (seed)-[s:SIMILAR_TO]->(candidate:Movie)
WHERE s.run_id = $run_id AND s.score > 0
  AND NOT EXISTS { MATCH (u)-[:RATED]->(candidate) }
  AND ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
WITH candidate, round(sum(s.score*r.score)/sum(s.score), 8) AS score,
     count(DISTINCT seed) AS supporting_seeds, sum(s.support) AS support
RETURN candidate.movie_id AS movie_id, candidate.title AS title,
candidate.year AS year, [(candidate)-[:IN_GENRE]->(g:Genre) | g.name] AS genres, score, support, supporting_seeds
ORDER BY score DESC, supporting_seeds DESC, movie_id ASC LIMIT $limit;
