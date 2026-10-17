// Canonical implementation: app/queries.py
MATCH (:SystemState {key:'dataset'})
CALL { MATCH (:User)-[rating:RATED]->(:Movie) RETURN avg(rating.score) AS global_mean }
MATCH (candidate:Movie)
WHERE ($genre IS NULL OR EXISTS { MATCH (candidate)-[:IN_GENRE]->(:Genre {name:$genre}) })
  AND ($user_id IS NULL OR NOT EXISTS { MATCH (:User {user_id:$user_id})-[:RATED]->(candidate) })
MATCH (:User)-[r:RATED]->(candidate)
WHERE r.timestamp >= $since AND r.timestamp <= $as_of
WITH candidate, global_mean, count(r) AS votes, avg(r.score) AS mean
WHERE votes >= $min_votes
RETURN candidate.movie_id AS movie_id, candidate.title AS title,
candidate.year AS year, [(candidate)-[:IN_GENRE]->(g:Genre) | g.name] AS genres, votes AS support,
(votes*mean+20*global_mean)/(votes+20) AS score
ORDER BY score DESC, support DESC, movie_id ASC LIMIT $limit;
