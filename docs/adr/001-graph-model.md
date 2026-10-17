# ADR 001: Keep interactions and tag provenance at their natural granularity

Status: accepted. Scope: MovieLens small, immutable snapshot import.

`User -RATED-> Movie -IN_GENRE-> Genre` is the core. Rating score/time belongs to the user/movie relationship; a separate Rating node would add an unnecessary traversal for this snapshot, which preserves only the latest pair rating. A future append-only history needs RatingEvent instead.

Genres are shared nodes rather than a redundant array property: filters and shared-concept traversals use the same canonical vocabulary. Maintaining both would create two sources of truth.

Tags are not authoritative plot descriptions. `User -APPLIED-> TagApplication -ON_MOVIE-> Movie` and `TagApplication -WITH_TAG-> Tag` preserve who said what about which film, and when. Two independent User–Tag and Movie–Tag edges cannot preserve that three-way event. Raw text remains on the application; normalized keys live on Tag.

IDs are source userId/movieId, not titles or Neo4j internal IDs. Same title does not imply the same film. Five domain labels and five observed relationship types satisfy the heterogeneous model requirement without invented actors or directors.

Consequences: cardinality/rating range checks live in import validation and tests; Community uniqueness constraints do not enforce them automatically. Snapshot replacement requires a clean database, not a partial MERGE that leaves removed rows behind.
