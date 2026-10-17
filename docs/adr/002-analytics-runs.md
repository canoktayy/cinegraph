# ADR 002: Version derived relationships and activate runs atomically

Status: accepted.

Node Similarity uses Movie→User projections of ratings ≥4. Support ≥3 and a shrink factor `support/(support+5)` temper low-support Jaccard. GDS computes 40 raw candidates per movie, then the application keeps up to 20 shrunk neighbors. This is a bounded approximation, not guaranteed exhaustive shrunk top-K. `topK` does not remove the cost of all GDS pair comparisons.

For Louvain/PageRank, canonical movie pairs merge the two directed top-K lists with max weight and are projected once in each direction. Reciprocal storage must not double the weight. Isolated catalog movies remain represented, so total Louvain communities includes many singleton isolates; the report distinguishes connected coverage.

The guide's movie-property alternative is replaced with versioned `Movie -ANALYZED_IN-> AnalyticsRun` relationships containing community, PageRank, vote count and Bayesian mean. A `SystemState` node atomically selects the active run. New edges and memberships stage separately; failure does not overwrite the serving run. An API repository pins snapshot metadata for the lifetime of one request.

Internal IDs appear only inside temporary projections. Exported results use movie_id. Projections are dropped after jobs; persistent source/derived edges remain. Run manifests record source hash, cutoff, parameters and source-code hash. Louvain labels are run-specific and may vary between environments.

Neo4j 5.26.0/GDS 2.13.2 is the tested pair. Cypher projection uses the legacy `gds.graph.project.cypher` API supported by this pinned version. Migration is required before upgrading to an incompatible GDS release.
