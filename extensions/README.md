# Extensions

External consumers of the core live here.

Current read-only extensions:

- `handoff_export`
- `status_export`
- `return_map_export`

The core does not depend on anything in this directory.

Every extension must consume the stable public core API, remain disposable, and never gain authority over runtime state.
