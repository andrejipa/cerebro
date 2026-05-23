# validation-export

Read-only extension that renders a short validation view from the persisted canonical state.

## What It Does

- reads the current snapshot through the public core API
- renders a compact view of the last persisted validation result and detail codes
- prints to stdout or writes to an explicit output file

## What It Does Not Do

- it does not reopen validation on its own
- it does not modify state
- it does not modify session
- it does not inspect source contents
- it does not become a source of truth

The generated validation view is derived and disposable.

