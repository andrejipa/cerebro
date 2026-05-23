# Handoff: Bootstrap Scan Stable Boundary

- State: stable assistive baseline

## Where This Front Stopped

- `bootstrap-scan` remains an assistive-only bootstrap helper outside runtime authority.
- It now rejects non-positive shortlist limits explicitly.
- It reports heuristic basis, total matched candidates, and returned shortlist size separately.
- It ignores common noisy local directories such as `node_modules`, `livros_fontes`, `venv`, and `env`.
- It still classifies candidates by project-tree paths and filenames only.

## What Is Already Safe

- it does not create or modify `.cerebro`
- it does not import `core`
- it does not register `sources`
- it does not call `import-context`
- it does not read file contents for classification
- it does not claim to define canonical context

## What Was Validated

- synthetic noisy-tree tests cover false memory signals, historical/acervo paths, and local environment directories
- real-project validation showed that the shortlist reduces manual pointing while keeping final source choice human
- architecture tests now lock the assistive-only wording and the no-authority boundary

## Why This Front Stops Here

- any further improvement that depends on reading file contents, semantic ranking, or identifying the "right" entrypoint would open new semantics
- any automatic source registration or bootstrap execution would violate the runtime boundary

## Decision Still Required Before Reopening

- explicit approval to open a true external-analysis layer for bootstrap support

## First Exact Action After Release

- write one concrete repeated unmet bootstrap use case that cannot be satisfied by path-and-filename shortlist assistance alone
