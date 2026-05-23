# Runbook — Full Gate for Context Discovery Slice 1

Mechanical runbook for promoting
`FORMAL_RESUME_TRIGGER_CONTEXT_DISCOVERY_EXT_SLICE_1` from
`implementation complete` to `consumed / completed`.

Run from the Cerebro repository root on the target Windows machine in an
activated PowerShell session with the local venv enabled.

## 1. Preflight — check and clear any stale git lock

```powershell
# 1.1 Check
if (Test-Path .git\index.lock) {
  Write-Host "index.lock present; verifying no git process is running..."
  Get-Process git -ErrorAction SilentlyContinue
} else {
  Write-Host "no stale lock; proceed"
}

# 1.2 Remove ONLY if no git process is active
# (confirm the Get-Process output above returned nothing before running this)
Remove-Item .git\index.lock
```

If any `git` process is listed, stop and wait for it to finish. Do not
remove the lock while a real git operation is in flight.

## 2. Run the full AGENTS-equivalent gate

Paste the AGENTS.md runner verbatim from `AGENTS.md` "Verificação obrigatória
antes de qualquer trabalho". It wraps the session with the `TEMP`, `TMP`,
`CEREBRO_SESSION_CLAIMS_DIR`, `CEREBRO_SESSION_LIVE_PROOFS_DIR`, and
`tempfile.mkdtemp` overrides needed on Windows.

Capture the final `SUMMARY` line, which has the shape:

```
SUMMARY ran=<N> failures=<F> errors=<E> skipped=<S>
```

Also run the architecture gate directly for a clean per-file count:

```powershell
python -m unittest tests.test_architecture -v
```

And the new derived-track tests:

```powershell
python -m unittest experiments.context_discovery.tests.test_discovery -v
```

## 3. Interpret outcome

### 3a. Green — full gate passed

Expected shape:

- `failures=0 errors=0` in the AGENTS-equivalent `SUMMARY`
- architecture gate: `51` tests, `0` failures
- `experiments/context_discovery/tests/test_discovery`: `12` tests, `0` failures
- `tests/test_bootstrap_scan`: baseline count, `0` failures

Then promote:

1. Edit
   `docs/operations/FORMAL_RESUME_TRIGGER_CONTEXT_DISCOVERY_EXT_SLICE_1.md`
   Status section: replace the
   `implementation complete on 2026-04-23; formal closure BLOCKED …` line
   with `consumed / completed on <YYYY-MM-DD>` and append the final gate
   numbers to the `objective result:` block.
2. Edit `docs/operations/SYSTEM_STATE.md` — replace the "BLOCKED pending the
   full AGENTS-equivalent suite" phrasing with a "Formal resume trigger
   consumed on <DATE>" entry and record the final full-suite numbers.
3. Edit `docs/operations/OPPORTUNITY_MAP.md` — mirror the same change.
4. Mark task #7 in the session tracker as completed.

### 3b. Red — failures attributable to this slice

A failure is attributable to this slice if and only if the failing test
lives under `experiments/context_discovery/` or explicitly names a symbol
from that package.

Action:

1. Do NOT promote the trigger.
2. Capture the full failure output into a comment on the trigger doc under
   a new `## Verification Block` section.
3. Rollback choice:
   - revert the whole `experiments/context_discovery/` tree and the
     `experiments/lifecycle.toml` entry (`git restore -- experiments/`
     scoped to the new paths plus the lifecycle file)
   - OR, fix-forward by opening a follow-on slice whose scope is narrowly
     the fix; do not expand scope beyond this.

### 3c. Red — failures NOT attributable to this slice

If the failing tests match any of the known sandbox-environment categories
(`Operation not permitted` on `.tmp_live_proofs/`, `No module named
tomllib`, `not a git repository`, `windows_credential_store`), treat them as
environmental blockers.

Action:

1. Do NOT promote the trigger.
2. Document the environmental blocker in
   `docs/operations/BUG_REPORT.md` with the exact failing test names and
   the reason each is environmental, not a slice defect.
3. Fix the environment first. Typical candidates:
   - install `tomli` and wire it as `tomllib` on Python 3.10 (or upgrade to
     Python 3.11+)
   - ensure `.tmp_live_proofs/` is owned by the current user and supports
     file removal
4. Re-run step 2 after the environment is fixed. Only then apply 3a.

## 4. Do not open new slices

Per AGENTS.md, no new formal slice starts until this one closes cleanly or
is documented as blocked. Task #7 gates any new trigger.
