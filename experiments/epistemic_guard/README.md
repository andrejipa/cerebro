# Epistemic Guard

`experiments/epistemic_guard/` is a derived, local-only, read-only advisory
experiment.

It builds deterministic `DecisionEnvelope` evidence for concrete action
questions. The envelope answers whether current evidence is sufficient to:

- do nothing;
- observe only;
- produce an advisory report;
- continue a derived experiment;
- require human approval;
- require a formal trigger for canonical/runtime change;
- block the action.

Hard boundary:

- may evaluate caller-supplied evidence;
- may render advisory JSON and Markdown;
- must preserve `state_change: none`;
- must not mutate `.cerebro/state.json`;
- must not import sources;
- must not edit target projects;
- must not create a runtime gate;
- must not create a canonical claim graph;
- must not treat advisory pass, approval presence, digest equality, or closeout
  as permission.

Slice 2 adds a checked-in TOML manifest loader. Manifest presence only makes the
same advisory envelope re-executable; it does not authorize the action described
inside the manifest.

Slice 3 adds pre-action reports. A pre-action manifest must include
`[proposed_action]` plus the bounded `[[scenario]]` evidence used by the
decision manifest loader. The resulting `PreActionGuardReport` aggregates
blockers, missing evidence, stale claims, conflicts, warnings, action readiness,
and recommended human decision before an operator treats a proposed action as
ready.

Pre-action reports are still advisory. They do not execute anything, grant
permission, mutate state, register sources, write memory, create a canonical
claim graph, or become a runtime gate.

Slice 4 adds a pre-action stress matrix. It records the expected behavior of
the operator-facing report under degraded evidence: missing `[proposed_action]`,
non-`none` expected state changes, runtime promotion without trigger, stale
approval, and read/write drift. Stress success is evidence that degraded cases
remain visible; it is not permission to execute.

Slice 5 adds a pre-action decision packet. It combines one
`PreActionGuardReport` with one `PreActionStressMatrixReport` and emits a single
operator-facing posture: `go_for_advisory_review`,
`go_requires_human_review`, or `no_go_blocked`.

The packet reduces review cost; it does not execute anything, approve anything,
grant permission, promote authority, register sources, write memory, create a
canonical claim graph, or become a runtime gate.

Slice 6 adds a pre-action packet stress/repro report. It checks that clean
packets, blocked packets, human-review packets, failed upstream stress,
checked-in JSON/Markdown packet artifacts, stale artifacts, malformed artifacts,
missing artifacts, root escapes, and `.cerebro/` targets stay visible as
advisory evidence.

Reproducibility and stress success are still not permission. Digest equality is
only reproducibility evidence; it is not truth, approval, source registration,
memory, runtime authority, execution, or promotion.

Slice 7 adds a pre-action packet review closeout. It consumes the pre-action
decision packet and packet stress/repro report, then declares whether this
derived lane should stop recursing until new evidence appears.

Closeout and `no_action` are still not permission. They only mean the current
derived review lane has no remaining blocker under the declared advisory inputs.
