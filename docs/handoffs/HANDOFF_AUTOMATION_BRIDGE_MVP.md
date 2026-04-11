# Handoff: Automation Bridge MVP

- State: minimum-safe external integration designed and initialized
- Classification: `integration`

## Problem

Current real flow still has one mechanical loop:

1. a decision or prompt is produced outside Codex
2. the text is copied manually into Codex CLI or the VS Code extension
3. execution happens locally
4. the result is brought back manually for the next round

The bridge exists to remove that copy-paste loop without changing runtime truth, bootstrap authority, or project state semantics.

## Non-Negotiable Constraints

The bridge may not:

- touch the core
- alter `analyze`, `validate`, `state.json`, schema, or session policy
- write inside `.cerebro/`
- register `sources`
- call `import-context` automatically
- create a second source of truth
- turn executor logs into project memory
- open a new semantic layer implicitly

## Architecture Options

## Option 1: Local Orchestrator With Agents SDK Plus Codex Executor Over MCP

- What it solves:
  - rich multi-agent orchestration with formal handoffs, tools, and guardrails
  - strong fit if the coordinator server should own agent routing, approvals, and state
- Why it is plausible:
  - the Agents SDK is the recommended path when the application owns orchestration, tool execution, approvals, and state
  - Codex CLI, IDE, and app share configuration, and Codex can be integrated with MCP-based workflows
- Effort:
  - medium to high
- Main risks:
  - more moving parts before the workflow shape is fully proven
  - higher chance of creating a second coordination runtime too early
  - more hidden state unless logging and handoff discipline are tightened immediately
- Verdict:
  - technically valid, but too heavy for the first bridge

## Option 2: Deep Integration Through Codex App Server

- What it solves:
  - rich client integration with threads, approvals, streamed events, and conversation lifecycle
  - strongest fit when building a product-grade custom client around Codex
- Why it is plausible:
  - app-server powers rich clients such as the VS Code extension
  - it exposes thread, turn, command, file-change, and approval primitives directly
- Effort:
  - high
- Main risks:
  - deep coupling to Codex conversation/runtime APIs before the bridge problem is even proven
  - wider approval and auth surface
  - overbuild for a workflow that currently only needs to replace copy-paste and capture logs
- Verdict:
  - not the right first move

## Option 3: Minimal Local Orchestrator Using `codex exec`, Structured Logs, And Disposable Run Dirs

- What it solves:
  - replaces the mechanical copy-paste loop immediately
  - keeps the coordinator outside the product runtime
  - gives explicit, auditable handoff artifacts per round
- Why it is plausible:
  - `codex exec` is the supported non-interactive surface for scripted use
  - it supports `--json` JSONL event output, `--output-schema` for structured final responses, `-o` for last-message capture, `-C` for explicit working root, and `--ephemeral` to avoid hidden session persistence
  - CLI, IDE, and Codex app share configuration layers, so behavior stays aligned with existing local use
- Effort:
  - low
- Main risks:
  - less expressive than SDK/app-server for long-running orchestration
  - approval handling must stay explicit and conservative
- Verdict:
  - recommended primary architecture

## Recommendation

- Recommended architecture:
  - Option 3, a minimal local orchestrator built around `codex exec`

## Reason

- It replaces a material part of the manual loop now.
- It stays closest to the already validated local usage surface.
- It is the most auditable path because every run can live in a disposable directory with explicit request, prompt, event stream, final structured output, and stderr log.
- It does not force a second orchestration runtime before the workflow has been proven in practice.

## Operational Flow

1. Human coordinator writes or triggers one task.
2. Orchestrator creates one disposable run directory outside `.cerebro/`.
3. Orchestrator records:
   - task id
   - target project root
   - explicit context paths
   - role or round label
   - approval mode for this run
4. Orchestrator builds a context packet and a prompt envelope.
5. Orchestrator invokes Codex as the subordinate executor with:
   - explicit project root
   - structured output schema
   - JSONL event capture
   - ephemeral mode when hidden session persistence is not wanted
6. Executor reads, inspects, optionally runs safe commands, and returns a structured result.
7. Orchestrator captures:
   - request metadata
   - prompt sent
   - raw JSONL event stream
   - final structured result
   - stderr and exit status
8. Human or higher-level coordinator decides:
   - close the round
   - ask for another round
   - escalate to explicit approval for write-capable work
9. If the work affects Cerebro governance, the coordinator updates board or handoffs explicitly. The bridge never treats those updates as automatic truth.

## Components

- `task envelope`: one explicit task payload
- `context packet builder`: packages project root and explicit context paths
- `Codex executor adapter`: shells out to `codex exec`
- `result schema`: defines the final structured output shape
- `run logger`: writes request, prompt, JSONL events, final JSON, and stderr
- `approval gate`: blocks write-capable or core-sensitive work until a human approves

## Required Human Approvals

The bridge must require explicit human approval for:

- any write-capable run
- any task aimed at the brain repository itself
- any change that touches `core/`
- any change that touches `state.json`, `.cerebro/`, schema, `analyze`, `validate`, or session policy
- destructive shell commands
- config changes for Codex or MCP
- any step that would open a new semantic layer

## MVP

The first safe MVP is intentionally small and external:

- location:
  - `_local/automation_bridge/`
- mode:
  - read-only by default
- inputs:
  - project root
  - task text or task file
  - explicit context paths
- outputs per run:
  - `request.json`
  - `prompt.txt`
  - `event-stream.jsonl`
  - `final.json`
  - `stderr.log`
  - `summary.json`
- executor transport:
  - `codex exec --ephemeral --json --output-schema -o`

This MVP is enough to replace a relevant part of the manual loop while staying disposable and non-authoritative.

## Explicit Limits

This MVP does not:

- replace the brain
- decide canonical context
- automate `import-context`
- does not register `sources`
- create memory outside explicit run logs
- persist Codex thread history as project truth
- update board or handoffs automatically
- open app-server, SDK orchestration, or MCP-based manager flows

## Exact Implementation Sequence

1. Keep the bridge outside tracked product code during incubation.
2. Create one disposable local orchestrator under `_local/automation_bridge/`.
3. Start with read-only execution only.
4. Require structured final output via JSON Schema.
5. Capture full JSONL event logs for each run.
6. Use explicit context-path lists instead of discovery with authority.
7. Validate the bridge on repeated audit-style tasks first.
8. Only consider write-capable rounds after a separate approval-gate design is explicitly approved.

## Sources

- Codex SDK:
  - https://developers.openai.com/codex/sdk
- Codex app-server:
  - https://developers.openai.com/codex/app-server
- Codex non-interactive mode:
  - https://developers.openai.com/codex/noninteractive
- Codex best practices:
  - https://developers.openai.com/codex/learn/best-practices
- Agents SDK:
  - https://developers.openai.com/api/docs/guides/agents
- Orchestration and handoffs:
  - https://developers.openai.com/api/docs/guides/agents/orchestration
- Tools in the Agents SDK:
  - https://developers.openai.com/api/docs/guides/tools
