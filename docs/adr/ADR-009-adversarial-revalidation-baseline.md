# ADR-009: Adversarial Revalidation Is The Public-Surface Baseline

## Context

The repository now has a deterministic core, explicit boundaries, read-only extensions, and architectural tests.

That architecture was recently attacked through adversarial revalidation of:

- corrupted `state.json`
- corrupted `session.local.json`
- broken and malicious `sources`
- blocked `analyze` flows
- repeated runtime cycles
- extension boundary and filesystem bypass attempts

No critical or moderate failures were found.
If this result remains only as an informal memory of one test cycle, future changes can weaken the system without clearly violating a documented rule.

## Decision

Adopt the adversarial revalidation baseline as a permanent evolution rule for the public surface of the system.

- the current robustness baseline is recorded in `docs/operations/ROBUSTNESS_BASELINE.md`
- exports and derived views remain subordinate to the canonical snapshot and the last persisted validation result
- exports do not revalidate the runtime by themselves and do not create a second validation gate
- any change to the public surface must add proportional adversarial and regression coverage
- hardening remains outside the runtime unless a concrete gap cannot be contained by tests and governance

Public-surface changes include:

- new or changed CLI commands
- new or changed extensions
- new or changed external integrations

## Consequences

- future contributors must treat adversarial tests as part of the contract, not optional extra caution
- documentary drift around robustness becomes a testable regression risk
- hardening is no longer open-ended; it should expand only for a concrete new evasion path or a real surface change
- the core remains unchanged by this policy; enforcement stays in tests, documentation, and architectural review
