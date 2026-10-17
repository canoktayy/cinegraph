// Canonical implementation: app/queries.py
MATCH (seed:Movie {movie_id: $movie_id})<-[r1:RATED]-(u:User)-[r2:RATED]->(candidate:Movie)
WHERE r1.score >= 4 AND r2.score >= 4 AND seed <> candidate
WITH seed, candidate, count(DISTINCT u) AS common
WHERE common >= $min_common
CALL { WITH seed MATCH (:User)-[r:RATED]->(seed)
       WHERE r.score >= 4 RETURN count(r) AS left_count }
CALL { WITH candidate MATCH (:User)-[r:RATED]->(candidate)
       WHERE r.score >= 4 RETURN count(r) AS right_count }
RETURN candidate.movie_id AS movie_id, candidate.title AS title,
candidate.year AS year, [(candidate)-[:IN_GENRE]->(g:Genre) | g.name] AS genres, common AS support,
toFloat(common)/(left_count+right_count-common)*common/(common+5) AS score
ORDER BY score DESC, support DESC, movie_id ASC LIMIT $limit;
