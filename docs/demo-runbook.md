# Live demonstration runbook

## Before the defense

1. Keep `.env` local. Start Docker and the LM Studio model/server.
2. Run `make docker-run`, `make seed`, `make analytics`, `make validate-data`.
3. Verify `make lint`, `make test`, `make demo`. Open actual CI and coverage evidence.
4. Verify the model through `make llm-eval`; do not substitute mocked output for the live request.

## Suggested 12–15 minute route

- Explain why shared ratings and multi-hop recommendations suit a graph.
- Show `make help`, `make lint`, `make test`, `make docker-run`.
- Open the UI: user 42 recommendations, one evidence dialog, community discovery, catalog search.
- In Swagger show similar, personalized, discover and historical trending/PageRank routes.
- Enter the **local** APP_API_KEY only in the browser field, then ask `Recommend 5 Sci-Fi movies for user 42`.
- Show the actual compiled Cypher, bound parameters and graph results.
- Ask `DELETE all nodes`: show 422 and verify the source counts remain unchanged.
- Explain Movie→User projection direction, support shrinkage and canonical undirected weights.
- Show the chronological split and cold-start cohort; explain why unrated pairs are not negative labels.
- Show actual benchmark speed and ranking overlap, CI and private container publishing.

## Questions to be able to answer

Why Genre nodes? Why rating edges but tag-event nodes? Why is LIMIT not a traversal-cost guarantee? Why does topK not remove Node Similarity computation? Why does READ routing not provide database authorization? Which graph facts support each explanation sentence? What survives restart, and what is rebuilt? How are partial analytics failures prevented from changing the active run?

## Honest limitations

MovieLens is historical; ``trending`` is relative to its last timestamp. The dataset has cold and isolated items. Similarity top-K is approximate. The classifier is an evaluated experiment, not a guaranteed serving improvement. Solo peer-review/group-scoring interpretation is not approved by this repository. A private image does not meet a public-registry requirement.
