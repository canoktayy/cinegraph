# ADR 003: Compile a typed query plan rather than sanitize arbitrary model Cypher

Status: accepted.

The local Qwen model outputs a Pydantic QueryPlan, not executable code. Only six intents exist; unsupported questions fail closed. The compiler resolves real identities and canonical genres, selects an exact reviewed Cypher template and binds parameters. Unknown fields, large limits and guessed identities are rejected. At most one output-format repair is attempted. The trace exposes the compiled Cypher and actual rows.

EXPLAIN catches syntax/plan failures but is not a security sandbox. READ routing is not a database privilege boundary. In Neo4j Community this application relies on its fixed query language, network isolation (every port binds to 127.0.0.1) and per-client budgets on the costly model endpoints, with an optional key (`REQUIRE_API_KEY=true`) for any exposed deployment; it does not pretend to have Enterprise fine-grained read roles. The importer and analytical job path have trusted database management access; no HTTP route accepts free Cypher, CALL/APOC, file import or mutations.

Observed ratings are distinct from derived similarity and generated language. Recommendation explanations are deterministically rendered from actual paths; there is no second unconstrained model that can invent a plot, director or preference. When key protection is enabled, the key stays in .env or in a user's current browser tab, never in responses or checked-in screenshots.

This is constrained NL→plan→Cypher. It satisfies the engineering intent of validated NL-to-Cypher; if the instructor requires raw model-written Cypher specifically, that interpretation needs clarification. A genuine LangGraph multi-step agent is not claimed for this Level 2 project.
