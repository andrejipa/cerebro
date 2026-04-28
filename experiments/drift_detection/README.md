# drift_detection (experimental derived track)

AST-based structural drift detector for Cerebro core modules.

Captures a baseline snapshot of normalized AST hashes for files in `core/`,
`cli/`, and `extensions/`, then compares future scans to the baseline to
identify added, modified, or removed Python modules.

## Boundaries

- derived, non-authoritative, observability-only
- read-only over Python source files
- no writes under `.cerebro/`
- no target-project mutation
- no network calls or external services
- no imports from `cli/`
- never calls `import-context`
- never registers or removes sources

## Usage

```
# Capture current state as baseline
python -m experiments.drift_detection.cli baseline

# Detect drift since baseline
python -m experiments.drift_detection.cli detect

# Show last report summary
python -m experiments.drift_detection.cli status
```

## Output

Produces `drift_report_latest.md` and `drift_report_latest.json` under
`experiments/drift_detection/`. Both are observability artifacts — they
describe structural change but never decide whether the change is valid.

## Staleness Scoring

The `staleness_scorer` module provides deterministic scoring for how stale
a registered source may be, based on elapsed time and structural change
count. See `staleness_scorer.py` for the scoring contract.
