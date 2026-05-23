# Capability Policy

Status: derived experiment, read-only.

This package evaluates a proposed tool/command capability against an explicit
local policy manifest. It exists before any MCP, Agents SDK, or external-tool
adapter so Cerebro can reason about:

- allowed, denied, and review-required command families;
- argv prefixes;
- path scopes;
- data sensitivity;
- network/cloud access;
- output budget;
- approval and rollback expectations.

It does not execute commands, mutate `.cerebro/`, grant permission, register
tools, create a runtime gate, or become scheduler authority. Every assessment
declares `state_change = "none"`, `authority = "non-authoritative"`,
`advisory_allow_is_not_permission = true`, and
`must_not_execute_automatically = true`.
