"""Advisory decision-envelope oracle for concrete action questions.

This derived package is local-only, read-only, deterministic, and
non-authoritative. It evaluates whether evidence is sufficient to proceed with
an action posture, but it does not grant permission or create runtime authority.
"""

from .contract import (
    ActionProfile,
    ApprovalContext,
    DecisionEnvelope,
    DecisionScenario,
    EvidenceClaim,
    EvidenceRequirement,
    EvidenceSource,
    PathDigest,
    PrewriteGuard,
)
from .evaluator import evaluate_decision_scenario
from .fixtures import all_fixture_scenarios
from .manifest import (
    DecisionManifestError,
    evaluate_manifest_file,
    load_decision_manifest,
)
from .pre_action import (
    PreActionGuardError,
    PreActionGuardReport,
    ProposedAction,
    build_pre_action_guard_report,
    build_pre_action_guard_report_from_manifest,
    render_pre_action_guard_report_json,
    render_pre_action_guard_report_markdown,
)
from .pre_action_stress import (
    PreActionStressCaseResult,
    PreActionStressMatrixReport,
    build_default_pre_action_stress_matrix,
    render_pre_action_stress_matrix_json,
    render_pre_action_stress_matrix_markdown,
)
from .pre_action_packet import (
    PreActionDecisionPacket,
    build_pre_action_decision_packet,
    render_pre_action_decision_packet_json,
    render_pre_action_decision_packet_markdown,
)
from .pre_action_packet_stress import (
    PreActionPacketArtifactCheck,
    PreActionPacketStressError,
    PreActionPacketStressReproCaseResult,
    PreActionPacketStressReproReport,
    build_pre_action_packet_stress_repro_report,
    check_pre_action_packet_artifacts,
    render_pre_action_packet_stress_repro_json,
    render_pre_action_packet_stress_repro_markdown,
)
from .pre_action_closeout import (
    PreActionPacketReviewCloseout,
    build_pre_action_packet_review_closeout,
    render_pre_action_packet_review_closeout_json,
    render_pre_action_packet_review_closeout_markdown,
)
from .render import render_envelopes_json, render_envelopes_markdown

__all__ = [
    "ActionProfile",
    "ApprovalContext",
    "DecisionEnvelope",
    "DecisionScenario",
    "EvidenceClaim",
    "EvidenceRequirement",
    "EvidenceSource",
    "PathDigest",
    "PrewriteGuard",
    "PreActionGuardError",
    "PreActionGuardReport",
    "PreActionDecisionPacket",
    "PreActionPacketArtifactCheck",
    "PreActionPacketStressError",
    "PreActionPacketReviewCloseout",
    "PreActionPacketStressReproCaseResult",
    "PreActionPacketStressReproReport",
    "PreActionStressCaseResult",
    "PreActionStressMatrixReport",
    "ProposedAction",
    "all_fixture_scenarios",
    "build_pre_action_guard_report",
    "build_pre_action_guard_report_from_manifest",
    "build_pre_action_decision_packet",
    "build_pre_action_packet_stress_repro_report",
    "build_pre_action_packet_review_closeout",
    "build_default_pre_action_stress_matrix",
    "check_pre_action_packet_artifacts",
    "DecisionManifestError",
    "evaluate_manifest_file",
    "evaluate_decision_scenario",
    "load_decision_manifest",
    "render_pre_action_guard_report_json",
    "render_pre_action_guard_report_markdown",
    "render_pre_action_decision_packet_json",
    "render_pre_action_decision_packet_markdown",
    "render_pre_action_packet_stress_repro_json",
    "render_pre_action_packet_stress_repro_markdown",
    "render_pre_action_packet_review_closeout_json",
    "render_pre_action_packet_review_closeout_markdown",
    "render_pre_action_stress_matrix_json",
    "render_pre_action_stress_matrix_markdown",
    "render_envelopes_json",
    "render_envelopes_markdown",
]
