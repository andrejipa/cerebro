# sources-export

Read-only extension that renders a short inventory of registered sources from the canonical state.

## What It Does

- reads the current state through the public core API
- renders a compact inventory of registered source paths and roles
- prints to stdout or writes to an explicit output file

## What It Does Not Do

- it does not modify state
- it does not modify session
- it does not inspect source contents
- it does not infer project coverage or semantic meaning
- it does not become a source of truth

The generated sources view is derived and disposable.
