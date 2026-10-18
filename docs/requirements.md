# Requirement-to-evidence map

Source: [instructor specification](https://gist.github.com/bdallard/2ada69b40c3abfe3a7b3f6ed402b4b51). Each row points to where the criterion is met; it is evidence, not a self-awarded grade.

| Rubric item | Points | Evidence |
|---|---:|---|
| docker-compose.yml with ≥3 services | 2 | `neo4j`, `api`, `nginx` in [`docker-compose.yml`](../docker-compose.yml), all with health checks |
| Proper Dockerfile / official image | 2 | Non-root, pinned [`Dockerfile`](../Dockerfile); pinned official Neo4j and Nginx images |
| `.env.example`, no secrets committed | 2 | [`.env.example`](../.env.example); `make setup` writes an untracked `.env`; history scanned: no secret ever committed |
| ≥1 image on a public registry | 2 | [`ghcr.io/canoktayy/cinegraph`](https://github.com/canoktayy/cinegraph/pkgs/container/cinegraph), published by the [Container workflow](../.github/workflows/image.yml) |
| Docker Compose starts cleanly | 1 | `make docker-run` waits until all three services are healthy; CI does the same |
| ≥3 labels, ≥3 relationship types | 3 | 7 labels, 7 relationship types: [graph model](../README.md#graph-model) |
| ≥2 constraints | 2 | 7 uniqueness constraints in `scripts/data.py` (`create_schema`) |
| Appropriate indexes | 2 | Full-text title index and year range index; [PROFILE of an index seek](evidence/profile-index.json) |
| Dataset ingestion script | 2 | `make download seed`: validated, idempotent batch import (`scripts/data.py`) |
| Dataset source documented | 1 | [Data sources](../README.md#data-sources-and-attribution), checksums in `artifacts/reports/data_quality.json` |
| ≥4 endpoints, ≥3 advanced graph queries | 2 | 18 endpoints; similar, recommendations, discovery, trending/PageRank, explanation paths, shortest path |
| Pydantic validation | 2 | `app/models.py`, `app/taste.py`, `app/agent/*` (strict types, bounds, `extra="forbid"`) |
| Swagger `/docs` works | 1 | http://localhost:18080/docs; checked by `tests/integration/test_containers.py` |
| Proper error handling | 1 | 404/422/429/502/503/504 with messages; database errors hide internals (`app/main.py`) |
| Pathfinding/GDS in ≥2 endpoints | 4 | `shortestPath` in `/api/movies/{a}/path/{b}`; GDS Node Similarity in `/similar` and `/recommendations`; Louvain in `/discover`; PageRank in `/trending` |
| Complex pattern matching | 3 | Multi-hop rating → similarity paths, `EXISTS` subqueries, event-node tag traversal (`app/queries.py`) |
| WITH, UNWIND, subqueries, aggregations | 2 | `TASTE_RANKING` (UNWIND), `RECOMMEND` (WITH, aggregation), `DIRECT_SIMILAR` (CALL subqueries) |
| Optimized queries + benchmarks | 5 | Parameters, LIMIT, pagination, precomputed neighbours; [benchmark](results.md#same-workload-query-benchmark) and PROFILE captures |
| GDS projection + ≥2 algorithms | 2 | Cypher projections; Node Similarity, Louvain, PageRank (`app/analytics/build.py`) |
| ML prediction/classification workflow | 3 | Leakage-free classifier on frozen graph features ([ADR 004](adr/004-offline-evaluation.md), `make train`) |
| NL-to-Cypher / agent | 4 | Query lab: templates **and** model-written Cypher; two-layer film assistant (orchestrator + verbaliser) |
| LLM reliability and guardrails | 4 | Keyword guard, typed plans, static Cypher checks, EXPLAIN read-only proof, READ transactions; [52/52 query-lab cases](../artifacts/reports/llm_evaluation.json), [23/23 assistant checks](../artifacts/reports/assistant_evaluation.json) |
| Neo4j graph diagram | 2 | [`schema.svg`](diagrams/schema.svg) with draw.io source |
| System architecture diagram | 2 | [`architecture.svg`](diagrams/architecture.svg) with services, ports and data flows |
| Modeling rationale + anti-genericity appendix | 3 | [Appendix in the README](../README.md#appendix-our-schema-vs-a-generic-ai-generated-schema), [ADRs](adr/), [full comparison](modeling-comparison.md) |
| Complete README + screenshots | 3 | [README](../README.md) with 15 screenshots |
| Demonstration notebook | 2 | [`demo.ipynb`](../demo.ipynb): executed, with graph exploration and charts |
| .pylintrc, pylint ≥9.5, make lint | 2 | Course `.pylintrc`; `make lint` enforces 9.5 (current 9.9) |
| PEP 8 + clean architecture | 1 | Black-formatted; routes, services, repository, queries and agents separated |
| Docstrings | 1 | Every module, class and public function in `app/` and `scripts/` |
| Makefile: commands, functional, documented | 3 | `make help`; [Commands](../README.md#commands) |
| Unit/API/Neo4j tests | 3 | `tests/unit`, `tests/api`, `tests/integration` |
| Container health checks | 2 | `tests/integration/test_containers.py` (FastAPI via Nginx, Swagger, Neo4j Bolt, Docker health) |
| Cypher tests | 2 | `tests/integration/test_graph.py` runs the real queries on Neo4j |
| Coverage ≥60% | 2 | Enforced in `pyproject.toml`; current figure in the README |
| All tests pass | 1 | CI [Quality workflow](../.github/workflows/ci.yml) |
| Lint workflow / Test workflow / Badges | 3 | `lint` and `tests` jobs; badges at the top of the README |
| Code reviews | 1 | Every merged pull request has at least two constructive review comments (self-review, labelled as such) |
| Reverse proxy | 3 | Nginx with rate limits, body size limit and security headers (`nginx/default.conf`); optional API key |
| EXPLAIN / PROFILE demonstration | 2 | [PROFILE captures](evidence/), EXPLAIN in both query-lab modes |
| Branch workflow, .gitignore, merged PRs, commit messages | 7 | Feature branches and pull requests for every change; conventional commit prefixes |
| Balanced contributions | 3 | Solo project: all work is by one student; see [solo scope](solo-scope.md) |

## Required repository artifacts

`docker-compose.yml`, `app/`, `scripts/`, `tests/`, `Makefile`, `.env.example`, `requirements.txt`, `demo.ipynb` and the root `README.md` are all present.
