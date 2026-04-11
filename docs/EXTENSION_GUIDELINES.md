# Extension Guidelines

This document defines the permanent contract for external extensions.

Extensions are consumers. The core remains the only authority over state, runtime files, invariants, and validation semantics.

## Mandatory Enforcement Rules

An extension is invalid if it violates any rule below.

1. Extensions never write inside `.cerebro/`.
2. Extensions never modify `state.json`.
3. Extensions never modify `session.local.json`.
4. Extensions never read runtime JSON directly.
5. Extensions use only the public `core` API.
6. Extensions never infer meaning from `sources`.
7. Extensions never create a second source of truth.
8. Extensions never execute business decisions on behalf of the core.

## Allowed Extension Categories

Every extension must fit one of these categories.

- `export`: read-only rendering or export of canonical state
- `analysis`: read-only processing of canonical state into derived output
- `integration`: interface with an external tool or system without authority over core state

No category has authority over the core.

## Guidelines

These are implementation guidelines that support the mandatory rules.

- import from `core`, not from `core.*` internals
- read state through `read_snapshot()`, `read_checkpoint()`, or `read_sources()`
- use read-only helpers such as `has_active_session()` only when they are explicitly exposed by `StateStore`
- treat every extension output as derived and disposable
- reject ambiguous behavior instead of guessing
- fail explicitly when the canonical state cannot be read safely
- keep filesystem writes outside `.cerebro/`
- keep extension code small, obvious, and replaceable

## Correct Example

`extensions/handoff_export/` is correct because it:

- reads the canonical snapshot through the public `StateStore` API
- renders a short Markdown handoff as derived output
- does not inspect source file contents
- does not modify runtime files
- rejects output paths inside `.cerebro/`

## Incorrect Example

The following shape is invalid:

```python
from pathlib import Path
import json

def run(root: Path) -> None:
    state_path = root / ".cerebro" / "state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["checkpoint"]["summary"] = "updated by extension"
    state_path.write_text(json.dumps(data), encoding="utf-8")
```

It is invalid because it:

- reads runtime JSON directly
- depends on internal runtime paths
- writes canonical state outside the core
- creates extension authority over product behavior

## Failsafe

If a proposed extension needs to guess, infer, or reach into runtime internals, do not implement it in that form.

- do not assume
- do not infer
- do not bypass
- do not write

Choose the most conservative design that keeps the core authoritative.
