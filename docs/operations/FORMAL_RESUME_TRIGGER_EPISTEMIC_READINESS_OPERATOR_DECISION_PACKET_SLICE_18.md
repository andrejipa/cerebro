# Formal Resume Trigger — Epistemic Readiness Operator Decision Packet, Slice 18

## Status

- status: consumed
- opened_at: 2026-04-24
- owner: Orchestrator
- accepted_by_operator: explicit continuation request, "mature sua ideia" / "sem ser conservador, avance"
- mode: execution
- level: 2

## Objective

Add a bounded advisory operator decision packet that combines the current
metacognitive handoff, decision-taxonomy conformance, drift policy, and baseline
lifecycle evidence into one compact evidence-to-action summary for the human
operator.

The packet must say what is known, what is unknown, what is blocked, what
evidence is missing, and which human decision, if any, is requested. It must make
the evidence easier to act on without becoming permission or runtime authority.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_DECISION_PACKET_SLICE_18.md`
- `experiments/epistemic_readiness/operator_decision_packet.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_DECISION_PACKET.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_DECISION_PACKET.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`.
- Do not touch `cli/`.
- Do not touch `extensions/`.
- Do not touch `core/schema.py`.
- Do not alter `.cerebro/state.json`.
- Do not create a runtime gate.
- Do not create a canonical claim graph.
- Do not promote claim extraction, claim evaluation, metacognitive handoff,
  decision taxonomy conformance, drift policy, baseline lifecycle, or operator
  packet output into authority.
- Do not treat the packet as permission.
- Do not treat conformance pass as permission.
- Do not update replay baselines.
- Do not write memory automatically.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- A deterministic advisory operator packet exists under
  `experiments/epistemic_readiness/`.
- The packet consumes only existing advisory payloads: metacognitive handoff,
  decision taxonomy conformance, drift policy, and baseline lifecycle.
- The packet preserves `state_change: none`.
- The packet surfaces blockers and incompatible conformance instead of hiding
  them.
- The packet preserves human-decision/readiness semantics from the handoff when
  human intervention is required.
- JSON and Markdown renderers expose the non-authoritative boundary.
- Focused tests cover clean no-action, conformance failure, handoff escalation,
  mutating/malformed input rejection, and renderer boundary text.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_DECISION_PACKET.{json,md}`
  are generated from the implemented helper.

## Required Gates

- Initial full AGENTS-equivalent gate before implementation.
- Focused `experiments.epistemic_readiness` tests after implementation.
- `tests.test_architecture` and `tests.test_doc_governance` after docs updates.
- Final full AGENTS-equivalent gate before marking this trigger consumed.

## Stop Conditions

- Any packet output grants permission.
- Any blocker or incompatible conformance is hidden or coerced to pass.
- Any output mutates state, writes memory, updates replay baselines, creates a
  claim graph, or becomes runtime authority.
- Any edit outside the whitelist is required.
- Any gate turns red and cannot be fixed inside the whitelist.

## Closure

- result: consumed
- implementation: `OperatorDecisionPacket`, `build_operator_decision_packet(...)`, `render_operator_decision_packet_json(...)`, and `render_operator_decision_packet_markdown(...)`
- real_artifacts: `CEREBRO_SELF_EPISTEMIC_OPERATOR_DECISION_PACKET.json`; `CEREBRO_SELF_EPISTEMIC_OPERATOR_DECISION_PACKET.md`
- real_output: `recommended_human_decision=none`, `action_readiness=no_action`, `conformance_passed=true`, `18` sources, `35` candidates, `35` findings, `35` ready, `0` blocked, `0` insufficient, `blocker_count=0`, `missing_evidence_count=0`, `state_change: none`
- focused_validation: `experiments.epistemic_readiness` `65` tests, `0` failures, `0` errors
- governance_validation: `tests.test_architecture` + `tests.test_doc_governance` `64` tests, `0` failures, `0` errors
- final_gate: full AGENTS-equivalent `923` tests, `0` failures, `0` errors, `6` skipped
- next_candidate: `epistemic-readiness-operator-packet-stress-matrix-slice-19`
