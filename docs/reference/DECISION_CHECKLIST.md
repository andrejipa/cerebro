# Decision Checklist

Use this before changing architecture, adding files, creating abstractions, or expanding scope.

## Accept Only If

- The change preserves a single canonical source of truth.
- The change keeps derived views, summaries, and exports clearly derived.
- The change belongs in the core only if it is essential to runtime truth or invariants.
- The change goes to an extension when it is optional, contextual, or replaceable.
- The change reduces ambiguity instead of adding interpretation layers.
- The change improves robustness in proportion to its added complexity.
- The change serves the system's purpose, not a side goal or convenience artifact.
- The change preserves existing invariants, contracts, and validation boundaries.

## Reject Or Isolate If

- It turns a view, cache, summary, prompt, or helper into a second source of truth.
- It mixes categories such as runtime state, documentation, heuristic guidance, and derived output.
- It introduces inference where the system currently depends on explicit input.
- It puts optional behavior into the core without a runtime invariant that requires it.
- It adds complexity, indirection, or files without strengthening correctness or maintainability.
- It weakens `validate`, bypasses explicit sources, or blurs core versus extension boundaries.
- It expands repository scope with material that is not active product code, tests, or essential documentation.

## Fast Questions

Ask these in order:

1. Is this canonical truth, or only a derived view?
2. Does this belong in the core, or should it stay in an extension or document?
3. Does this introduce inference, ambiguity, or category mixing?
4. Does this create a new source of truth, even indirectly?
5. Does the added complexity buy real robustness?
6. Does this serve the system's actual purpose?
7. Does this threaten an existing invariant or contract?

If any answer is unclear, preserve the current boundary and isolate the proposal until it is explicit.

## Scope Guard

This checklist is governance only.

- It guides humans and future agents.
- It does not enter runtime state.
- It does not become an automatic source.
- It does not affect `validate`.
- It does not change product behavior by itself.
