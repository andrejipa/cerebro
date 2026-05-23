# Context Vectors Oracle Eval — cerebro_self

- project_root: `D:\projetos_cli\cerebro`
- indexed_files: 360
- skipped_files: 5
- state_status: absent
- state_change: none
- oracle_cases: 4
- recall_at_1: 0.500
- recall_at_3: 1.000
- all_cases_passed_at_3: true
- scoring: deterministic sparse vector similarity plus bounded path/heading metadata cues
- authority: non-authoritative; advisory evidence only

## Verdict

All oracle cases found their expected paths within top 3.

## Cases

### live-system-state

- query: system state estado vivo atual suite gate posture freeze next_action runtime continuity
- expected_path: `docs/operations/SYSTEM_STATE.md`
- rank: 2
- passed_at_1: false
- passed_at_3: true
- rationale: Must find the live system snapshot rather than older historical ledgers.
- top_hits:
  - `AGENTS.md`
    - score: 0.5070
    - source_status: unregistered
    - heading: # Cerebro — Instruções para Agentes
  - `docs/operations/SYSTEM_STATE.md`
    - score: 0.4938
    - source_status: unregistered
    - heading: # System State
  - `docs/adr/ADR-001-single-state-file.md`
    - score: 0.4620
    - source_status: unregistered
    - heading: # ADR-001: Single State File
  - `tests/test_state_runtime_lock_service.py`
    - score: 0.4579
    - source_status: unregistered
    - heading: from __future__ import annotations
  - `cli/commands/approve.py`
    - score: 0.4535
    - source_status: unregistered
    - heading: """Implementation of the alpha-runtime approve command."""

### live-next-action

- query: opportunity map next item technology lane hybrid scoring next action
- expected_path: `docs/operations/OPPORTUNITY_MAP.md`
- rank: 2
- passed_at_1: false
- passed_at_3: true
- rationale: Must find the human-facing next-action projection.
- top_hits:
  - `docs/operations/codex_prompts/validation_decomposition.md`
    - score: 0.4359
    - source_status: unregistered
    - heading: # Codex Prompt — _validate_agent_runtime_block Structural Decomposition
  - `docs/operations/OPPORTUNITY_MAP.md`
    - score: 0.4321
    - source_status: unregistered
    - heading: # Opportunity Map
  - `experiments/context_vectors/tests/test_context_vectors.py`
    - score: 0.3988
    - source_status: unregistered
    - heading: from __future__ import annotations
  - `tests/test_state_store_digest.py`
    - score: 0.3973
    - source_status: unregistered
    - heading: from __future__ import annotations
  - `experiments/operational_signals/suggestions/rules.py`
    - score: 0.3964
    - source_status: unregistered
    - heading: # Conservative thresholds. Anything smaller is treated as noise because

### machine-queue

- query: observation center machine primary queue unresolved work single flight overlap policy
- expected_path: `docs/operations/observation_center.toml`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the machine-primary queue surface.
- top_hits:
  - `docs/operations/observation_center.toml`
    - score: 0.5151
    - source_status: unregistered
    - heading: # Status vocabulary:
  - `instrucoes/test_protocol.py`
    - score: 0.4083
    - source_status: unregistered
    - heading: from __future__ import annotations
  - `experiments/lifecycle.toml`
    - score: 0.3980
    - source_status: unregistered
    - heading: # Experiments Lifecycle Ledger
  - `docs/operations/SUPERSEDES_TRIPWIRE_MANUAL.md`
    - score: 0.3879
    - source_status: unregistered
    - heading: # Supersedes Mechanical Metadata Tripwire Manual
  - `experiments/recall_eval/tests/test_ranker.py`
    - score: 0.3878
    - source_status: unregistered
    - heading: from __future__ import annotations

### content-layering

- query: content aware filesystem analysis belongs in experiments extensions read only bootstrap_scan content blind
- expected_path: `docs/handoffs/HANDOFF_CONTENT_AWARE_ANALYSIS_LAYERING.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the handoff that codifies the current content-analysis layering rule.
- top_hits:
  - `docs/handoffs/HANDOFF_CONTENT_AWARE_ANALYSIS_LAYERING.md`
    - score: 0.7298
    - source_status: unregistered
    - heading: # Handoff — Content-Aware Analysis Layering
  - `docs/operations/FORMAL_RESUME_TRIGGER_BOOTSTRAP_SCAN_ENRICHMENT.md`
    - score: 0.6534
    - source_status: unregistered
    - heading: # Formal Resume Trigger — Bootstrap Scan Content-Signal Enrichment
  - `docs/handoffs/HANDOFF_READ_ONLY_EXPORTS_EXHAUSTED.md`
    - score: 0.5950
    - source_status: unregistered
    - heading: # Handoff: Read-Only Exports Exhausted
  - `experiments/context_discovery/content.py`
    - score: 0.5402
    - source_status: unregistered
    - heading: """Bounded content reading and heading-signal extraction.
  - `experiments/recall_eval/analysis/__init__.py`
    - score: 0.5175
    - source_status: unregistered
    - heading: from __future__ import annotations
