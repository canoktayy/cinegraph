# Live demonstration runbook

## Before the defense

1. Keep `.env` local. Start Docker and the LM Studio model/server.
2. Run `make docker-run`, `make seed`, `make analytics`, `make validate-data`.
3. Verify `make lint`, `make test`, `make demo`. Open actual CI and coverage evidence.
4. Verify the local model through `make assistant-eval` and `make llm-eval`; do not substitute mocked output for live requests.

## Suggested 12–15 minute route

- Explain why shared ratings and multi-hop recommendations suit a graph.
- Show `make help`, `make lint`, `make test`, `make docker-run`.
- Open Home and explain the two ways to get recommendations. In **Film assistant**, choose a few films (card clicks never call the model), open a “Why?” reason, then type `Scarface is my favourite film`, `only 80s and 90s please` and `no horror please`. Point at the chips (*Like Scarface*, *1980 to 1999*, *No Horror*) and open *What did the assistant decide?* to show the orchestrator decision and which layer wrote the reply. Type `something like that one movie` to show a clarifying question that leaves the results unchanged.
- Show that **Quick picks** works without the model, including genre chips and “Why?”. Then open **Dataset users** for rater 42 (both methods and the path evidence), **Catalog** for title search and “Fans also liked”, and **Top films** for the rating/PageRank toggle.
- In Swagger show similar, personalized, discover and historical trending/PageRank routes.
- In **Query lab**, point at the green “Local model ready” status, then ask `Recommend 5 Sci-Fi movies for user 42`. No key is needed locally; explain that `REQUIRE_API_KEY=true` turns key protection on for an exposed deployment.
- Show the actual compiled Cypher, bound parameters and graph results.
- Click “Try a blocked request” (`DELETE all nodes`): show the red 422 guardrail stage and verify the source counts remain unchanged.
- Explain Movie→User projection direction, support shrinkage and canonical undirected weights.
- Show the chronological split and cold-start cohort; explain why unrated pairs are not negative labels.
- Show actual benchmark speed and ranking overlap, CI and the public container image.

## Questions to be able to answer

Why Genre nodes? Why rating edges but tag-event nodes? Why is LIMIT not a traversal-cost guarantee? Why does topK not remove Node Similarity computation? Why does READ routing not provide database authorization? Which graph facts support each explanation sentence? What survives restart, and what is rebuilt? How are partial analytics failures prevented from changing the active run?

## Honest limitations

MovieLens is historical; ``trending`` is relative to its last timestamp. The dataset has cold and isolated items. Similarity top-K is approximate. The classifier is an evaluated experiment, not a guaranteed serving improvement. Solo peer-review/group-scoring interpretation is not approved by this repository. A private image does not meet a public-registry requirement.
