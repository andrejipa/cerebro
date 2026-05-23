# Local Artifact Retention Policy

This policy governs locally generated material that lives outside the canonical
runtime surface — primarily under `_local/` and any sibling directory created
at the repo root by an operational round.

It is operational hygiene, not runtime authority. It does not break the freeze
described in `FREEZE_POLICY.md` and does not introduce a second source of truth
about state.

## Scope

In scope:

- `_local/` and all of its descendants
- repo-root scratch directories such as `.tmp_*`, `.sandbox_*`, `.codex_tmp`,
  `.pytest_cache`, `.tracecov`, `.wrangler`
- repo-root or parent-level local backups such as `cerebro-workingtree-backup-*`,
  `cerebro.zip`, `cerebro-backup-*.git`, `cerebro-postrewrite-*.git`
- repo-root cleanup quarantines such as `_local_cleanup_quarantine_<DATE>/`
- locally captured evidence files (PDFs, CSVs, XLSX, archives) not yet routed
  to an external archive

Out of scope:

- `.cerebro/` artifacts — governed by `cerebro validate --retention-report`,
  `--retention-apply`, and the canonical retention rules described in
  `OPERATIONS_BASELINE.md`
- the canonical event log — governed by `parallel_approach_consolidated`
  preservation and the canonical event-log retention rules
- Git history — governed by Git itself
- canonical sources registered through `import-context`
- code under `core/`, `cli/`, `extensions/`, `tests/`, `experiments/`

This policy and the canonical retention surface are complementary. They never
overlap and never reference each other as authority.

## Why This Exists

The cleanup round on 2026-05-07 (`CLEANUP_PROPOSAL_2026-05-07.md`) found that
the workspace carried roughly 13 GiB of weight, almost all of it operational
residue: regenerable scratch caches, a full mirror backup without an
expiration date, validation sandboxes preserved verbatim with their build
environments, and source documents (PDFs, CSVs) sitting next to runtime code.

The pattern was consistent: artifacts entered the local surface without a
declared lifecycle. Once in, they had no owner, no expiration, no delete rule,
and no restore rule. They turned into a parallel memory — useful at birth,
unsafe to remove later because nobody could decide if removing them would
break something.

This policy fixes that gap. It adds a minimum contract every locally generated
artifact must declare so the next operational round can remove it safely or
preserve it deliberately, without ad hoc archaeology.

## Artifact Class Contract

Every locally generated artifact declares one class with one contract.

### Classes

`scratch` — regenerable cache or temporary intermediate output of a producer
that still exists. Examples: `.tmp_perf_cache/` recall fingerprints,
`.tmp_sandbox/` workspaces, `.pytest_cache/`, sandbox temp dirs created by the
AGENTS-equivalent runner. Default lifetime: removed at end of round, or by the
next cleanup sweep at end of week. Restore rule: regenerate by rerunning the
producer.

`quarantine` — material removed from the active path but preserved for
rollback. Example: `_local_cleanup_quarantine_<DATE>/<phase>/`. Default
lifetime: 14 days after both an AGENTS-equivalent gate and the broken-reference
tripwire stay clean. Restore rule: same-volume `Move-Item` back to the
original parent path.

`evidence` — source documents that prove an external claim and cannot be
regenerated. Examples: audit PDFs, fiscal CSVs, third-party reports, raw
exports from regulator systems. Default lifetime: indefinite, but the canonical
home is an external archive, not the repo. Restore rule: external archive plus
a small repo-side manifest pointing at the archive.

`report_capsule` — preserved analytical output that may be useful for future
historical comparison. Examples: closing memorials, audit narratives, round
postmortems extracted from a sandbox before its environment is discarded.
Default lifetime: indefinite if material to project history; otherwise 90 days
followed by a review. Restore rule: regeneration is usually impossible — the
preservation choice is the artifact.

`backup` — local snapshot of repo state created for safety during a specific
operation. Examples: `cerebro-workingtree-backup-<DATE>/`, `cerebro.zip`,
`cerebro-backup-<DATE>.git`. Default lifetime: until the operation that
motivated the backup closes, plus 30 days; hard cap 90 days. Restore rule:
extract or copy back; in most cases redundant with Git history.

### Required Fields

Every class instance declares its contract in a `MANIFEST.md` adjacent to the
artifact, or as the artifact itself when it is a single file. The contract uses
these fields:

```
artifact_class      : scratch | quarantine | evidence | report_capsule | backup
owner               : human or trigger/slice id responsible for the artifact
created_by          : trigger/slice/operation id, or "manual" with a reason
created_at          : ISO date
retention_until     : ISO date, or "indefinite-with-review-on:<DATE>"
delete_rule         : the condition and procedure for removal
restore_rule        : the procedure for bringing it back
canonical_reference : yes | no
```

If `canonical_reference = yes`, the artifact must not be deleted by sweep.
The canonical doc that cites it must be edited first to remove the reference,
and only after that can the artifact follow its class lifecycle.

## Mandatory Rules

1. No artifact enters `_local/` without a manifest. A new `_local/`
   subdirectory or repo-root scratch directory must declare its class and
   contract in the same operational round that creates it.

2. No artifact in `_local/` is canonical. `_local/` is operational scratch.
   Canonical state lives in `.cerebro/`, canonical docs in `docs/`, canonical
   code in `core/`, `cli/`, `extensions/`, `tests/`, `experiments/`. Any
   reference from a canonical surface to a `_local/` path must be replaced
   before that canonical surface is closed.

3. Retention is manual, not automatic. Aligned with `OPERATIONS_BASELINE.md`.
   No background sweep, no threshold-driven autodelete. Removal is always a
   deliberate operational round with pre-checks, gate, tripwire, and human
   reconfirmation.

4. Quarantine before delete. Any cleanup pass moves material into
   `_local_cleanup_quarantine_<DATE>/<phase>/` first. Final deletion happens
   only after the retention window passes with the gate green and the tripwire
   clean.

5. Evidence has its canonical home outside the repo. PDFs, CSVs, third-party
   reports, regulator exports go to an external archive (for example
   `D:\projetos_cli\arquivo_<project>\`). The repo carries only a small
   manifest pointing at the archive, never the bytes.

6. Local backups have an explicit expiration. A `cerebro-workingtree-backup-*`
   or `cerebro.zip` declares the operation that motivated it and a hard-cap
   retention. When the motivating operation closes and 30 days pass, the
   backup goes to quarantine; at the hard cap, it is removed.

7. Sandbox preservation captures reports, not environments. When a validation
   sandbox closes, only its narrative artifacts (memorials, READMEs, analysis
   markdown, audit reports) are extracted into a
   `_local/cleanup_preserved_reports_<DATE>/` capsule with a manifest. The
   build environment (`node_modules/`, embedded `.cerebro/`, scratch dirs,
   build outputs) does not survive.

## Tripwire

A lightweight advisory check denounces drift against this policy. The tripwire
surfaces drift to the next operational round; it never deletes anything
autonomously and never gates the suite.

Conditions the tripwire should flag:

- `_local/` total size exceeds a documented threshold (default `1 GiB`)
- a top-level entry in `_local/` exists for at least 7 days without a
  `MANIFEST.md` or contract declaration
- a new `node_modules/`, `.zip`, `.git` (bundle), or `.tmp_*` directory
  appears at repo root outside the documented set
- a quarantine directory under `_local_cleanup_quarantine_<DATE>/` exceeds its
  declared `retention_until` without resolution

Implementation must stay outside the runtime contract: no extension status
inside `core/`, no schema changes, no influence on `validate` or `analyze`.
The tripwire is a script run on demand or at the start of an operational
round, and its output is operational signal only.

Current advisory implementation:

```
powershell -NoProfile -ExecutionPolicy Bypass -File docs/operations/LOCAL_ARTIFACT_TRIPWIRE.ps1
```

The script always reports as `authority = advisory-only`, emits findings as
operator signal, and does not delete, move, rewrite runtime state, or turn
findings into a failing test gate.

## Relation to Canonical Retention

The canonical retention surface — `cerebro validate --retention-report`,
`cerebro validate --retention-apply`, the canonical event-log retention rules,
and `.cerebro/trash/retention/` — governs material inside `.cerebro/`. It is
the source of truth for runtime artifact lifecycle.

This policy explicitly does not apply to that surface and does not redefine it.
The two surfaces sit on opposite sides of the runtime boundary. A future
proposal that tried to merge them, or to make either one read or rewrite the
other, would create a second source of truth and must be rejected.

## Freeze Posture

This document is operational hygiene. It declares contracts and rules for
local material; it does not add a runtime feature, does not change
`validate`, `analyze`, `state.json`, or session policy, and does not introduce
a new authority surface.

It therefore does not break the freeze in `FREEZE_POLICY.md`.

A later proposal to make tripwire enforcement runtime-gating — for example to
fail the suite on `_local/` policy drift — would be runtime feature growth
and must follow the Formal Resume Trigger and Resume Protocol in
`FREEZE_POLICY.md`.

## Out Of Scope

- `.cerebro/` artifacts and any retention behavior governed by
  `OPERATIONS_BASELINE.md`
- Git history
- canonical sources registered via `import-context`
- code under `core/`, `cli/`, `extensions/`, `tests/`, `experiments/`
- decisions about external archive layout, backup tooling, or storage
  topology beyond declaring that evidence has its home outside the repo
