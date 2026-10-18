# Recorded verification results

Measured locally on 18 October 2026 after the interface redesign. These are observed results, not promised future accuracy or latency. Full inputs and methodology are in the JSON reports and ADRs.

## Quality gates

- **207 Python tests and 21 frontend behavioural tests passed**, including real Neo4j, Cypher, projection and GDS algorithm jobs.
- **84.81% combined Python statement/branch coverage**, minimum enforced: 60%.
- **Pylint 9.90/10**, teacher configuration, minimum enforced: 9.5. Black reports no changes.
- **40/40 query-lab reliability cases passed**. The 20 supported questions check intent, exact entity/filter/budget parameters and returned genre membership. Other cases distinguish scope/guardrail rejection from controlled malformed-provider fault injection.
- **23/23 film-assistant checks passed** with the real local model and real Neo4j: ten quiz rounds, then ten typed requests through the two model layers (orchestrator and verbaliser), including “Scarface en sevdiğim film”, decade and exclusion filters in English and Turkish, a switch back to all favourites, an unknown Turkish title and a vague request, plus two scope guards and unchanged source counts.
- **14/14 live HTTP smoke checks passed** against the rebuilt container stack.
- First-load transfer through Nginx: about 316 KB (HTML 7 KB, app.js 11.5 KB, poster metadata 298 KB gzip), down from about 3.1 MB. Posters display in Chrome and WebKit (Safari) on every screen.
- The Film assistant and Query lab work without any key on a local install, in Chrome and WebKit. With the model server stopped, the status line explains how to start it, card rounds still work, and a typed request returns a clear 503 with retry.
- Every notebook cell executed; real model HTTP 200, exact Sci-Fi filtering and unsafe-operation HTTP 422 are assertions.
- The interface was driven end to end in Chrome at 1440 px and 390 px (all seven screens, dialogs, the assistant and the query lab). No screen has horizontal overflow at 375 px. Screenshots are in `docs/screenshots/`; no key appears in them.

## GDS on the actual source snapshot

- Neo4j 5.26.0 / GDS 2.13.2.
- 48,580 positive rating edges in the Movie→User projection.
- 33,679 supported, shrunk, per-source top-20 similarity edges.
- 2,437 connected movies; 11 non-isolated Louvain communities.
- 7,316 total communities includes isolated singleton catalog movies. The difference is important: it does not mean thousands of meaningful taste groups.
- GDS job time in this run: 4.891 seconds; memory estimate recorded in `gds.json`.
- Active run: `gds-246d37dafdab7423`. Community IDs are not stable semantic labels.

## Frozen-history supervised experiment

| Model | Test average precision | ROC-AUC | F1 |
|---|---:|---:|---:|
| Dummy prior | 0.4801 | 0.5000 | 0.6488 |
| Historical movie mean | 0.6036 | 0.6581 | 0.6618 |
| Graph-feature logistic model | 0.6165 | 0.6689 | 0.6773 |

Test examples: 8,598. Positive rate: 0.480. Cold-user test examples: 8,379; cold-movie test examples: 3,316. This heavy global-time cold-start cohort prevents interpreting one average as personalized quality for every user. Ratings not observed are not negative classification labels. Production GDS is not read by the offline feature builder.

Full-catalog item-CF Recall@10: 0.0503; NDCG@10: 0.2277. Bayesian baseline Recall@10: 0.0500. These modest ranking numbers are reported rather than hidden. The supervised model beats the recorded classification baselines but is not automatically promoted to serving.

## Same-workload query benchmark

| Method | p50 ms | p95 ms |
|---|---:|---:|
| Direct graph traversal | 21.786 | 42.526 |
| Versioned precomputed lookup | 2.614 | 4.234 |

Thirty identical source-movie IDs, five warm-up calls, sequential local-client timings. Mean top-10 overlap: 0.973. The precomputed raw-candidate cap is approximate, so faster does not imply perfectly equivalent ranking. PROFILE captures are separate from normal latency timing. This is not a concurrency/SLA test.

## Boundaries that remain external

The owner requested a private repository and private image; the public-registry rubric criterion is not claimed. Independent human peer review and solo-submission approval require the instructor/another person. No grade, external approval, collaboration balance or human review is fabricated.

## New-visitor taste discovery

Ten rounds of five distinct supported films; skip/back states; selected-film exclusion; exact sum-of-similarities normalization; canonical genre filtering; actual graph reasons; no new source users or ratings. HTTP contract and real graph tests exercise the visitor path. This is functional validation, not an independently measured accuracy/user-study claim. Film display metadata has 9,586 identity-matched references of 9,742 catalog movies; both TMDB and IMDb IDs must match. Source SHA-256 and counts are in `artifacts/reports/posters.json`.

The review added delayed-response UI regressions, strict graph-identity bounds, natural-language context/count cases, malformed CSV cases and full-snapshot catalog pagination. All 18 notebook code cells were executed, including the new visitor path and exact graph-affinity assertions. See [review report](review.md).
