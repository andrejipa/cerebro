# Third-Party Trigger Review

`experiments/third_party_trigger_review/` is a deterministic advisory checker for
proposed third-party project triggers.

It reviews caller-supplied trigger text against the third-party dogfood runbook
and reports missing or risky fields before an agent starts target work.

It checks for:

- `target_path`
- `slice_kind`
- `dogfood_value`
- `proof_cost`
- source-set roles
- target `.cerebro/` handling
- rollback and cleanup
- stop conditions
- forbidden paths
- consecutive target-slice consolidation risk
- runtime boundary drift

It does not read target projects, mutate files, register sources, write memory,
create a runtime gate, call a network service, or approve execution. A pass means
only `ready_for_human_review`.
