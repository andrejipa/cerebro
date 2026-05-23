# Control Plane Work Queue Review

state_change: none

This package reviews caller-supplied work queue candidates before any QA queue,
work queue file, queue reader, scheduler, state store, worker reservation, or
canonical runtime boundary exists.

It is non-authoritative package code. It does not read `docs/operations`,
`tasks/`, `.cerebro/`, queue files, state files, or live stores. It does not
write files, enqueue work, dequeue work, reserve workers, execute commands,
call tools, schedule work, choose next action, grant permission, mutate state,
or become a runtime/canonical gate.

## Guardrails

- authority: non-authoritative; advisory control-plane work queue review only
- work_queue_review_is_not_permission: true
- work_queue_review_is_not_scheduler: true
- queue_item_is_not_execution_approval: true
- queue_priority_is_not_truth: true
- dependency_status_is_not_truth: true
- ready_status_is_not_execution_approval: true
- work_queue_review_is_not_queue_reader: true
- work_queue_review_is_not_state_store: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

## Scope

The review can detect inconsistent candidate items, revision/supersession drift,
missing evidence, unknown or blocked dependencies, missing acceptance criteria,
missing owners, high-priority items without decision evidence, ready candidates
with unsatisfied dependencies, scheduler/queue/state authority claims, priority
truth claims, auto-dispatch claims, live queue reads, state mutation, secret
material, supplied-review guardrail drift, and forged summaries.

It can report `work_queue_candidates_observed`,
`work_queue_review_attention_required`, or `work_queue_review_blocked`. These
statuses are advisory review statuses only.
