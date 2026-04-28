# context_discovery (experimental derived track)

Read-only helper that compares the canonical Cerebro state against the current
target-project filesystem and produces a human-reviewable report describing:

- **candidates_not_registered** — files in the target project that show
  content-level evidence of being context-worthy (project scope, architecture
  decisions, handoffs, current-state markers, project-definition manifests)
  but are not in the registered source set.
- **drift_on_registered_sources** — registered sources whose stored SHA-256
  no longer matches the file on disk, with a short content preview of the
  current head to help the operator decide whether the drift represents a
  meaningful role change.
- **missing_registered_sources** — registered sources that have been deleted
  or renamed away in the target project.

This layer is derived, non-authoritative, opt-in, and observability-only. It
does not mutate `.cerebro/state.json`, does not register sources, does not
enforce anything, and must never be treated as a decision gate. The operator
reads the report and chooses whether to act through the canonical CLI flow
(`cerebro import-context`, `cerebro validate`).

## Boundaries

- reads target-project files through bounded content heads only (line and
  byte caps enforced per file; binary files skipped)
- reads the canonical state only through the public `core.StateStore` API
- never writes under `.cerebro/`
- never modifies the target project
- never imports from `cli/`
- is not part of the authoritative runtime surface
