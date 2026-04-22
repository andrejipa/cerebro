# General Work Model

This document defines the current generalization boundary for Cerebro.
It reflects implemented behavior.
It does not promise a chatbot-like interpretation layer and does not authorize fuzzy execution.

## Core Thesis

Cerebro now treats a task as a universal work unit when it can be represented as:

- canonical state
- an explicit task record
- constraints and dependencies
- an expected state transition
- optional governed execution
- optional verification
- audit trail and continuity

The runtime does not require every task to behave like a code mutation.
It distinguishes operational weight from natural-language domain labels.

## Universal Work Unit

A universal task in Cerebro remains the canonical plan task object:

- `id`
- `title`
- `status`
- `details`
- `depends_on`
- `working_set`
- `acceptance_criteria`
- `action_ids`

What changed is the interpretation layer above that object.
The runtime now derives a work profile from the task shape and runtime evidence instead of assuming every missing technical field is an error.

## Derived Work Profiles

Profiles are derived from canonical runtime state.
They are not stored as new schema keys.

### `light` + `state_only`

Use when the task can close by explicit state transition alone.

Structural signals:

- no registered verification commands
- no bounded `working_set`
- no recorded runtime actions
- no pending verification
- no pending approval
- no governed action kinds
- no dependency or acceptance structure that demands stronger control

Operational meaning:

- suitable for simple lists
- suitable for checklists
- suitable for lightweight personal organization
- the runtime must not emit technical warnings just because `working_set` or `acceptance_criteria` are empty

### `moderate` + `structured_state`

Use when the task is still state-driven, but already has explicit structure.

Structural signals:

- dependencies exist
- or state-level acceptance criteria exist
- but governed execution signals are still absent

Operational meaning:

- suitable for study plans
- suitable for structured routines
- suitable for ordered checklists or multi-step planning
- verify can still be state-level rather than command-level

### `heavy` + `governed_execution`

Use when the task touches runtime-governed execution surfaces.

Structural signals:

- verification commands are registered
- or `working_set` is defined
- or runtime actions exist
- or approval gates exist
- or pending verification exists
- or governed action kinds exist

Operational meaning:

- suitable for software work
- suitable for filesystem mutations
- suitable for any domain that needs strong approval, rollback, verify, or explicit bounded surfaces
- missing `working_set` and missing `acceptance_criteria` remain real diagnostics here

## Why This Design Won

Two designs were compared for the first generalization slice:

1. add explicit persisted domain and workload fields to canonical schema
2. derive work profile from the existing runtime shape

The derived approach won because it:

- adds no schema keys
- requires no migration
- preserves backward compatibility
- keeps `StateStore` as the single source of truth
- generalizes behavior without introducing a second taxonomy layer into canonical state

The persisted-schema alternative was rejected for now because it would add structural churn before the new concepts have enough operational evidence.

## Domain Adapter Contract

Generalization does not mean magical inference.
A domain adapter must translate a domain-specific input into canonical task state explicitly.

The currently implemented adapter is deterministic and shape-driven.
It supports:

- simple lists
- single concrete tasks
- explicit structured plans

It rejects vague or structurally inconsistent input instead of guessing.
It also stops on plausible multi-interpretation inputs and requires explicit external selection.
That stop condition now covers semantic ambiguity as well: broad work phrases that could honestly map to more than one canonical projection do not advance automatically.

Accepted adapter posture:

- explicit transformation into canonical task records
- explicit choice of lightweight, moderate, or heavy shape through structure
- no hidden authority over runtime policy
- no implicit command execution
- no fuzzy promotion of vague text into governed actions

Rejected adapter posture:

- prompt-like free interpretation without canonical output
- storing new truth outside `state.json` and the audit trail
- domain-specific shortcuts that bypass approval, rollback, or verify

## Examples

### Lightweight checklist

```json
{
  "goal": "Organizar semana",
  "summary": "Checklist simples",
  "tasks": [
    {
      "id": "task-001",
      "title": "Planejar treino",
      "status": "ready",
      "details": "Planejar treino",
      "depends_on": [],
      "working_set": [],
      "acceptance_criteria": [],
      "action_ids": []
    }
  ]
}
```

Derived profile:

- mode: `light`
- unit: `state_only`

### Moderate study plan

```json
{
  "goal": "Estudar algebra linear",
  "summary": "Plano semanal",
  "tasks": [
    {
      "id": "task-002",
      "title": "Capitulo 2",
      "status": "ready",
      "details": "Ler e resumir o capitulo 2",
      "depends_on": ["task-001"],
      "working_set": [],
      "acceptance_criteria": ["resumo concluido"],
      "action_ids": []
    }
  ]
}
```

Derived profile:

- mode: `moderate`
- unit: `structured_state`

### Heavy technical task

```json
{
  "goal": "Corrigir runtime",
  "summary": "Patch governado",
  "tasks": [
    {
      "id": "task-003",
      "title": "Atualizar exporter",
      "status": "ready",
      "details": "Patch governado",
      "depends_on": [],
      "working_set": ["extensions/status_export/exporter.py"],
      "acceptance_criteria": ["python -m unittest discover -s tests -v passes"],
      "action_ids": []
    }
  ]
}
```

Derived profile:

- mode: `heavy`
- unit: `governed_execution`

## Limits

Generalization is still disciplined.

- Cerebro is not a free-form conversational agent.
- Light tasks do not authorize implicit external execution.
- Moderate tasks do not skip auditability.
- Heavy tasks still obey approval, rollback, verify, and path discipline.
- Domain adaptation must remain explicit enough to be auditable.

If a use case cannot be represented as canonical state plus explicit state transitions or governed actions, it is outside the current generalization boundary.
