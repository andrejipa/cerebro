# Extensions

External consumers of the core live here.

Current read-only extensions:

- `handoff_export`
- `impact_export`
- `status_export`
- `return_map_export`

The core does not depend on anything in this directory.

Every extension must consume the stable public core API, remain disposable, and never gain authority over runtime state.

Tracked extension packages currently cover read-only exports and derived analysis only.
Any orchestration that lives outside the runtime must stay outside tracked extension packages and keep consuming only public core interfaces.

Tracked extension packages stay intentionally narrow:

- Python modules for read-only behavior
- Markdown documentation for usage and constraints

Shell wrappers, executable helpers, and other non-Python runtime artifacts do not belong here under the current contract.
