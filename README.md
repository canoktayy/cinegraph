<div align="center">

# 🎬 MovieGraph

### Pick films you love. See what to watch next — and exactly why.

An explainable movie recommender built on a **Neo4j graph** of 100,836 real MovieLens ratings,
with **Graph Data Science** algorithms, a guarded **natural-language → Cypher** lab and a **local-LLM film assistant**.

[![Quality](https://github.com/canoktayy/moviegraph/actions/workflows/ci.yml/badge.svg)](https://github.com/canoktayy/moviegraph/actions/workflows/ci.yml)
[![Container](https://github.com/canoktayy/moviegraph/actions/workflows/image.yml/badge.svg)](https://github.com/canoktayy/moviegraph/actions/workflows/image.yml)
![Coverage](docs/evidence/coverage.svg)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5.26%20%2B%20GDS%202.13-018bff?logo=neo4j&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.143-009688?logo=fastapi&logoColor=white)

**Can Oktay** · Student no. B00818187 · AIDAMS 3A — Graph Databases
Project 4 · *Movie Recommender in Production* (Level 2)

<img src="docs/screenshots/ui-home.jpg" alt="MovieGraph home page" width="900">

</div>

---

## Contents

1. [What it does](#what-it-does)
2. [Tour of the application](#tour-of-the-application)
3. [Quick start](#quick-start)
4. [Architecture](#architecture)
5. [Graph model](#graph-model)
6. [How recommendations are computed](#how-recommendations-are-computed)
7. [Language-model components and guardrails](#language-model-components-and-guardrails)
8. [API reference](#api-reference)
9. [Quality, evaluation and performance](#quality-evaluation-and-performance)
10. [Commands](#commands)
11. [Repository layout](#repository-layout)
12. [Data sources and attribution](#data-sources-and-attribution)
13. [Limitations](#limitations)

---

## What it does

| | Feature | How it works |
|---|---|---|
| 🎯 | **Quick picks** | Ten rounds of five well-known films — click or press <kbd>1</kbd>–<kbd>5</kbd>. Pick favourites, get matches, filter by genre. No account, no model. |
| 💬 | **Film assistant** | The same flow as a conversation. Say *“Bana sadece komedi öner”* or *“more like Fargo”* — a local LLM interprets the request, the graph returns the films. |
| 🔍 | **“Why this film?”** | Every recommendation shows the picks it is linked to and how many raters loved both films. |
| 📚 | **Catalog** | Full-text search over 9,742 films, genre filter, and “fans also liked” for any film. |
| 🏆 | **Top films** | Bayesian-rated films from the snapshot’s final year, or the most central films by **PageRank**. |
| 👥 | **Dataset users** | See what any of the 610 MovieLens raters loved, then their item-CF and **Louvain** community recommendations with path-level evidence. |
| 🧪 | **Query lab** | A question in plain English becomes a typed plan → a reviewed Cypher template → real rows. Unsafe requests are rejected with HTTP 422. |

**Design principle:** the language model never invents films, scores or explanations. All titles, counts and paths come from Neo4j and are shown with their provenance.

---

## Tour of the application

### 1 · Quick picks — no setup required

Five films per round, ten rounds. Unpicked films are **not** treated as dislikes.

<img src="docs/screenshots/ui-picks-round.jpg" alt="Quick picks round" width="900">

Results are ranked by graph affinity to your picks. Genre chips re-run the query in Neo4j.

<img src="docs/screenshots/ui-picks-results.jpg" alt="Quick picks results" width="900">

### 2 · A visible reason for every match

<table>
<tr>
<td width="50%"><img src="docs/screenshots/ui-why.jpg" alt="Why this film dialog"></td>
<td width="50%"><img src="docs/screenshots/ui-similar.jpg" alt="Fans also liked dialog"></td>
</tr>
<tr>
<td align="center"><sub>Which of your picks lead to the film, and how many raters loved both</sub></td>
<td align="center"><sub>Any catalog film: neighbours by shared positive raters</sub></td>
</tr>
</table>

### 3 · Film assistant — conversation on top of the graph

The deterministic controller runs the ten rounds itself; the local model is only called for free-text requests, which it turns into a validated `AssistantPlan` (tool, genre, reference film).

<img src="docs/screenshots/ui-assistant-comedy.jpg" alt="Film assistant filtering to comedies" width="900">

### 4 · Explore the data

<table>
<tr>
<td width="50%"><img src="docs/screenshots/ui-top.jpg" alt="Top films ranking"></td>
<td width="50%"><img src="docs/screenshots/ui-users.jpg" alt="Dataset user recommendations"></td>
</tr>
<tr>
<td align="center"><sub>Top films: Bayesian rating or PageRank centrality</sub></td>
<td align="center"><sub>Recommendations for MovieLens rater 42 (item CF / Louvain)</sub></td>
</tr>
</table>

### 5 · Query lab — natural language to safe Cypher

<table>
<tr>
<td width="50%"><img src="docs/screenshots/ui-lab.jpg" alt="Successful natural-language query"></td>
<td width="50%"><img src="docs/screenshots/ui-lab-blocked.jpg" alt="Rejected unsafe query"></td>
</tr>
<tr>
<td align="center"><sub>Question → model plan → checked template → Neo4j rows</sub></td>
<td align="center"><sub>“DELETE all nodes” is rejected before any database call</sub></td>
</tr>
</table>

### 6 · Mobile

<p align="center">
<img src="docs/screenshots/ui-mobile-home.jpg" alt="Mobile home" width="260">
<img src="docs/screenshots/ui-mobile-picks.jpg" alt="Mobile quick picks" width="260">
<img src="docs/screenshots/ui-mobile-menu.jpg" alt="Mobile menu" width="260">
</p>

---

## Quick start

**Requirements:** Python 3.12+, Docker with Compose v2, Git, Node.js 20+ (frontend tests only). Allow 4–6 GB of Docker memory.

```bash
git clone https://github.com/canoktayy/moviegraph.git
cd moviegraph
make install        # virtualenv + pinned dependencies
make setup          # creates an untracked .env with unique secrets (never printed)
make docker-run     # Neo4j + GDS, FastAPI, Nginx — waits until healthy
make download seed  # MovieLens small: download, validate, import
make analytics      # GDS similarity, Louvain, PageRank → versioned run
make demo           # live HTTP smoke checks
```

| Service | URL |
|---|---|
| **MovieGraph** | http://localhost:18080 |
| Swagger / OpenAPI | http://localhost:18080/docs |
| Neo4j Browser | http://localhost:17474 (Bolt `17687`, credentials in your `.env`) |

**Optional local model** (Film assistant and Query lab): load `qwen2.5-7b-instruct` in [LM Studio](https://lmstudio.ai) and start its server on port `1234`. No key is needed: the Film assistant and Query lab show a live status (“Local model ready” or how to start it). Everything else works without a model.

A Turkish walkthrough is available in [docs/START_HERE_TR.md](docs/START_HERE_TR.md).

---

## Architecture

![System architecture](docs/diagrams/architecture.svg)

```mermaid
flowchart LR
    B[Browser] -->|HTTP :18080| N[Nginx<br/>rate & size limits]
    N -->|HTTP :8000| A[FastAPI<br/>contracts · policy · compiler]
    A -->|Bolt, parameterised<br/>read-only templates| G[(Neo4j 5.26<br/>+ GDS 2.13)]
    A -->|JSON-schema plan| L[LM Studio<br/>qwen2.5-7b · host :1234]
    J[Batch CLI<br/>ETL · GDS · ML · benchmarks] -->|trusted writes| G
```

| Component | Responsibility |
|---|---|
| **Nginx 1.28** | Single entry point on `18080`; 16 KB body limit, per-IP budgets for model endpoints, timeouts, security headers |
| **FastAPI** | Pydantic contracts, recommendation policy, plan compiler, static frontend; one driver per process, bounded query time |
| **Neo4j 5.26 + GDS 2.13** | Source graph, 7 uniqueness constraints, full-text and range indexes, versioned analytical output |
| **Batch CLI** | Source validation and idempotent import, GDS jobs with atomic activation, offline ML experiment, benchmarks |
| **LM Studio (optional)** | Local, OpenAI-compatible model for intent planning only |
| **Frontend** | Dependency-free HTML/CSS/JS; hash-routed screens, stale-request protection, responsive down to 360 px |

The API never runs GDS per request: it reads the results of the active `AnalyticsRun`. Readiness (`/health/ready`) requires a Neo4j round trip **and** a seeded snapshot; liveness lets an empty install start before import. All three containers have health checks.

---

## Graph model

![Graph schema](docs/diagrams/schema.svg)

| Node | Key properties | Meaning |
|---|---|---|
| `User` | `user_id` | Anonymous MovieLens rater |
| `Movie` | `movie_id`, `title`, `year`, `imdb_id`, `tmdb_id` | Catalog film (title is not an identity) |
| `Genre` | `name` | Canonical genre vocabulary |
| `Tag` | `key` | Normalised tag concept |
| `TagApplication` | `application_id`, `raw_text`, `timestamp` | One user tagging one film at one time |
| `AnalyticsRun` | `run_id`, `cutoff`, `gds_version`, `status` | A versioned GDS computation |
| `SystemState` | `data_version`, `as_of`, `active_run_id` | Snapshot identity and the active run |

| Relationship | Properties | Kind |
|---|---|---|
| `(:User)-[:RATED]->(:Movie)` | `score`, `timestamp` | observed |
| `(:Movie)-[:IN_GENRE]->(:Genre)` | — | observed |
| `(:User)-[:APPLIED]->(:TagApplication)-[:ON_MOVIE]->(:Movie)` | — | observed |
| `(:TagApplication)-[:WITH_TAG]->(:Tag)` | — | observed |
| `(:Movie)-[:SIMILAR_TO]->(:Movie)` | `score`, `support`, `run_id` | derived (GDS) |
| `(:Movie)-[:ANALYZED_IN]->(:AnalyticsRun)` | `community_id`, `pagerank`, `vote_count`, `bayesian_rating` | derived (GDS) |

**Key modelling decisions**

- **Genres are nodes**, not a list property: filters and traversals share one canonical vocabulary, and `EXISTS { … }` filtering cannot multiply rating contributions. Keeping both would create two sources of truth.
- **Ratings are relationships**: score and time describe a user–film pair; a `Rating` node would add a hop for no benefit in a latest-rating snapshot.
- **Tag applications are event nodes**: two independent `User–Tag` and `Movie–Tag` edges would lose *who tagged which film, when*.
- **Derived data is versioned**: `SIMILAR_TO` and `ANALYZED_IN` carry a `run_id`; a new run is staged and activated atomically, so a failed job never changes what the API serves.
- **No invented entities**: MovieLens small has no actors or directors, so none are modelled.

Full rationale: [ADR 001 – graph model](docs/adr/001-graph-model.md) · [ADR 002 – versioned analytics](docs/adr/002-analytics-runs.md) · [anti-genericity comparison with an AI-generated baseline](docs/modeling-comparison.md) · editable [draw.io sources](docs/diagrams/).

---

## How recommendations are computed

```mermaid
flowchart LR
    R[RATED ≥ 4★] --> P[GDS projection<br/>Movie → User]
    P --> S[Node Similarity<br/>Jaccard, top-40]
    S --> K[Support shrinkage<br/>× support / support+5<br/>keep top-20, support ≥ 3]
    K --> E[(SIMILAR_TO<br/>run-versioned)]
    E --> U[Undirected weighted<br/>movie graph]
    U --> LV[Louvain communities]
    U --> PR[PageRank centrality]
```

| Use case | Method | Endpoint |
|---|---|---|
| Similar films | Precomputed shrunk-Jaccard neighbours; direct traversal fallback | `GET /api/movies/{id}/similar` |
| Your picks (visitor) | Mean similarity to selected seeds, picks excluded, reasons attached | `POST /api/taste/recommendations` |
| Dataset rater | Item CF over the latest 50 positive ratings, already-rated films excluded; labelled Bayesian fallback | `GET /api/users/{id}/recommendations` |
| Community discovery | Films from the rater’s 3 dominant Louvain communities | `GET /api/users/{id}/discover` |
| Top films | Bayesian average over the last 365 days of data, or PageRank | `GET /api/movies/trending` |
| Explanation | Exact `User-RATED->Movie-SIMILAR_TO->Movie` paths and contributions | `GET /api/users/{u}/recommendations/{m}/explanation` |

Scores are graph affinities, not predicted stars or probabilities. “Trending” is relative to the snapshot’s last timestamp (September 2018), not today.

**Machine learning.** An offline experiment ([ADR 004](docs/adr/004-offline-evaluation.md)) predicts whether a future observed rating will be ≥ 4★ from graph features frozen at an earlier cutoff (chronological 60/20/10/10 split, no leakage, unrated pairs never used as negatives).

---

## Language-model components and guardrails

Both components use a **local** model through an OpenAI-compatible API with JSON-schema output, temperature 0 and at most one format repair.

### Query lab — constrained NL → Cypher

```mermaid
flowchart LR
    Q[Question] --> G1{Keyword guard<br/>DELETE · DROP · APOC · password…}
    G1 -->|unsafe| X[422]
    G1 --> M[LLM → typed QueryPlan<br/>6 allowed intents]
    M --> V{Pydantic + bound<br/>explicit IDs/genre/limit}
    V -->|invalid| Y[502 / 422]
    V --> C[Compiler: exact reviewed<br/>Cypher template + parameters]
    C --> E[EXPLAIN] --> R[Bounded READ execution]
```

- The model outputs a **plan**, never Cypher. Templates are matched by exact string against an allow-list.
- User and movie IDs, genres and result counts written in the question are **bound from the text**; the model cannot change them.
- Unknown identities → 404, unsafe or unsupported requests → 422, malformed model output → 502, model offline/timeout → 503/504, budget exceeded → 429.
- The response exposes the plan, compiled Cypher, bound parameters, rows and a trace ID.

### Film assistant

- Card clicks (start, pick, skip, back) are handled **deterministically** by the server; the model is called only for free text.
- The model may choose one of two read-only tools (`graph_affinity`, `similar_movies`), a canonical genre and a reference film **from the visitor’s own picks**. Every value is validated server-side; picks are re-checked against the seeded rounds so a client cannot forge preferences.
- Mutation requests and unsupported data (actors, plots) are rejected before the model is called.

Details: [ADR 003 – language safety](docs/adr/003-language-safety.md) · [assistant design](docs/film-assistant.md).

---

## API reference

Interactive documentation: **http://localhost:18080/docs**

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` · `/health/ready` | Liveness / readiness (DB round trip + seeded data) |
| GET | `/api/system/status` | Real graph counts and snapshot metadata |
| GET | `/api/genres` | Canonical genres |
| GET | `/api/movies?q=&genre=&year=&limit=&offset=` | Full-text catalog search with pagination |
| GET | `/api/movies/{id}/similar` | Similar films (GDS) |
| GET | `/api/movies/trending?metric=rating\|pagerank` | Historical top films / centrality |
| GET | `/api/users/{id}/favorites` | The rater’s own 4★+ ratings (context for their recommendations) |
| GET | `/api/users/{id}/recommendations?genre=` | Item-CF recommendations |
| GET | `/api/users/{id}/discover` | Louvain community discovery |
| GET | `/api/users/{u}/recommendations/{m}/explanation` | Path evidence |
| GET | `/api/taste/rounds?seed=` | Ten seeded rounds of five films |
| POST | `/api/taste/recommendations` | Recommendations from visitor picks |
| POST | `/api/ask` 🔑 | Natural-language query lab |
| POST | `/api/assistant/turn` 🔑 | Film assistant turn |

🔑 model endpoints: always rate-limited by Nginx and the API; they additionally require the `X-API-Key` header when the server runs with `REQUIRE_API_KEY=true` (off by default because every port binds to `127.0.0.1`). `GET /api/model/status` tells the interface whether LM Studio answers.

```bash
curl 'http://localhost:18080/api/movies/1/similar?limit=5'
curl 'http://localhost:18080/api/users/42/recommendations?genre=Sci-Fi&limit=10'
curl -X POST 'http://localhost:18080/api/taste/recommendations' \
  -H 'Content-Type: application/json' -d '{"movie_ids":[1,260,296],"limit":8}'
curl -X POST 'http://localhost:18080/api/ask' -H 'Content-Type: application/json' \
  -d '{"question":"Recommend 5 Sci-Fi movies for user 42"}'
```

---

## Quality, evaluation and performance

| Check | Result |
|---|---|
| Python tests (unit, API, real Neo4j/Cypher/GDS integration) | **190 passed** |
| Frontend behavioural tests (Node test runner) | **21 passed** |
| Statement + branch coverage (enforced ≥ 60 %) | **83.8 %** |
| Pylint with the course `.pylintrc` (enforced ≥ 9.5) | **9.90 / 10** |
| Query-lab evaluation: 20 live model cases, 10 unsafe, 5 unsupported, 5 injected faults | **40 / 40** |
| Assistant evaluation: real model + real Neo4j, 10 rounds, Turkish genre filter, tool switch, guards | **17 / 17** |

CI ([Quality workflow](.github/workflows/ci.yml)) starts the real three-service stack, imports MovieLens twice to prove idempotency, runs GDS and the whole suite. Integration tests fail loudly when the database is missing instead of skipping.

**Graph analytics (actual run):** 48,580 positive-rating edges projected · 33,679 `SIMILAR_TO` edges · 2,437 connected films in 11 non-trivial Louvain communities · GDS jobs in 4.9 s.

**Offline classifier (test set, 8,598 future ratings):**

| Model | Average precision | ROC-AUC | F1 |
|---|---:|---:|---:|
| Majority prior | 0.480 | 0.500 | 0.649 |
| Historical movie mean | 0.604 | 0.658 | 0.662 |
| **Graph-feature logistic regression** | **0.617** | **0.669** | **0.677** |

**Query performance** (same 30 films, after warm-up — see [`profile-*.json`](docs/evidence/) for `PROFILE` plans):

| Method | p50 | p95 |
|---|---:|---:|
| Direct graph traversal | 21.8 ms | 42.5 ms |
| Precomputed GDS neighbours | **2.6 ms** | **4.2 ms** |

Mean top-10 overlap between the two: 0.97. More detail in [docs/results.md](docs/results.md).

**Page weight:** Nginx gzip plus compact poster metadata (`[file, tmdb_id]` per film) cut the first load from about **3.1 MB to 0.32 MB**. Posters are requested at the size each slot needs (92, 185 or 342 px wide), and static files are revalidated on every visit so a new release is never mixed with stale CSS or JS.

---

## Commands

| Command | Purpose |
|---|---|
| `make help` | List every target |
| `make install` / `make setup` | Virtualenv and dependencies / local secrets |
| `make docker-run` / `make stop` | Start (and wait for health) / stop the stack, keeping data |
| `make download` `make profile` `make seed` `make validate-data` | Data acquisition, quality report, import, graph invariants |
| `make analytics` | GDS Node Similarity, Louvain, PageRank with atomic run activation |
| `make test` | Frontend + Python/HTTP/Neo4j/GDS tests with coverage |
| `make test-unit` / `make test-ui` | Tests without a database / frontend only |
| `make lint` / `make format` | Pylint gate / Black |
| `make train` | Offline ML experiment |
| `make benchmark` | Latency and `PROFILE` capture |
| `make llm-eval` / `make assistant-eval` | Real-model evaluations |
| `make notebook` / `make demo` | Execute `demo.ipynb` / HTTP smoke checks |
| `make clean` | Remove caches only |

---

## Repository layout

```
moviegraph/
├── app/
│   ├── main.py            # FastAPI routes, auth, budgets, error handling
│   ├── models.py          # Pydantic contracts
│   ├── queries.py         # Reviewed Cypher templates
│   ├── repository.py      # Parameterised data access
│   ├── services.py        # Recommendation policy and explanations
│   ├── taste.py           # Visitor quick-pick rounds and ranking
│   ├── agent/             # Query lab (plans, client, compiler, workflow) + film assistant
│   ├── analytics/build.py # GDS jobs with versioned, atomic runs
│   ├── ml/experiment.py   # Leakage-free offline classifier
│   └── static/            # Frontend: index.html, style.css, app.js, assistant.js
├── scripts/               # ETL, setup, benchmarks, evaluations, smoke tests
├── tests/                 # unit · api · integration (real Neo4j) · frontend
├── cypher/                # Readable copies of the main queries
├── docs/                  # ADRs, diagrams, screenshots, evidence, guides
├── nginx/default.conf     # Reverse proxy
├── docker-compose.yml     # neo4j · api · nginx
├── demo.ipynb             # Executed demonstration notebook
└── Makefile
```

Further reading: [requirement-to-evidence map](docs/requirements.md) · [demo runbook](docs/demo-runbook.md) · [reliability review](docs/review.md) · [project guide (PDF, Turkish)](proje_guide.pdf).

---

## Data sources and attribution

- **Ratings:** [GroupLens MovieLens small](https://grouplens.org/datasets/movielens/) — 610 users, 9,742 movies, 100,836 ratings, 3,683 tag applications (1996–2018). F. Maxwell Harper and Joseph A. Konstan (2015), *The MovieLens Datasets: History and Context*, [DOI 10.1145/2827872](https://doi.org/10.1145/2827872). Used under the [MovieLens terms](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html); no endorsement implied.
- **Posters:** 9,586 references joined on **both** TMDB and IMDb IDs from the [Full TMDB Movies Dataset](https://www.kaggle.com/datasets/asaniczka/tmdb-movies-dataset-2023-930k-movies); only URLs are stored. Images remain with their rights holders. This product uses TMDB data but is not endorsed or certified by TMDB. Posters are never used for ranking.

Import validation rejects invalid scores, missing foreign keys and conflicting identities; per-file SHA-256 hashes are recorded in [`data_quality.json`](artifacts/reports/data_quality.json).

---

## Limitations

- MovieLens is a historical, selection-biased research sample; “top films” are not live trends.
- Similarity uses a bounded top-K approximation; many catalog films have too few ratings to be connected.
- Visitor picks live only in the browser tab and are never written to the graph.
- The stack is built for one computer: ports bind to `127.0.0.1`. Before exposing it, set `REQUIRE_API_KEY=true` (the interface then asks for the key) and put real authentication in front.
- The container image is published to GitHub Container Registry as **private** by the owner’s choice.

---

<div align="center">
<sub>Built by <b>Can Oktay</b> · Neo4j × MovieLens · AIDAMS 3A</sub>
</div>
