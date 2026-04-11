# handoff-export

Read-only extension that renders a short Markdown handoff from the canonical state.

## What It Does

- reads the current state through the public core API
- renders a short human-readable handoff
- prints to stdout or writes to an explicit output file

## What It Does Not Do

- it does not modify state
- it does not modify session
- it does not read source contents
- it does not infer missing context
- it does not become a source of truth

The generated handoff is derived and disposable.
