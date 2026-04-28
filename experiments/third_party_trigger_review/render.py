from __future__ import annotations

from .contract import ThirdPartyTriggerReview


def render_review_markdown(review: ThirdPartyTriggerReview) -> str:
    lines = [
        "# Third-Party Trigger Review",
        "",
        f"- trigger_id: `{review.trigger_id}`",
        f"- readiness: `{review.readiness}`",
        f"- target_path: `{review.target_path or 'missing'}`",
        f"- slice_kind: `{review.slice_kind or 'missing'}`",
        f"- blocker_count: `{review.blocker_count}`",
        f"- warning_count: `{review.warning_count}`",
        f"- consecutive_target_slice_risk: `{review.consecutive_target_slice_risk}`",
        f"- state_change: `{review.state_change}`",
        "",
        "## Checks",
        "",
    ]

    checks = [
        ("dogfood_value_present", review.dogfood_value_present),
        ("proof_cost_declared", review.proof_cost_declared),
        ("source_roles_declared", review.source_roles_declared),
        ("target_cerebro_handling_declared", review.target_cerebro_handling_declared),
        ("rollback_declared", review.rollback_declared),
        ("cleanup_declared", review.cleanup_declared),
        ("stop_lines_declared", review.stop_lines_declared),
        ("forbidden_paths_declared", review.forbidden_paths_declared),
    ]
    lines.extend(f"- {name}: `{str(value).lower()}`" for name, value in checks)

    lines.extend(["", "## Findings", ""])
    if review.findings:
        lines.extend(
            f"- `{finding.severity}` `{finding.code}`: {finding.message}"
            for finding in review.findings
        )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This report is advisory evidence only. It does not approve execution,",
            "mutate target projects, register sources, write memory, create a runtime",
            "gate, or promote authority.",
            "",
        ]
    )
    return "\n".join(lines)
