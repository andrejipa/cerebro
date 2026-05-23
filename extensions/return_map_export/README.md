# return-map-export

Read-only extension that renders a short restart map from the canonical checkpoint.

## What It Does

- reads the current state through the public core API
- renders a short point-of-return view for human or agent resume
- prints to stdout or writes to an explicit output file

## What It Does Not Do

- it does not modify state
- it does not modify session
- it does not inspect source contents
- it does not add lineage metadata that does not exist in the canonical state
- it does not become a source of truth

The generated return map is derived and disposable.
