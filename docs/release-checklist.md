# Release verification

The local suite, data invariants, real GDS jobs, model evaluation and notebook are checked before release. Actual numbers and environment notes are in [results](results.md). Source-controlled reports are measured snapshots, not promised future performance.

- [x] Real MovieLens small import, repeated seed and graph cardinality checks.
- [x] Four principal API use cases, evidence, search, guarded natural-language endpoint.
- [x] Three healthy Docker services.
- [x] Real GDS projection direction and algorithm-job tests.
- [x] Frozen-history supervised experiment and baseline comparisons.
- [x] Unit/API/Cypher integration suite with enforced coverage.
- [x] Teacher lint configuration and ≥9.5 score.
- [x] Actual model, exact query parameters and guardrail evaluation.
- [x] Desktop/mobile UI and evidence dialog checks.
- [x] Executed notebook with real local-model success and rejection.
- [x] Graph/architecture diagrams, editable sources and modeling comparison.
- [x] [GitHub CI passed for the final application commit](https://github.com/canoktayy/moviegraph/actions/runs/39052798282).
- [ ] GitHub Container Registry image verification is recorded in the GitHub release after publication.

Independent human review, instructor solo approval and **public** image visibility are not claimed. Review observations posted by the owner account are self-review, not an external sign-off.
