# status-export

Read-only extension that renders a short operational status from the canonical state.

## What It Does

- reads the current state through the public core API
- renders a compact operational status view
- prints to stdout or writes to an explicit output file

## What It Does Not Do

- it does not modify state
- it does not modify session
- it does not inspect source contents
- it does not infer missing context
- it does not become a source of truth

The generated status is derived and disposable.
