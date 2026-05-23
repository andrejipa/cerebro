# Formal Resume Trigger — Context Discovery Derived Track, Slice 1

## Status

- `proposed on 2026-04-23`
- `corrected on 2026-04-23 — path moved from extensions/ to experiments/ after a second architecture-gate check revealed tests.test_architecture.test_extensions_do_not_read_files_or_enumerate_directories_directly forbids any file read in extensions/; experiments/ is the approved precedent for content-aware non-authoritative analysis (see experiments/recall_eval and experiments/operational_signals)`
- `accepted on 2026-04-23 by André (explicit message: "aceito tudo, desde que nao tenha chance de quebrar tipo a C") — acceptance is recorded here as the audit anchor for the slice`
- `implementation complete on 2026-04-23; formal closure BLOCKED pending the full AGENTS-equivalent suite running green in the target Windows environment — this is an environmental block, not a defect in the slice`
- `consumed / completed on 2026-04-23 — full AGENTS-equivalent gate ran green on the target Windows environment: 923 tests, 0 failures, 0 errors, 6 skips; architecture gate 51/51, experiments/context_discovery/tests 12/12, tests/test_bootstrap_scan 17/17 baseline unchanged; all closure criteria met`
- objective result:
  - new directory `experiments/context_discovery/` created with `__init__.py`, `README.md` declaring non-authoritative boundary, `content.py` (bounded content reading + role signal extraction), `discovery.py` (pipeline over the public `StateStore` API plus bounded filesystem scan), `report.py` (stable-shape Markdown rendering), and `tests/test_discovery.py`
  - lifecycle ledger updated: new `[[experiment]]` entry in `experiments/lifecycle.toml` with `name = "context_discovery"`, `status = "active"`, `started = "2026-04-23"`, next review due 2026-07-22
  - architecture gate: green at `51` tests, `0` failures, `0` errors (no architecture invariant touched)
  - new `experiments/context_discovery/tests/test_discovery.py`: green at `12` tests, `0` failures, `0` errors; covers candidates lifted by content-scope heading, drift detection on registered SHA-256 mismatch, missing registered source detection, zero runtime or target-project mutation, no-registered-state note emission, invalid root rejection, invalid candidate-limit rejection, binary-file skip, non-textual-suffix skip, per-file byte and line caps, each content role family detected, and stable Markdown report shape
  - `tests/test_bootstrap_scan.py`: green at `17` tests, `0` failures (baseline — no change, since the slice does not touch `cli/commands/bootstrap_scan.py`)
  - full AGENTS-equivalent suite: **EXECUTED AND GREEN** on 2026-04-23 in the target Windows environment — 923 tests, 0 failures, 0 errors, 6 skips; runbook `docs/operations/RUNBOOK_GATE_CONTEXT_DISCOVERY_SLICE_1.md` followed successfully
- layering rule consolidated in handoff: `docs/handoffs/HANDOFF_CONTENT_AWARE_ANALYSIS_LAYERING.md` — *"Content-aware filesystem analysis belongs in `experiments/`; `extensions/` project canonical state through public APIs; `bootstrap_scan` remains assistive-only and content-blind."*
- closure block (open item for André on Windows): follow `docs/operations/RUNBOOK_GATE_CONTEXT_DISCOVERY_SLICE_1.md` step by step
  - remove the stale `.git/index.lock` left by an interrupted git process in this sandbox
  - run the full AGENTS-equivalent runner documented in `AGENTS.md`
  - if green, update this trigger's Status line to `consumed / completed on <DATE>` and append the final full-suite numbers; if red for any reason unrelated to this slice, document the blocker instead
- boundary after implementation (still open until the gate runs):
  - `core/`: closed
  - `cli/`: closed
  - `tests/`: closed
  - `tests/test_architecture.py`: untouched
  - `.cerebro/`: untouched in any code path of the new extension
  - `experiments/context_discovery/`: active, non-authoritative, reviewed by 2026-07-22

## Classification

- `assistive-only derived track under experiments/, same approved shape as experiments/recall_eval and experiments/operational_signals`
- not a runtime integration
- not a new canonical surface
- not an auto-registration of sources
- not a replacement for `bootstrap-scan`; content-aware analysis lives here instead of inside the scanner
- not an extension under `extensions/`; that namespace is restricted to read-only projectors over the public core API and is architecturally forbidden from reading files

## Why This Trigger Exists

- The preceding trigger `FORMAL_RESUME_TRIGGER_BOOTSTRAP_SCAN_ENRICHMENT.md` was withdrawn because `cli/commands/bootstrap_scan.py` carries a formal architecture-gate invariant that forbids file-content reads. That invariant is good and stays.
- The operator gap it tried to address — context curation load in new projects, drift awareness over time, and continuous visibility into what changed in the territory versus what is currently registered — is real and still open.
- The architecturally clean way to close that gap is to add a parallel read-only derived track (a projector over `.cerebro/state.json` plus target-project files) that is allowed to do content-aware analysis because it has no bounded-time invariant and no authoritative role.
- This is the same pattern already approved in the repository: `experiments/recall_eval/` and `experiments/operational_signals/` are non-authoritative derived tracks that produce reports outside the canonical runtime. This slice adds one more under `extensions/` for the same reason.

## Non-Goals

- no automatic registration of sources in `.cerebro/state.json`
- no mutation of any runtime file
- no new CLI subcommand under `cli/commands/` (the extension may expose a runnable entrypoint, but it is not promoted into the canonical CLI surface)
- no change to `cli/commands/bootstrap_scan.py`
- no change to `tests/test_architecture.py` (the bootstrap-scan invariant stays)
- no change to any `core/` module
- no change to `.cerebro/` directory contents from the extension code path
- no promotion of any output of this extension into authoritative truth

## Allowed Scope

- create the directory `experiments/context_discovery/` with its own `__init__.py`, module files, and a local `README.md` that states the non-authoritative boundary in one paragraph
- implement an isolated content-aware discovery helper under that directory that, given a target project root and a read of the registered sources from `.cerebro/state.json`, produces a human-readable report with three sections:
  - *candidates not registered*: files that look relevant (based on path, filename, and bounded content signals) but do not appear in the current registered-sources set
  - *drift on registered sources*: registered sources whose content head has changed shape substantially (for example, a file that used to start with a project-scope heading and now starts with a changelog, or a registered file whose content is now empty or effectively binary)
  - *missing registered sources*: registered sources that are no longer present in the target project
- add proportional tests under a path the architecture gate allows for extensions (mirroring the layout used by the existing derived tracks in `experiments/`, for example `experiments/context_discovery/tests/`)
- update `docs/operations/SYSTEM_STATE.md` and `docs/operations/OPPORTUNITY_MAP.md` to record the new derived track as active and non-authoritative at closeout
- update the top-level `README.md` only to add a one-sentence reference to the new derived track under the "Evolution State" section, using the same phrasing convention the existing derived tracks already use

## Prohibited Scope

- any write under `.cerebro/` from the extension code path
- any change in `core/`
- any change in `cli/`
- any change in `tests/test_architecture.py` or any canonical runtime test
- any new top-level CLI command, flag, or subcommand tied to this extension
- any unbounded content read (a hard per-file byte cap and per-file line cap must be enforced explicitly)
- any network I/O
- any read of files outside the target project root
- any attempt to re-register, mutate, or propose changes to `.cerebro/state.json` beyond printing observations
- any coupling between this extension and the authoritative runtime that would let its output be treated as truth by `validate` or `analyze`

## Required Invariants

- the extension is non-authoritative: before and after any invocation, `.cerebro/` must be byte-identical
- the extension is read-only with respect to the target project apart from reading content heads
- binary files and oversized files are never fully read; bounded per-file caps are explicit
- the output is strictly a report, not an action proposal the runtime can consume
- the canonical runtime does not import any module from `experiments/context_discovery/`
- the architecture gate stays green without any modification to its tests
- the bootstrap-scan assistive-only architecture invariant stays intact and is not relaxed by this slice

## Stop Conditions

- any need to touch `core/`, `cli/`, or `tests/test_architecture.py`
- any need to register or mutate `.cerebro/state.json`
- any architectural pressure to make this extension authoritative or part of the canonical runtime surface
- any test failure in the full AGENTS-equivalent suite or in the architecture gate
- any attempt to weaken tests or relax invariants in order to pass
- any proposal that the report should be machine-consumed by `validate` or `analyze` without a separate, explicit, formally-triggered integration slice

## Acceptance Gate (Closeout Criteria)

- full AGENTS-equivalent suite: green, no regression against the baseline at slice start
- architecture gate: green, no modification to its tests
- new `experiments/context_discovery/tests/` suite: green, covering at least the three report sections above and at least one negative case proving no runtime or target-project mutation occurs during execution
- manual smoke: running the extension against the Cerebro repo root itself produces a report that mentions zero registered sources when no `.cerebro/state.json` is present, and does not create `.cerebro/`
- `SYSTEM_STATE.md` and `OPPORTUNITY_MAP.md` updated with a short note that this trigger consumed and the new extension stays explicitly non-authoritative and advisory-only
- this trigger file updated to `consumed / completed` with the final gate numbers
