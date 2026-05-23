# FORMAL RESUME TRIGGER - Control Plane Replay Eval Slice 1

status: consumed
created_at: 2026-05-08
closed_at: 2026-05-08

## Objective

Create the first advisory evaluator for Control Plane replay JSONL.

This slice answers one question: does a replay artifact still respect the local
control-plane contract, or does it contain incompleteness, malformed replay
evidence, or authority drift?

## Scope

Allowed paths:

- `experiments/control_plane_replay_eval/`
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

The evaluator must always declare:

```text
state_change = none
authority = non-authoritative
evaluation_is_not_permission = true
replay_pass_is_not_truth = true
must_not_execute_automatically = true
```

It must not:

- write files;
- append logs;
- register memory;
- export OpenTelemetry;
- execute commands or tools;
- select tasks;
- recompute readiness;
- grant permission;
- mutate canonical state;
- expose a CLI;
- become a runtime gate.

## Closure

Implemented `experiments/control_plane_replay_eval/` as a read-only advisory
experiment.

The package adds:

- `ControlPlaneReplayEvaluationIssue`;
- `ControlPlaneReplayEvaluation`;
- `evaluate_control_plane_replay_jsonl(...)`;
- JSON renderer;
- Markdown renderer;
- verdicts for valid replay, incomplete replay, failed replay contract, and
  authority drift.

Validation:

- `python -m unittest discover -s experiments/control_plane_replay_eval/tests -v`
  passed `9/0`.
- `python -m unittest discover -s experiments/_lifecycle/tests -v` passed after
  lifecycle registration.
- `python -m unittest discover -s tests -p "test_doc_governance.py" -v`
  passed.
- `python -m unittest discover -s tests -p "test_architecture.py" -v` passed.
- `python -m unittest discover -s tests -p "test_runtime_units.py" -v` passed.
- `python -m unittest discover -s experiments -v` passed `589/0`.
- AGENTS-equivalent full runner passed `969/0/0/6`.

No runtime, CLI, extension, `.cerebro/`, schema, persistent log, OpenTelemetry
export, external-tool adapter, MCP, Agents SDK, or third-party target mutation
occurred.
