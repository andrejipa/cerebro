# Handoff - Epistemic Readiness Operator Evidence Intake

## Status

- date: 2026-04-24
- mode: handoff / consolidation only
- authority: advisory documentation, not runtime authority
- state_change: none
- current_gate: full AGENTS-equivalent `923` tests, `0` failures, `0` errors, `6` skipped
- current_queue_head: `epistemic-readiness-operator-evidence-intake-reproducibility-check-slice-24`

This handoff consolidates the current point in the Risk-Adaptive Epistemic
Runtime lane after slice 23. It does not open a boundary, authorize
implementation, promote any derived report to runtime authority, mutate
canonical state, write memory, register sources, or create a claim graph.

## Where We Are

The epistemic-readiness lane has moved from "can we produce advisory evidence?"
to "can we prove the advisory evidence itself is reproducible, bounded, and
degraded-input aware?"

The current operator-facing chain is:

1. Read bounded operational sources through explicit manifests.
2. Extract claim candidates.
3. Evaluate claim candidates into advisory readiness findings.
4. Emit repeatable reports and decision traces.
5. Compare traces against a checked-in advisory baseline.
6. Surface protocol self-audit candidates.
7. Classify drift and baseline lifecycle.
8. Package the result into metacognitive handoff, human decision taxonomy,
   operator decision packet, packet stress matrix, evidence bundle, bundle
   stress matrix, manifest-driven intake, and intake stress matrix artifacts.

The important shift is that the lane no longer relies only on "the report says
ready." It now asks whether the report, bundle, inputs, manifest, digests, and
stress behavior survive degraded evidence. This is the practical shape of:

```text
Explore fast.
Trust slowly.
Act only with proof.
Demote when proof degrades.
```

## What Slice 23 Proved

Slice 23 consumed
`FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_INTAKE_STRESS_SLICE_23`.

Implemented helper:

- `experiments/epistemic_readiness/operator_evidence_intake_stress_matrix.py`

Generated artifacts:

- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX.md`

Real output:

- `scenario_count=8`
- `pass_count=8`
- `fail_count=0`
- `all_scenarios_passed=true`
- `blocker_count=7`
- `boundary_error_count=7`

Scenario meaning:

- `clean_manifest` remains `none/advisory_report_allowed`.
- `missing_artifact`, `stale_digest`, `root_escape`, `non_json_artifact`,
  `mutating_payload`, `duplicate_artifact_id`, and
  `missing_required_artifact` all become `review_blockers/blocked`.

This proves the intake layer does not silently turn degraded declared evidence
into a clean operator bundle. Malformed, stale, missing, escaping, mutating,
duplicate, and incomplete inputs stay visible as blockers.

## What Is Still Not Proven

The checked-in intake artifacts are now stress-tested as a protocol shape, but
they are not yet automatically checked for reproducibility against a fresh
regeneration.

That means the lane can currently prove:

- a manifest can drive an advisory intake report;
- degraded manifest inputs block as expected;
- digest equality is treated as reproducibility evidence only;
- stress pass is not permission.

It does not yet prove, as a reusable check:

- the checked-in intake report still matches a freshly regenerated intake
  report;
- the checked-in Markdown and JSON are synchronized with the current manifest;
- a stale derived artifact is detected before a human relies on it;
- a mismatch is surfaced without auto-refreshing the artifact.

This gap is exactly what slice 24 should close.

## Matured Thesis

The lane should keep moving toward a derived evidence supply chain:

```text
source manifest
  -> bounded read
  -> claim extraction
  -> claim evaluation
  -> readiness report
  -> decision trace
  -> trace diff
  -> protocol self-audit
  -> lifecycle/drift policy
  -> metacognitive handoff
  -> operator decision packet
  -> evidence bundle
  -> manifest-driven intake
  -> stress matrix
  -> reproducibility check
```

The next maturity threshold is not more semantic intelligence. The next useful
threshold is self-checking evidence freshness: if an operator-facing advisory
artifact is checked in, the system should be able to say whether it still
reproduces from its declared inputs.

This remains advisory. It must not become permission, memory, authority,
source registration, a runtime gate, canonical state, automatic baseline
refresh, or a canonical claim graph.

## Next Slice

Queue head:

- `epistemic-readiness-operator-evidence-intake-reproducibility-check-slice-24`

Recommended trigger:

- `FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_INTAKE_REPRODUCIBILITY_CHECK_SLICE_24.md`

Recommended scope:

- add a derived helper in `experiments/epistemic_readiness/`;
- read the existing checked-in intake manifest/report artifacts;
- regenerate the intake report from the manifest;
- compare stable machine-facing fields and/or stable digests;
- report `reproducible`, `stale_or_mismatched`, or `blocked_input`;
- render JSON/Markdown advisory outputs;
- add focused tests for clean, stale report, missing artifact, stale digest,
  malformed report, mutating report, and root escape;
- update `observation_center.toml`, `SYSTEM_STATE.md`, and
  `OPPORTUNITY_MAP.md` only after gates are green.

Required behavior:

- clean checked-in artifacts produce `none/advisory_report_allowed`;
- stale or mismatched checked-in artifacts produce
  `review_blockers/blocked`;
- missing or malformed input produces visible blockers;
- no output auto-refreshes checked-in artifacts;
- no output treats digest equality as truth;
- no output grants permission.

## Do Not Do Next

Do not jump directly to runtime integration.

Do not promote `claim_extraction`, `claim_evaluation`, `epistemic_readiness`,
operator packets, evidence bundles, intake reports, or stress matrices to
runtime authority.

Do not create a canonical claim graph.

Do not update `.cerebro/state.json`.

Do not add automatic source registration.

Do not make the checker a gate. It can recommend blocking; it cannot enforce
runtime blocking without a separate explicit trigger.

Do not refresh artifacts automatically when mismatch is detected. Mismatch is
evidence for review, not authorization to rewrite.

## Wake-Up Protocol

On the next continuation:

1. Read `AGENTS.md`.
2. Read `docs/operations/observation_center.toml`.
3. Read `docs/operations/SYSTEM_STATE.md`.
4. Read `docs/operations/OPPORTUNITY_MAP.md`.
5. Confirm queue head remains
   `epistemic-readiness-operator-evidence-intake-reproducibility-check-slice-24`.
6. Run the full AGENTS-equivalent gate before any write.
7. If green, open a narrow formal trigger for slice 24.
8. Implement only inside the trigger whitelist.
9. Run focused tests, architecture/doc governance, then full gate.

If any of these diverge, reconcile docs first and do not start slice 24.
