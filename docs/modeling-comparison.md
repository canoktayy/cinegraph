# Modeling comparison: baseline versus implemented graph

The [baseline record](evidence/modeling-baseline.json) contains the exact project brief, local model identity, timestamp and **unedited** generated schema. It is a comparison artifact, not a second contributor or an independent reviewer. The same MovieLens recommendation brief is the starting point for both designs.

| Decision | Generic starting point | Deliberate implementation and effect |
|---|---|---|
| Identity | User/movie entities and their ratings | Source IDs are unique; titles are not identities. Duplicate pairs are resolved with an explicit timestamp policy. |
| Genre representation | Core Movie–Genre example | Genre nodes are canonical; no redundant array is maintained. Filtering uses EXISTS so multiple genres do not multiply rating contributions. |
| Tags | A source field can be omitted or flattened | A TagApplication event preserves the user–movie–tag triple, raw wording and time. Independent binary links would lose event provenance. |
| Similarity | Similarity can be queried without a persistence policy | GDS outputs carry score, support, method and run ID. Support shrinkage and a bounded top-K candidate policy are measurable choices. |
| Community/centrality | Algorithms can be named without lifecycle details | ANALYZED_IN relationships version movie statistics per run. Staging and atomic selection prevent partial overwrites. |
| Time | Ratings can be treated as one undated graph | Historical as_of is explicit. Offline feature edges precede every target label; no production GDS artifact leaks into evaluation. |
| Language interface | A graph query can be generated directly | A typed plan is compiled into one reviewed parameterized template; actual returned paths support the answer. |

These are implementation decisions addressing concrete integrity, cost and reliability problems. More labels alone would not make the model better. In particular, actors/directors are absent from MovieLens small and are not invented to meet a minimum-label count.

The comparison should be read together with the raw baseline; it does not assert the baseline necessarily lacks every good idea in this table. Any overlap is acknowledged rather than rewriting the captured output to make it look weaker.
