# impact-export

Read-only extension that renders a short operational impact view from the canonical state.

## What It Does

- reads the current state through the public core API
- renders a compact view of the current operational surface
- prints to stdout or writes to an explicit output file

## What It Does Not Do

- it does not modify state
- it does not modify session
- it does not inspect source contents
- it does not infer semantic impact beyond canonical validation metadata
- it does not become a source of truth

The generated impact view is derived and disposable.
