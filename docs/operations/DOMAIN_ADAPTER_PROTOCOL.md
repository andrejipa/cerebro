# Domain Adapter Protocol

This document records the currently accepted adaptation protocol for non-technical work in Cerebro.
It reflects the adapter-only generalization slice implemented in the runtime.

## Purpose

The adapter layer exists to convert domain-specific inputs into canonical Cerebro state without changing the canonical schema for every new domain.

The adapter is responsible for:

- normalizing human input into explicit task records
- choosing the correct operational weight through structure
- preserving auditability
- refusing vague input when no disciplined canonical translation exists

The current public entrypoint is the `plan` command through:

- `--input-text`
- `--input-file`
- `--input-kind auto|list|task|structured`

The adapter is deterministic and fail-closed.
It does not execute text.
It only emits canonical plan-compatible data or rejects the input.
When `--input-kind auto` finds more than one plausible interpretation, it does not choose.
It emits an ambiguity block and requires explicit rerun with one selected `--input-kind`.
This now includes both structural ambiguity and semantic ambiguity.

## Accepted Input Kinds

### `list`

Accepted forms:

- comma-separated items
- semicolon-separated items
- multi-line bullet or numeric lists

Examples:

- `comprar arroz, leite, pao`
- `1. revisar agenda`
- `- pagar contas`

Behavior:

- one canonical lightweight task per normalized item
- duplicate normalized items are rejected
- vague or non-actionable fragments are rejected instead of being promoted into tasks
- no verification commands are inferred

### `task`

Accepted form:

- exactly one non-empty line representing one concrete task

Examples:

- `Revisar agenda semanal`
- `- Comprar arroz`

Behavior:

- a single bullet line is normalized into a single task title without the marker
- vague commands such as `organiza isso` are rejected, including trailing punctuation variants
- no verification commands are inferred

### `structured`

Accepted grammar:

- `goal: ...`
- `summary: ...`
- `verify: ...`
- `task: TITLE | key=value`
- `- TITLE | key=value`

Supported task metadata keys:

- `id`
- `depends`
- `working_set`
- `acceptance`

Behavior:

- duplicate ids are rejected
- unknown dependencies are rejected
- self-dependencies are rejected
- repeated `goal:` or `summary:` are rejected
- unsupported metadata keys are rejected
- task titles still go through vagueness rejection
- `verify:` is rejected unless at least one structured task declares a bounded `working_set`

### `auto`

`auto` chooses only by safe shape:

- explicit structured markers => `structured`
- multi-item separators or bullet list => `list`
- otherwise => `task`

Important safety rule:

- a pipe (`|`) only upgrades a bullet line into structured parsing when the post-pipe segments are valid supported `key=value` metadata
- comma-separated prose that contains vague or non-actionable fragments is rejected instead of being guessed as a list

If the shape stays ambiguous after this routing, the adapter rejects instead of guessing.

Current ambiguity rules exposed to the operator:

- comma or semicolon single-line input with multiple actionable fragments => explicit `list` or `task` selection required
- single bullet line => explicit `task` or `list` selection required
- inline supported metadata on a single line without explicit structured marker => explicit `structured` or `task` selection required
- short coordinated compound instructions such as `review and merge` => explicit rewrite or `task` selection required
- broad semantic phrases such as `organizar semana`, `arrumar backlog`, `revisar projeto`, `planejar viagem` or `preparar fechamento do mês` => block when they plausibly fit more than one canonical projection (`task`, `list`, `structured`)

Semantic ambiguity is not solved by guessing.
The adapter now reports:

- ambiguity type
- ambiguity level
- competing interpretations
- impact of each interpretation
- the explicit resolution path required to continue

## Canonical Output

Every adapter must produce the same canonical plan task shape already used by the technical runtime:

- `id`
- `title`
- `status`
- `details`
- `depends_on`
- `working_set`
- `acceptance_criteria`
- `action_ids`

The adapter may also populate:

- plan `goal`
- plan `summary`
- command registry when the domain truly needs governed verification

It must not invent new runtime truth outside canonical state.

## Operational Weight Selection

Adapters choose weight through structure, not prose labels.

### Lightweight

Use for lists, simple checklists, lightweight personal organization, and low-friction tracking.

Adapter shape:

- `working_set = []`
- `acceptance_criteria = []`
- `depends_on = []` unless ordering is real
- no verification commands

### Moderate

Use for structured plans, study schedules, routines with explicit ordering, and state-level completion criteria.

Adapter shape:

- dependencies when order matters
- acceptance criteria when completion should be explicit
- still no governed execution surface unless truly needed

### Heavy

Use only when the task needs governed execution.

Adapter shape:

- bounded `working_set`
- verification commands when command-level proof is required
- approval/rollback pressure only when actual runtime actions demand it

## Rejected Adapter Behaviors

The following remain invalid:

- classifying by vague prose alone
- inventing `working_set` metaphors for non-technical tasks just to satisfy old heuristics
- forcing lightweight tasks through verification commands with no operational value
- hiding free-form advice as canonical task state
- letting adapters bypass approval, verify, or rollback for heavy work

## Accepted Example Mappings

### Shopping or simple list

Input:

- goal: buy groceries
- items: bananas, rice, coffee

Canonical translation:

- one lightweight state-only task per item or one task per store pass

### Study plan

Input:

- goal: finish chapter sequence
- units: chapter 1, chapter 2, exercises

Canonical translation:

- moderate structured-state tasks
- dependencies when sequence is real
- acceptance criteria only when they clarify completion

### Technical project

Input:

- goal: patch runtime bug
- files, commands, test gates

Canonical translation:

- heavy governed-execution tasks
- bounded `working_set`
- explicit verification commands

## Current Limits

This protocol intentionally does not include:

- free-form natural-language parsing into canonical state
- persistent domain registries
- custom schema branches per domain
- inferred external execution from vague goals
- fuzzy extraction of hidden goals, priorities, deadlines, or dependencies from prose

Those steps remain deferred until they can be justified without degrading the technical core.
