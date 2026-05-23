# Control Plane Evidence Policy Review

`control_plane_evidence_policy_review` is a read-only, non-authoritative review of caller-supplied evidence policy candidates and evidence records.

It exists before any evidence store, evidence registry, runtime state, scheduler, queue reader, adapter, or canonical gate exists in this repository.

The package evaluates whether proposed evidence rules and records preserve the required distinctions:

- accepted evidence is not truth;
- evidence status is not execution approval;
- raw or secret material cannot be accepted;
- sensitive or personal evidence needs redaction and human decision evidence;
- expired, quarantined, rejected, and insufficient evidence cannot be silently promoted.

## Boundary

- state_change: none
- authority: non-authoritative; advisory control-plane evidence policy review only
- evidence_policy_review_is_not_permission: true
- accepted_evidence_is_not_truth: true
- evidence_record_is_not_truth: true
- evidence_record_is_not_runtime_state: true
- evidence_policy_review_is_not_evidence_store: true
- evidence_status_is_not_execution_approval: true
- evidence_sufficiency_is_not_execution_approval: true
- approval_presence_is_not_sufficient_evidence: true
- silence_is_not_negative_evidence: true
- secret_material_must_not_be_retained: true
- raw_tool_output_must_not_be_retained: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

The package does not read `.cerebro/`, `docs/operations`, state files, queues, locks, sessions, events, evidence stores, runtime stores, or target-project files. It does not import core runtime modules, runtime SDKs, CLI modules, adapters, network/process libraries, or storage backends. It does not write files, execute commands, mutate state, register evidence, store evidence, recover locks, schedule work, choose a next action, grant permission, approve execution, or become a source of truth.

All inputs are supplied by the caller as already-sanitized in-memory payloads or already-built advisory review objects.
