# context-index-export

Read-only extension that renders a short navigation index derived from canonical state and organized around canonical registered sources and canonical checkpoint text.

## What It Does

- reads the current state through the public core API
- groups registered sources by top-level path family
- highlights checkpoint-derived continuity anchors from exact case-sensitive path mentions and unique basename mentions in canonical checkpoint text only
- prints to stdout or writes to an explicit output file
- flattens multiline checkpoint fields into single-line Markdown-safe bullets

## What It Does Not Do

- it does not modify state
- it does not modify session
- it does not inspect source contents
- it does not overwrite registered canonical source files
- it does not infer or register new `sources`
- it does not compete with `analyze`
- it does not become a source of truth

The generated context index is derived and disposable.
