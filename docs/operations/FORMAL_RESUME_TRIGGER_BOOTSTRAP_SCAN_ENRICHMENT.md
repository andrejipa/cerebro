# Formal Resume Trigger — Bootstrap Scan Content-Signal Enrichment

## Status

- `proposed on 2026-04-23`
- `accepted on 2026-04-23 by André`
- `rejected / withdrawn on 2026-04-23 — scope collision with an existing formal architecture invariant`
- objective result: **not consumed**; all proposed code-level changes to `cli/commands/bootstrap_scan.py`, `cli/main.py`, and `tests/test_bootstrap_scan.py` were reverted to HEAD; no runtime surface was modified; no canonical state was touched
- boundary after withdrawal:
  - `core/`: closed
  - `tests/`: closed
  - `cli/`: closed
  - `docs/`: authorized (only for this withdrawal record)

## Classification

- `withdrawn — architecture-invariant collision`

## Why This Trigger Was Withdrawn

The trigger proposed adding a bounded content-signal pass to `cli/commands/bootstrap_scan.py`. During verification, two explicit, pre-existing invariants were identified that contradict that proposal:

1. `tests/test_architecture.py` has a test named `test_bootstrap_scan_command_remains_assistive_only` that forbids `open`, `read`, `read_bytes`, `read_text`, `io`, `subprocess`, and similar file-content-reading calls inside `cli/commands/bootstrap_scan.py`. The assistive-only property is enforced by the architecture gate.
2. `docs/handoffs/HANDOFF_NEXT_LAYER_DECISION_BOOTSTRAP_SCAN.md` carries the asserted sentence *"it does not read file contents for classification"* as a formal handoff decision.

Both are prior, explicit, formally-tested commitments that the scanner surface remains bounded to path and filename signals only. The content-signal enrichment proposed here required violating both. The trigger's own Stop Conditions forbid weakening architecture tests or relaxing invariants in order to pass, so the slice was stopped and reverted instead of completed.

## Replacement Direction

The same operator gap (curadoria inicial, drift, visibilidade) will be attacked through a read-only derived track at `extensions/context_discovery/` under a new trigger. Extensions are a legitimate non-authoritative consumer surface where content-aware analysis is architecturally natural and no pre-existing invariant is broken.

The follow-on trigger is `docs/operations/FORMAL_RESUME_TRIGGER_CONTEXT_DISCOVERY_EXT_SLICE_1.md`.

## Lessons Captured

- Before proposing a slice that touches `cli/commands/bootstrap_scan.py`, re-read `tests/test_architecture.py` and the `docs/handoffs/HANDOFF_NEXT_LAYER_DECISION_BOOTSTRAP_SCAN.md` decision. The architecture gate is the authority when filename or path assumptions suggest a natural place for new behavior.
- Do not accept a trigger that enlarges the scanner surface without first verifying that no architecture-gate invariant already forbids the change.
- Content-aware discovery work belongs in `extensions/`, not in `cli/`. Mixing surface-cheap and content-heavy analysis in one component fans in I/O concerns (binary, encoding, size) and contaminates the bounded-error, bounded-time property the scanner was designed around.
