# Control Plane Runtime Adoption Review

Advisory runtime-adoption review for caller-supplied technology proposals.

- state_change: none
- authority: non-authoritative; advisory control-plane runtime adoption review only
- adoption_review_is_not_permission: true
- adoption_status_is_not_execution_approval: true
- technology_selection_is_not_authority: true
- proposal_record_is_not_truth: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

The package asks whether a proposed runtime technology adoption is research-only, a candidate that needs human review, or blocked by decision, integrity, rule-promotion, action, evidence, proposal-version, safety-plan, or boundary drift. Proposals are caller-supplied records with `proposal_thread_id`, `revision`, and `supersedes_proposal_id`; the review detects gaps, duplicate thread revisions, cross-thread supersession, non-previous supersession, multiple active candidates, active-not-latest candidates, and stale runtime-change candidates.

This review can mention technology families only as non-authoritative input categories. MCP adoption is not permission, Temporal adoption is not execution approval, OpenTelemetry adoption is not truth, LangGraph adoption is not scheduler authority, OpenAI Agents SDK adoption is not handoff permission, and Cloudflare Agents SDK adoption is not runtime authority. It does not import adapters, read docs/operations, read `.cerebro/`, mutate state, expose tools, start workers, schedule work, choose next action, grant permission, approve technology, or become a runtime/canonical gate.
