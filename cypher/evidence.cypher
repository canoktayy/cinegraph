// Canonical implementation: app/queries.py
MATCH (u:User {user_id:$user_id})-[r:RATED]->(seed:Movie)
WHERE r.score >= 4
WITH u, r, seed ORDER BY r.timestamp DESC, seed.movie_id ASC LIMIT 50
MATCH (seed)-[s:SIMILAR_TO]->(target:Movie {movie_id:$movie_id})
WHERE s.run_id = $run_id AND s.score > 0
RETURN seed.movie_id AS seed_id, seed.title AS seed_title,
       r.score AS source_rating, r.timestamp AS rating_timestamp,
       s.score AS similarity, s.support AS support,
       s.score*r.score AS numerator
ORDER BY numerator DESC, seed_id ASC;
