# Start here

**Cinegraph asks you to pick films you love, then suggests what to watch next and shows why.** No account is needed. Your picks stay in the open browser tab only.

## 1. Run the app

With Docker Desktop running, in the project folder:

```bash
make install
make setup
make docker-run
make download seed analytics
```

Then [open the site](http://localhost:18080). The [API docs (Swagger)](http://localhost:18080/docs) and the [Neo4j Browser](http://localhost:17474) are for technical inspection.

## 2. What is in the menu?

The top menu has two groups.

**Get recommendations**

| Page | What it does |
|---|---|
| Quick picks | You see five films per round; for ten rounds you pick the one you like or skip. No model or key needed. Genre chips filter the results, and **Why?** shows the reason behind each one. |
| Film assistant | The same flow as a conversation. After choosing, type requests such as “only comedies” or “films like Fargo” to change the results. Needs the local model. |

**Explore the data** (these pages do not use your picks)

| Page | What it does |
|---|---|
| Catalog | Search the 9,742 films by title and genre. Click a film to see the films loved by the same people. |
| Top films | The highest rated films in the final year of the data, or the most central films by PageRank. |
| Dataset users | Choose one of the 610 anonymous MovieLens raters to see the films they loved and what the graph recommends for them. |
| Query lab | A question in plain English becomes a checked Cypher query. Unsafe requests are rejected with HTTP 422. |

## 3. Using the film assistant

1. In LM Studio, load **qwen2.5-7b-instruct** and start the local server on port **1234**.
2. Open **Film assistant**. No key is needed. The status line tells you whether the model is ready: green **Local model ready** means you can start; otherwise it says what to open in LM Studio, and **check again** re-checks.
3. Click **Start the conversation**. Click a film card to choose it, or skip the round. Card clicks are handled by the server, so they are fast; only typed messages use the model.
4. Recommendations arrive after ten rounds, or earlier with **Recommend now**. Click a poster to open **Why?**.
5. Type what you want and the assistant changes the results. Examples:
   - “Scarface is my favourite film”: films loved by people who loved Scarface (it does not have to be one of your picks).
   - “only comedies”, “no horror”, “90s”, “before 2000”: filters. When you add a filter, the filters you already set stay as they are.
   - “from all my favourites”: back to all your picks; “all genres” removes the genre filter.

The assistant works in two layers. First the model understands the request and decides which search to run. The server checks that decision and runs one query in Neo4j. Then the model describes the real results in one short sentence. Films always come from the database; the model cannot invent them. If something is unclear, it asks a question and the results on screen stay the same.

If the model is off, you see a clear error; **Try that step again** retries without losing your choices. If you hit the request limit, wait a minute.

If you make the site reachable from other computers, set `REQUIRE_API_KEY=true` in `.env`. The interface then asks for **APP_API_KEY**. Never put that value in a screenshot or in Git.

## 4. Demo and quality checks

| Command | What it does |
|---|---|
| `make lint` | Pylint check (at least 9.5) |
| `make test` | Frontend tests and Python tests against the real Neo4j, with coverage |
| `make demo` | Live HTTP checks against the running services |
| `make assistant-eval` | Runs the conversation against the real model |
| `make llm-eval` | 40-case safety and accuracy evaluation of the query lab |

More detail: [demo runbook](demo-runbook.md), [assistant design](film-assistant.md), [measured results](results.md) and `demo.ipynb`.

`make stop` stops the services but keeps the data. The repository is private; the container image `ghcr.io/canoktayy/cinegraph` is public. No paid LLM or cloud Neo4j account is needed.
