# Formal Resume Trigger — Epistemic Guard Applied Third-Party Decision Slice 8

## Status

- status: consumed
- opened: 2026-04-24
- level: 1
- mode: docs-and-derived-artifacts-only
- initial_gate: AGENTS-equivalent `923` tests, `0` failures, `0` errors, `6` skips

## Objective

Apply the existing Epistemic Guard pre-action packet machinery to a real
operator decision:

> Should the Cerebro workstream resume the third-party project-management pilot
> now?

This slice must produce advisory evidence only. It may classify the decision,
make blockers visible, and identify the next human/operator step, but it must
not execute the pilot and must not mutate any third-party project.

## Whitelist

Allowed writes:

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_SLICE_8.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_REPORT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_REPORT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_PACKET.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_PACKET.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_PACKET_STRESS_REPRO.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_PACKET_STRESS_REPRO.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_CLOSEOUT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_CLOSEOUT.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

Allowed reads:

- `AGENTS.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- `docs/operations/FORMAL_RESUME_TRIGGER_THIRD_PARTY_PILOT.md`
- `docs/operations/THIRD_PARTY_INTAKE_GATE_RPG_CAMINHADA.md`
- `docs/operations/THIRD_PARTY_PILOT_RECON_CLAUDE.md`
- existing `experiments/epistemic_guard/` modules

## Explicit Prohibitions

- Do not touch `core/`.
- Do not touch `cli/`.
- Do not touch `extensions/`.
- Do not touch top-level `tests/`.
- Do not touch `core/schema.py`.
- Do not alter `.cerebro/state.json`.
- Do not create runtime gates.
- Do not create a canonical claim graph.
- Do not promote `claim_extraction`, `claim_evaluation`, or `epistemic_guard`
  to runtime authority.
- Do not mutate `D:\projetos_cli\pessoais\rpg_caminhada` or any other
  third-party project.
- Do not run `cerebro init` or `cerebro import-context` in a target project.
- Do not treat an advisory pass as permission.

## Stop Conditions

Stop if:

- the AGENTS-equivalent gate is red;
- the applied decision cannot be expressed as `expected_state_change = "none"`;
- any artifact would need to live under `.cerebro/`;
- the packet recommends automatic execution;
- the output tries to authorize target-project mutation;
- any generated artifact is non-reproducible;
- the slice requires implementation changes.

## Acceptance Criteria

The slice can close only when:

- the applied decision manifest exists and declares no state change;
- report, packet, stress/repro, and closeout artifacts exist;
- all artifacts explicitly preserve:
  - advisory-only authority;
  - `state_change: none`;
  - `must_not_execute_automatically`;
  - `silence_is_not_negative_evidence`;
- the output distinguishes advisory readiness from permission to mutate a
  third-party project;
- `experiments.epistemic_guard.tests.test_epistemic_guard` stays green;
- `tests.test_architecture` and `tests.test_doc_governance` stay green;
- the AGENTS-equivalent full gate stays green;
- `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md`, and `observation_center.toml`
  record the result without opening a runtime boundary.

## Closure

Consumed on 2026-04-24 after applying the existing Epistemic Guard
pre-action pipeline to the real operator decision of whether to resume the
third-party project-management pilot now.

Artifacts:

- `CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_MANIFEST.toml`
- `CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_REPORT.{json,md}`
- `CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_PACKET.{json,md}`
- `CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_PACKET_STRESS_REPRO.{json,md}`
- `CEREBRO_SELF_EPISTEMIC_GUARD_APPLIED_THIRD_PARTY_DECISION_CLOSEOUT.{json,md}`

Real output:

- report: `action_readiness=advisory_report_allowed`,
  `recommended_human_decision=none`, `blocker_count=0`,
  `missing_evidence_count=0`
- packet: `operator_posture=go_for_advisory_review`,
  `action_readiness=advisory_report_allowed`,
  `recommended_human_decision=none`, `packet_blocker_count=0`
- stress/repro: `case_count=10`, `pass_count=10`, `fail_count=0`
- closeout: `closeout_status=closed_until_new_evidence`,
  `action_readiness=no_action`, `blocker_count=0`

Decision:

- The advisory decision surface is clear enough to resume operator planning for
  the third-party pilot.
- This does not authorize `cerebro init`, `import-context`, or any target
  `.cerebro/` mutation.
- The next concrete step remains human approval or amendment of
  `THIRD_PARTY_INTAKE_GATE_RPG_CAMINHADA.md`, including target selection,
  legacy `.cerebro/state.json` handling, and exact source set.

Final gate evidence:

- focused `experiments.epistemic_guard.tests.test_epistemic_guard`: `33`
  tests, `0` failures
- `tests.test_architecture` + `tests.test_doc_governance`: `64` tests, `0`
  failures
- AGENTS-equivalent full gate: `923` tests, `0` failures, `0` errors, `6`
  skips
