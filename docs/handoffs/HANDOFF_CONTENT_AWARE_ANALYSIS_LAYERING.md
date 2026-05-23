# Handoff — Content-Aware Analysis Layering

## Canonical Rule

**Content-aware filesystem analysis belongs in `experiments/`; `extensions/`
project canonical state through public APIs; `bootstrap_scan` remains
assistive-only and content-blind.**

This sentence is the contract. Future proposals that blur these boundaries
must either respect it or supersede it explicitly through an ADR.

## Why This Handoff Exists

On 2026-04-23 a formal slice attempted to add content-signal enrichment
directly to `cli/commands/bootstrap_scan.py`. The slice was withdrawn after
two explicit, pre-existing architecture invariants were re-encountered:

- `tests.test_architecture.test_bootstrap_scan_command_remains_assistive_only`
  forbids `open`, `read`, `read_bytes`, `read_text`, `io`, `subprocess`, and
  similar file-content-reading calls inside
  `cli/commands/bootstrap_scan.py`.
- `tests.test_architecture.test_extensions_do_not_read_files_or_enumerate_directories_directly`
  forbids the same operations across every module under `extensions/`.

The follow-on slice placed the new content-aware derived track at
`experiments/context_discovery/`, where content reads are architecturally
permitted (`experiments/recall_eval/` and `experiments/operational_signals/`
already do the same) and no canonical-runtime invariant is broken.

## The Three Layers, Named

- **`cli/commands/bootstrap_scan.py`** — *surface layer*. Classifies
  candidate entry files from path and filename only. Bounded time, bounded
  error surface, no I/O beyond `os.walk`. This is the "lexer" of Cerebro's
  bootstrap flow. It does not read file contents. That property is enforced
  by the architecture gate.

- **`extensions/*`** — *projector layer*. Read-only consumers of the
  canonical state. They use the public `core.StateStore` API to read
  snapshots and emit derived exports. They do not open or enumerate files
  on disk, do not import `json` or `subprocess`, and do not mutate state.
  Every extension carries a local `README.md` that declares these
  boundaries.

- **`experiments/*`** — *derived analysis layer*. Non-authoritative,
  registered in `experiments/lifecycle.toml` with an explicit status and
  review cadence. Experiments may read files, walk the target project, and
  produce reports. They never mutate `.cerebro/state.json`, never import
  from `cli/`, and never feed their output into the authoritative runtime
  without a separate, formally-triggered integration slice.

## Rule of Placement

When a new capability is proposed, answer in order:

1. Does it need to read or enumerate files on disk?
2. Does it need to mutate canonical runtime state?
3. Is it part of the bootstrap flow a first-time operator runs before any
   `.cerebro/state.json` exists?

- If (1) is yes and (2) is no, it belongs in `experiments/`.
- If (1) is no and it only derives from canonical state via the public API,
  it belongs in `extensions/`.
- If (3) is yes and (1) is no, it belongs in `cli/commands/bootstrap_scan.py`.
- If (2) is yes, it belongs in `core/` and requires a formal resume trigger
  plus explicit human acceptance.

Mixing (1) with (3) — "make the scanner read content" — is the antipattern
that this handoff exists to prevent.

## Supersedes

- supersedes: nothing; this handoff complements
  `HANDOFF_NEXT_LAYER_DECISION_BOOTSTRAP_SCAN.md` and the architecture gate
- superseded by: nothing

## Evidence

- `docs/operations/FORMAL_RESUME_TRIGGER_BOOTSTRAP_SCAN_ENRICHMENT.md`
  (withdrawn on 2026-04-23 for architecture-invariant collision)
- `docs/operations/FORMAL_RESUME_TRIGGER_CONTEXT_DISCOVERY_EXT_SLICE_1.md`
  (implementation complete; formal closure pending full AGENTS-equivalent
  gate in the Windows environment)
- `experiments/context_discovery/` (new derived track registered in
  `experiments/lifecycle.toml`)
- `tests/test_architecture.py` tests that enforce the three-layer rule:
  `test_bootstrap_scan_command_remains_assistive_only`,
  `test_extensions_do_not_read_files_or_enumerate_directories_directly`,
  `test_extensions_import_only_public_core_api`,
  `test_extensions_do_not_call_internal_state_store_operations`
