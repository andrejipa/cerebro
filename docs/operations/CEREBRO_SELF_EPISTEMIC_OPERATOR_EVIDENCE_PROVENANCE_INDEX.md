# Epistemic Readiness Operator Evidence Provenance Index

This is advisory operator evidence only. It is not a runtime gate, not memory, not a canonical graph, and not permission to act.

## Summary

- authority: non-authoritative; advisory operator evidence provenance index only
- state_change: none
- action_readiness: advisory_report_allowed
- recommended_human_decision: none
- artifact_count: 20
- present_count: 20
- dependency_edge_count: 39
- blocker_count: 0
- digest_manifest: d254a139135ddb7f46f29c8e28e3f8252894244ecb6bb2b74aee6eb9b99f4ef8

## Artifacts

| Artifact | Format | Digest | State Change | Authority | Parse | Dependencies | Summary |
|---|---|---|---|---|---|---|---|
| readiness_manifest | toml | 821b020a57474533a89d38a8f5184f839a157c65513168be9356dd6ec58a2960 | none | non-authoritative; advisory evidence only | parsed_toml | none | no indexed summary fields |
| readiness_report | markdown | 6fc8f4eeaa9b47f11b603934e1ddf83c3691e447f64bfccaeb1c464eaff128b2 | not_declared_text_digest_only | not_declared_text_digest_only | text_digest_only | readiness_manifest | text digest only; no truth inferred |
| readiness_trace | json | 5e2c0236c54d9dd1a60557357eda3654b4a0d508ff6c22fa1780cec01bbd5f44 | none | non-authoritative; advisory trace evidence only | parsed_json | readiness_manifest | action_readiness=derived_experiment_allowed |
| readiness_trace_baseline | json | 5e2c0236c54d9dd1a60557357eda3654b4a0d508ff6c22fa1780cec01bbd5f44 | none | non-authoritative; advisory trace evidence only | parsed_json | readiness_trace | action_readiness=derived_experiment_allowed |
| readiness_trace_diff | json | 8b7db86ff8c822f89eb721796dfe978eb53292ab19b6d019d475ea9d12ce12d2 | none | non-authoritative; advisory trace-diff evidence only | parsed_json | readiness_trace, readiness_trace_baseline | no indexed summary fields |
| protocol_self_audit | json | c1d5ab6ae3947928af446541a0a200c1b192ecf37cd9c0e06a32de0b68dcdfdd | none | non-authoritative; advisory protocol self-audit evidence only | parsed_json | readiness_trace_diff | no indexed summary fields |
| baseline_lifecycle | json | 9ecae3c306a345649cc43144ef6693240b9474559ce545f615fea217c519e547 | none | non-authoritative; advisory baseline lifecycle evidence only | parsed_json | readiness_trace, readiness_trace_baseline, readiness_trace_diff, protocol_self_audit | no indexed summary fields |
| drift_policy | json | 8a6a00025b8a5860921ba79414f592824cfc45b4420ae67ab0c1348eaf09d809 | none | non-authoritative; advisory replay drift policy evidence only | parsed_json | readiness_trace_diff, protocol_self_audit, baseline_lifecycle | no indexed summary fields |
| metacognitive_handoff | json | ac110d0def9bffa90d02ffb2da3c26c2110012694aeca34497796856f1d0d3b9 | none | non-authoritative; advisory metacognitive handoff evidence only | parsed_json | readiness_trace, baseline_lifecycle, protocol_self_audit, drift_policy | action_readiness=no_action; recommended_human_decision=none |
| handoff_stress_matrix | json | 23e1077dfe7ee90a2baa67edecd34bbb997907639d1c691142b6ced3eb11ad22 | none | non-authoritative; advisory handoff stress matrix evidence only | parsed_json | metacognitive_handoff | scenario_count=5; pass_count=5; fail_count=0 |
| human_decision_taxonomy | json | 5f9e12611e44319c3260cbdd27523af58bd7313cc743efcd22e42a69fba5640f | none | non-authoritative; advisory human decision taxonomy evidence only | parsed_json | handoff_stress_matrix | no indexed summary fields |
| decision_taxonomy_conformance | json | a3c4bb7a1b12a419bac9f32338805c43b76c448dc9797436f2017c8be00a02dc | none | non-authoritative; advisory decision taxonomy conformance evidence only | parsed_json | human_decision_taxonomy, handoff_stress_matrix | pass_count=5; fail_count=0 |
| operator_decision_packet | json | bfaa93d5629776be99f6a216e0bb2515c2644c3e52bc92c1bdc1ae87b6d291a9 | none | non-authoritative; advisory operator decision packet evidence only | parsed_json | metacognitive_handoff, decision_taxonomy_conformance, drift_policy, baseline_lifecycle | action_readiness=no_action; recommended_human_decision=none; blocker_count=0 |
| operator_packet_stress_matrix | json | 9554ce0a1e67e24923439cadc3e3f5cbbc25a3141841dd9becff78fa87a6a543 | none | non-authoritative; advisory operator packet stress matrix evidence only | parsed_json | operator_decision_packet | scenario_count=6; pass_count=6; fail_count=0; all_scenarios_passed=true |
| operator_evidence_bundle | json | ab330ddb47036cd50bbbdff8f43be5b5f354d6bd76b99fe3ce4bc2ba0957b29b | none | non-authoritative; advisory operator evidence bundle only | parsed_json | operator_decision_packet, operator_packet_stress_matrix, baseline_lifecycle, decision_taxonomy_conformance, drift_policy, metacognitive_handoff | input_count=6; source_artifact_count=4; boundary_error_count=1 |
| operator_evidence_bundle_stress_matrix | json | 2acd71d0eac68d65d73c990e87eea8a6c7885efe4a9b6844534ea40fcf42e808 | none | non-authoritative; advisory operator evidence bundle stress matrix only | parsed_json | operator_evidence_bundle | blocker_count=6; scenario_count=7; pass_count=7; fail_count=0; all_scenarios_passed=true; boundary_error_count=6 |
| operator_evidence_intake_manifest | toml | 404d07e4a6fa5ab444499b9be5279cacc1b2159a41b20202c45486e4cada192b | none | non-authoritative; advisory operator evidence intake manifest only | parsed_toml | operator_evidence_bundle | no indexed summary fields |
| operator_evidence_intake_report | json | eb3c2a168b94736737133d56c57410fb180c5e9def567694b1c5c54466a599c9 | none | non-authoritative; advisory operator evidence intake report only | parsed_json | operator_evidence_intake_manifest, operator_evidence_bundle | action_readiness=advisory_report_allowed; recommended_human_decision=none; blocked=false; blocker_count=0; input_count=6; source_artifact_count=4 |
| operator_evidence_intake_stress_matrix | json | 05e3e070d0386e31e7402bbb707c25f63aa326501315ff6f5cc94a9162b8c0a4 | none | non-authoritative; advisory operator evidence intake stress matrix only | parsed_json | operator_evidence_intake_report | blocker_count=7; scenario_count=8; pass_count=8; fail_count=0; all_scenarios_passed=true; boundary_error_count=7 |
| operator_evidence_intake_reproducibility_check | json | f6f09e900640dbe5b3a9d980218cab765aa0b5808a0468973705dfe54d49c053 | none | non-authoritative; advisory operator evidence intake reproducibility check only | parsed_json | operator_evidence_intake_manifest, operator_evidence_intake_report | action_readiness=advisory_report_allowed; recommended_human_decision=none; reproducibility_status=reproducible; blocked=false; blocker_count=0; mismatch_count=0; digest_match=true |

## Blockers

- none

## Guardrails

- provenance_index_is_not_permission: true
- provenance_index_is_not_memory: true
- provenance_index_is_not_authority: true
- provenance_index_is_not_runtime_gate: true
- provenance_index_is_not_claim_graph: true
- provenance_index_is_not_source_registry: true
- dependency_map_is_not_canonical_graph: true
- digest_is_not_truth: true
- silence_is_not_negative_evidence: true

## Must Not Apply

- mutate state
- register sources
- refresh artifacts automatically
- update replay baseline
- write memory automatically
- act as runtime gate
- create canonical claim graph
- create canonical evidence graph
- promote or demote authority
- treat provenance as permission
- treat digests as truth
- hide blockers
- infer negative evidence from silence
