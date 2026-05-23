# context_vectors (experimental derived track)

Deterministic local vector-search experiment for project context.

This layer indexes bounded textual heads from a target project and returns
ranked query results with trace metadata. It is designed to test whether a
small vector-style layer improves context selection before any heavier
embedding, GraphRAG, or orchestration feature is considered.

## Boundaries

- derived, non-authoritative, opt-in
- read-only over target-project files
- no writes under `.cerebro/`
- no target-project mutation
- no network calls, model downloads, or external services
- no imports from `cli/`
- never calls `import-context`
- never registers or removes sources

## What It Provides

- deterministic local sparse vectors
- bounded project indexing
- query ranking with cosine similarity plus bounded path/heading metadata cues
- optional registered-source awareness through public `StateStore`
- simple evaluation helper for expected-path queries
- trace data describing scanned/skipped files and state availability

The output is advisory evidence for a human. It is not canonical context.
