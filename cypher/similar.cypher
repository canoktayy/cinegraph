// Canonical implementation: app/queries.py
MATCH (seed:Movie {movie_id: $movie_id})-[s:SIMILAR_TO]->(candidate:Movie)
WHERE s.run_id = $run_id
  AND ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
RETURN candidate.movie_id AS movie_id, candidate.title AS title,
candidate.year AS year, [(candidate)-[:IN_GENRE]->(g:Genre) | g.name] AS genres, s.score AS score, s.support AS support
ORDER BY score DESC, support DESC, movie_id ASC LIMIT $limit;
