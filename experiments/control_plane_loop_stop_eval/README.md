# Control Plane Loop Stop Eval

`control_plane_loop_stop_eval` is a read-only, non-authoritative evaluator for
caller-supplied loop-frame records.

It answers one narrow question: whether a loop frame's claimed continuation or
stop posture is coherent with already-supplied validation, queue-frontier,
trigger/stop, agent-focus, and recent-round evidence. It detects unsafe
continuation after failed validation, met stop conditions, blocked/waiting queue
heads, missing trigger evidence, multiple frontiers under single-flight,
agent/head focus drift, repeated no-progress evidence digests, hidden blockers,
and authority-laundering wording.

Boundary:

- `state_change: none`
- non-authoritative advisory control-plane loop stop eval only
- loop stop eval is not permission
- loop stop status is not truth
- loop stop eval is not execution approval
- loop stop eval is not a scheduler
- loop stop eval is not a runtime gate
- loop stop eval is not a state store
- findings are not truth
- must_not_execute_automatically

The package does not read `.cerebro/`, `docs/operations`, queue files, state
files, approval stores, evidence stores, tool registries, target files, runtime
stores, logs, locks, or sessions. It does not write files, execute commands,
mutate state, validate live state, rank work, choose a next action, schedule
work, dispatch agents, approve execution, grant permission, call tools, expose
adapters, or become a canonical gate.
