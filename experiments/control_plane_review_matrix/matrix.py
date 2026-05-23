from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable

from experiments.control_plane_review_packet import ControlPlaneReviewPacket


class ControlPlaneReviewMatrixError(ValueError):
    """Raised when a review matrix cannot be built safely."""


@dataclass(frozen=True)
class ControlPlaneReviewMatrixRow:
    scenario_id: str
    trace_id: str
    selected_task_id: str
    packet_verdict: str
    combined_review_status: str
    recommended_human_decision: str
    blocker_count: int
    blockers: tuple[str, ...]
    required_capability_review_count: int
    required_capability_reviews: tuple[str, ...]
    replay_evaluation_verdict: str
    replay_status: str
    replay_issue_count: int
    replay_issue_codes: tuple[str, ...]
    trace_event_count: int
    guardrails: tuple[str, ...]


@dataclass(frozen=True)
class ControlPlaneReviewMatrix:
    schema_version: str
    matrix_role: str
    packet_count: int
    packet_verdict_counts: dict[str, int]
    combined_review_status_counts: dict[str, int]
    replay_evaluation_verdict_counts: dict[str, int]
    replay_status_counts: dict[str, int]
    blocker_counts: dict[str, int]
    replay_issue_counts: dict[str, int]
    required_human_decisions: tuple[str, ...]
    rows: tuple[ControlPlaneReviewMatrixRow, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane review matrix only"
    matrix_is_not_permission: bool = True
    matrix_pass_is_not_execution_approval: bool = True
    replay_pass_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


def _validate_scenario_id(scenario_id: str) -> None:
    if not scenario_id:
        raise ControlPlaneReviewMatrixError("scenario_id is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in scenario_id):
        raise ControlPlaneReviewMatrixError("scenario_id must be path-segment safe")


def _validate_packet(packet: ControlPlaneReviewPacket) -> None:
    if packet.state_change != "none" or "non-authoritative" not in packet.authority:
        raise ControlPlaneReviewMatrixError("packet must be non-authoritative with state_change none")
    if (
        not packet.packet_is_not_permission
        or not packet.replay_pass_is_not_truth
        or not packet.packet_pass_is_not_execution_approval
        or not packet.must_not_execute_automatically
    ):
        raise ControlPlaneReviewMatrixError("packet guardrails must remain true")


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _row(packet: ControlPlaneReviewPacket) -> ControlPlaneReviewMatrixRow:
    scenario_id = packet.trace_id
    _validate_scenario_id(scenario_id)
    _validate_packet(packet)
    return ControlPlaneReviewMatrixRow(
        scenario_id=scenario_id,
        trace_id=packet.trace_id,
        selected_task_id=packet.selected_task_id,
        packet_verdict=packet.packet_verdict,
        combined_review_status=packet.combined_review_status,
        recommended_human_decision=packet.recommended_human_decision,
        blocker_count=len(packet.blockers),
        blockers=packet.blockers,
        required_capability_review_count=len(packet.required_capability_reviews),
        required_capability_reviews=packet.required_capability_reviews,
        replay_evaluation_verdict=packet.replay_evaluation_verdict,
        replay_status=packet.replay_status,
        replay_issue_count=len(packet.replay_issue_codes),
        replay_issue_codes=packet.replay_issue_codes,
        trace_event_count=packet.trace_event_count,
        guardrails=packet.guardrails,
    )


def _validate_matrix(matrix: ControlPlaneReviewMatrix) -> None:
    if matrix.state_change != "none" or "non-authoritative" not in matrix.authority:
        raise ControlPlaneReviewMatrixError("matrix must be non-authoritative with state_change none")
    if (
        not matrix.matrix_is_not_permission
        or not matrix.matrix_pass_is_not_execution_approval
        or not matrix.replay_pass_is_not_truth
        or not matrix.must_not_execute_automatically
    ):
        raise ControlPlaneReviewMatrixError("matrix guardrails must remain true")
    if matrix.packet_count != len(matrix.rows):
        raise ControlPlaneReviewMatrixError("packet_count must match rows")
    if not matrix.rows:
        raise ControlPlaneReviewMatrixError("matrix must contain at least one row")


def build_control_plane_review_matrix(
    packets: Iterable[ControlPlaneReviewPacket],
) -> ControlPlaneReviewMatrix:
    """Aggregate already-built review packets without changing authority."""

    packet_items = tuple(packets)
    if not packet_items:
        raise ControlPlaneReviewMatrixError("matrix must contain at least one packet")
    trace_ids = [packet.trace_id for packet in packet_items]
    duplicates = sorted({trace_id for trace_id in trace_ids if trace_ids.count(trace_id) > 1})
    if duplicates:
        raise ControlPlaneReviewMatrixError(f"duplicate trace_id: {', '.join(duplicates)}")

    rows = tuple(_row(packet) for packet in packet_items)
    matrix = ControlPlaneReviewMatrix(
        schema_version="1",
        matrix_role="aggregates_existing_control_plane_review_packets",
        packet_count=len(rows),
        packet_verdict_counts=_count(row.packet_verdict for row in rows),
        combined_review_status_counts=_count(row.combined_review_status for row in rows),
        replay_evaluation_verdict_counts=_count(row.replay_evaluation_verdict for row in rows),
        replay_status_counts=_count(row.replay_status for row in rows),
        blocker_counts=_count(blocker for row in rows for blocker in row.blockers),
        replay_issue_counts=_count(issue for row in rows for issue in row.replay_issue_codes),
        required_human_decisions=_ordered_unique(
            row.recommended_human_decision
            for row in rows
            if row.recommended_human_decision != "none"
        ),
        rows=rows,
    )
    _validate_matrix(matrix)
    return matrix


def render_control_plane_review_matrix_json(matrix: ControlPlaneReviewMatrix) -> str:
    _validate_matrix(matrix)
    payload = asdict(matrix)
    payload["state_change"] = "none"
    payload["authority"] = matrix.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_review_matrix_markdown(matrix: ControlPlaneReviewMatrix) -> str:
    _validate_matrix(matrix)
    lines = [
        "# Control Plane Review Matrix",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane review matrix only",
        "- matrix_is_not_permission: true",
        "- matrix_pass_is_not_execution_approval: true",
        "- replay_pass_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- matrix_role: {matrix.matrix_role}",
        f"- packet_count: {matrix.packet_count}",
        f"- required_human_decisions: {', '.join(matrix.required_human_decisions) if matrix.required_human_decisions else 'none'}",
        f"- packet_verdict_counts: {matrix.packet_verdict_counts}",
        f"- combined_review_status_counts: {matrix.combined_review_status_counts}",
        f"- replay_evaluation_verdict_counts: {matrix.replay_evaluation_verdict_counts}",
        f"- replay_status_counts: {matrix.replay_status_counts}",
        f"- blocker_counts: {matrix.blocker_counts}",
        f"- replay_issue_counts: {matrix.replay_issue_counts}",
        "",
        "## Rows",
        "",
    ]
    for row in matrix.rows:
        lines.append(
            f"- {row.scenario_id}: {row.packet_verdict}; "
            f"trace={row.trace_id}; human={row.recommended_human_decision}; "
            f"replay={row.replay_evaluation_verdict}"
        )
    return "\n".join(lines).rstrip() + "\n"
