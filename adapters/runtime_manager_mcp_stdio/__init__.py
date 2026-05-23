"""MCP STDIO server for RuntimeManagerStore.

Transport: STDIO only.  No HTTP, no OAuth server, no TLS.
Token:     env var CEREBRO_RUNTIME_MCP_TOKEN; never from CLI args.
Identity:  AgentContext derived from authenticated token, never self-reported.
Scopes:    runtime:read, runtime:lease, runtime:execute, runtime:trace,
           runtime:metrics, runtime:replay.

record_approval is NOT exposed; approval remains CLI/human only.
"""


def build_app(*args, **kwargs):
    from adapters.runtime_manager_mcp_stdio.server import build_app as _build_app

    return _build_app(*args, **kwargs)


def run_stdio(*args, **kwargs):
    from adapters.runtime_manager_mcp_stdio.server import run_stdio as _run_stdio

    return _run_stdio(*args, **kwargs)

__all__ = ["build_app", "run_stdio"]
