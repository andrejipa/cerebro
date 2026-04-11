# Cerebro Local Checkpoint

Minimal local checkpoint CLI for agent-assisted execution.

## What It Does

- stores a single local state file in `.cerebro/state.json`
- registers explicit context sources with SHA-256 hashes
- validates that registered sources still match
- stores a short operational checkpoint
- opens a local session on `resume`

## What It Does Not Do

- it does not model the whole project
- it does not scan the repository
- it does not infer context automatically
- it does not replace Git, issues, or human communication

## Install

```powershell
pip install -e .
```

## Basic Flow

```powershell
cerebro init
cerebro import-context --files path\\to\\file.txt
cerebro checkpoint --goal "..." --summary "..." --next-step "..."
cerebro resume
cerebro validate
```

Normal daily flow:

- start with `cerebro resume`
- finish with `cerebro checkpoint`

## Runtime Files

- `.cerebro/state.json`
- `.cerebro/session.local.json`
- `.cerebro/logs/events.jsonl`

Only the first two affect runtime behavior.
