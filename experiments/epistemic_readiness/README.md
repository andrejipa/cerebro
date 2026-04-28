# Epistemic Readiness

Derived advisory experiment for generating repeatable epistemic-readiness
reports from bounded source heads.

This package:

- accepts an explicit source manifest;
- reads bounded heads only;
- runs `experiments.claim_extraction`;
- runs `experiments.claim_evaluation`;
- optionally evaluates a declared action's risk budget and blast radius;
- can load those inputs from a checked-in TOML manifest;
- renders a stable Markdown report;
- renders a stable JSON decision trace for replay and self-audit;
- compares two advisory traces to expose replay drift and regressions;
- emits advisory protocol self-audit candidates from report/trace/diff evidence;
- separates stable semantic claim identity from evidence traceability drift;
- preserves `state_change: none`.

It does not:

- mutate `.cerebro/`;
- mutate target projects;
- create a claim graph;
- act as a runtime gate;
- promote report readiness into permission;
- replace human approval.

Risk-budget assessment is advisory evidence. It can say that a proposed action
needs a stronger gate, human review, a separate formal trigger, or must be
blocked, but it cannot grant permission by itself.

Manifest ingestion is also advisory-only. A manifest makes a report rerun
repeatable; it does not make the manifest a source of permission, authority, or
canonical truth.

Decision traces are replay evidence only. They expose what was read, which
candidate ids were extracted, which finding ids were evaluated, and what risk
assessment was produced. A trace must not become telemetry, runtime permission,
or a canonical claim graph.

Trace diffs compare two trace JSON payloads and report added, removed, kept,
changed, and traceability-changed source reads, claim candidates, and findings.
Candidate/finding comparison uses stable semantic identity while still surfacing
`claim_id`, `semantic_id`, `evidence_id`, and `evidence_span` movement as
traceability drift. They can recommend human review when readiness or risk
posture worsens, but they cannot apply promotion, demotion, or permission by
themselves.

Protocol self-audit reports are anti-noise candidate lists. They can point at
readiness regressions, guardrail weakening, risk degradation, source drift, or
identity churn, but they do not write memory, apply learned rules, promote or
demote authority, or grant permission.

Baseline lifecycle reports decide whether replay evidence is merely current,
eligible for human-approved baseline refresh, or blocked by regression/high-risk
self-audit evidence. They preserve semantic, source, and traceability drift
counts and never overwrite the baseline automatically.

Drift-policy reports sit after trace diff, protocol self-audit, and baseline
lifecycle. They classify replay drift into no-action, traceability-only drift,
human-approved refresh candidates, or blocked regression/protocol-risk cases.
They are advisory dispositions only: they can reduce review ambiguity, but they
cannot update the baseline, promote authority, demote authority, grant
permission, write memory, or become a runtime gate.

Replay bundles orchestrate the full advisory chain in one tested helper:
bounded report, decision trace, trace diff, protocol self-audit, baseline
lifecycle, and drift policy. The bundle writer is deliberately narrow: it writes
only declared derived outputs and rejects `.cerebro/`, root-escape, and
checked-in baseline targets. A replay bundle may propose review; it must not
refresh the baseline, act as a runtime gate, or grant permission.
