# Reliability review

This review examined the visitor flow, catalog and research views, request lifetimes, API/model contracts, natural-language compiler, ingestion, graph analytics, historical ML evaluation, Docker setup, notebook execution and GitHub automation. It fixes the concrete failures listed below; passing these checks is not a proof that no future defect can exist.

| Finding | Correction | Verification |
|---|---|---|
| An older list request could overwrite a newer view; navigation was dropped while loading | Independent requests with a generation check; only the current response/error can render | Delayed-success and delayed-error Node regressions; rapid real-browser navigation/search |
| Old film results/errors could append into another or closed dialog; loading text remained after success | Dialog generation/close checks and complete result replacement | Three delayed-response dialog regressions; real detail/evidence interaction |
| Optional poster loading blocked graph startup | Initialize graph statistics independently, bound optional metadata loading, enrich existing cards afterwards | Pending-poster regression; real film-image loading |
| Catalog page offset silently wrapped at 1,000 | Continue within an explicit 10,000-row browsing budget and stop at the bound/end | Node pagination regression, API boundary checks and live last-page request |
| A literal user ID could conflict with context, or several IDs could silently reduce to the first | Reject ambiguous/conflicting identities and malformed signed/decimal/exponent literals before calling the provider | Provider-not-called assertions and typed input tests |
| Genre-containing result counts could expand; role IDs might be mistaken for counts | Bind canonical genre/count phrases and exclude identity-number positions | Comedy, science-fiction and non-English count cases; identity/time-window counterexamples |
| Global/movie queries could fail due to an unrelated unknown user | Resolve only identities used by the selected query | Compiler regressions for global rankings and movie similarity |
| Very large IDs could reach Neo4j's signed integer packing; boolean/fractional IDs could be coerced | Bound every public identity path/body and the model plan; strict JSON ID types | Invalid-path/body tests assert rejection before database access |
| Malformed source identities, duplicate catalog keys, missing link rows or empty text could fail late; numeric tags could lose formatting | Validate the source before writes; preserve text fields and classify absent genres consistently | Fourteen temporary-CSV cases plus re-seeding and graph invariants on the real source |
| Global Jupyter executables could use an incompatible interpreter | Dedicated notebook runner pins the current interpreter and cleans up its kernel | All 18 code cells executed, including model success/rejection and personal-ranking assertions |

## Recorded results

- 154 Python tests, including real Neo4j/Cypher/GDS; 7 Node UI behavioral regressions.
- 81.34% Python statement/branch coverage; teacher-config Pylint 9.89/10.
- The initial five frontend reproduction tests and five agent reproduction cases failed before their corresponding fixes. Their corrected scenarios pass; the final suites include additional boundary cases.
- The real local-model evaluation was repeated: 40/40 cases. Its unchanged JSON content is a deterministic result, not a new claimed dataset/model.
- Real source re-seed, source counts, rating uniqueness and tag-event cardinalities passed. ML/GDS numerical snapshots remain explicitly recorded historical measurements; the graph-building algorithm and offline feature code were not rewritten in this review.
- Desktop/mobile browser and live endpoint checks are recorded in `docs/evidence/review-live-checks.json` and screenshot artifacts.

Run `make test`, `make lint`, `make demo`, `make llm-eval` and `make notebook` to repeat the relevant checks. Node is needed for development tests only; the deployed application still runs without a Node runtime.
