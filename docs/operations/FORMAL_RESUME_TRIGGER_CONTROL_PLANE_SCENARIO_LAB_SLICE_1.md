# FORMAL RESUME TRIGGER - Control Plane Scenario Lab Slice 1

status: consumed
created_at: 2026-05-08
closed_at: 2026-05-08

## Objective

Create a read-only adversarial scenario lab for the advisory Control Plane.

This slice runs declared in-memory scenarios through the current review-packet
and review-matrix chain, compares observed outputs to declared expectations,
and reports expectation drift without becoming an execution gate.

## Scope

Allowed paths:

- `experiments/control_plane_scenario_lab/`
- `experiments/lifecycle.toml`
- this trigger
- live operational projections and queue/archive docs needed for closure

Forbidden paths:

- `core/`
- `cli/`
- `extensions/`
- `.cerebro/`
- third-party target projects

## Non-Authority Contract

The lab must always declare:

```text
state_change = none
authority = non-authoritative
lab_is_not_permission = true
expectation_match_is_not_execution_approval = true
replay_pass_is_not_truth = true
must_not_execute_automatically = true
```

It must not:

- read manifests;
- write files;
- append logs;
- register memory;
- export OpenTelemetry;
- execute commands or tools;
- choose tasks;
- rank scenarios;
- schedule scenarios;
- grant permission;
- mutate canonical state;
- expose a CLI;
- become a runtime gate.

## Closure

Implemented `experiments/control_plane_scenario_lab/` as a read-only advisory
experiment.

The package adds:

- `ControlPlaneAdversarialProbe`;
- `ControlPlaneAdversarialFinding`;
- `ControlPlaneAdversarialProbeResult`;
- `ControlPlaneAdversarialReport`;
- `ControlPlaneScenario`;
- `ControlPlaneScenarioResult`;
- `ControlPlaneScenarioLabReport`;
- `builtin_control_plane_adversarial_probes(...)`;
- `builtin_control_plane_scenarios(...)`;
- `build_control_plane_adversarial_report(...)`;
- `build_control_plane_scenario_lab_report(...)`;
- adversarial JSON renderer;
- adversarial Markdown renderer;
- JSON renderer;
- Markdown renderer;
- expectation-drift reporting over packet/matrix outputs.

The built-in scenario battery covers:

- clean advisory review;
- missing capability assessment;
- runtime/canonical boundary blocked;
- network capability review required.

The built-in adversarial probes cover:

- replay authority drift;
- replay missing `decision_opened`;
- packet guardrail drift before matrix aggregation;
- duplicate matrix trace ids;
- `advisory_allow` non-permission preservation;
- assessment blocker laundering;
- readiness contradiction;
- capability decision contradiction;
- expectation laundering;
- replay-pass laundering;
- capability identity collision.

Validation:

- `python -m unittest discover -s experiments/control_plane_scenario_lab/tests -v`
  passed: 9 tests.
- `python -m unittest discover -s experiments/_lifecycle/tests -v` passed:
  18 tests.
- `python -m unittest discover -s tests -p "test_architecture.py" -v`
  passed: 51 tests.
- `python -m unittest discover -s tests -p "test_doc_governance.py" -v`
  passed: 19 tests.
- `python -m unittest discover -s experiments -v` passed: 611 tests.
- `python -m unittest discover -s tests -p "test_runtime_units.py" -v`
  passed: 25 tests.
- Full repository unit discovery under the Windows-safe temporary directory
  runner passed: 969 tests, 0 failures, 0 errors, 6 skipped.

No runtime, CLI, extension, `.cerebro/`, schema, persistent log, OpenTelemetry
export, external-tool adapter, MCP, Agents SDK, or third-party target mutation
occurred.
