"""Advisory capability-policy checks for proposed tool use.

This package is derived/read-only. It evaluates declared capability requests
against explicit local policy rules, but it never executes commands or grants
runtime permission.
"""

from .policy import (
    CapabilityAssessment,
    CapabilityPolicyError,
    CapabilityRequest,
    CapabilityRule,
    evaluate_capability_request,
    load_capability_manifest,
    render_capability_assessment_json,
    render_capability_assessment_markdown,
)

__all__ = [
    "CapabilityAssessment",
    "CapabilityPolicyError",
    "CapabilityRequest",
    "CapabilityRule",
    "evaluate_capability_request",
    "load_capability_manifest",
    "render_capability_assessment_json",
    "render_capability_assessment_markdown",
]
