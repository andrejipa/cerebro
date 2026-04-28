from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .baseline_lifecycle import (
    BaselineLifecycleReport,
    evaluate_baseline_lifecycle,
    render_baseline_lifecycle_json,
    render_baseline_lifecycle_markdown,
)
from .contract import ReadinessReport
from .drift_policy import (
    DriftPolicyReport,
    evaluate_drift_policy,
    render_drift_policy_json,
    render_drift_policy_markdown,
)
from .diff import (
    TraceDiff,
    compare_decision_traces,
    load_decision_trace_json,
    render_trace_diff_json,
    render_trace_diff_markdown,
)
from .manifest import generate_readiness_report_from_manifest
from .render import render_readiness_markdown
from .self_audit import (
    ProtocolSelfAuditReport,
    audit_protocol_from_trace_diff,
    render_protocol_self_audit_json,
    render_protocol_self_audit_markdown,
)
from .trace import DecisionTrace, build_decision_trace, render_decision_trace_json


REPLAY_BUNDLE_AUTHORITY = "non-authoritative; advisory replay bundle evidence only"
BASELINE_TRACE_FILENAME = "CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json"


@dataclass(frozen=True)
class ReplayBundlePaths:
    readiness_report: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md"
    decision_trace: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json"
    trace_diff_json: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json"
    trace_diff_markdown: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.md"
    protocol_self_audit_json: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.json"
    protocol_self_audit_markdown: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.md"
    baseline_lifecycle_json: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.json"
    baseline_lifecycle_markdown: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.md"
    drift_policy_json: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_DRIFT_POLICY.json"
    drift_policy_markdown: str = "docs/operations/CEREBRO_SELF_EPISTEMIC_DRIFT_POLICY.md"

    def as_items(self) -> tuple[tuple[str, str], ...]:
        return (
            ("readiness_report", self.readiness_report),
            ("decision_trace", self.decision_trace),
            ("trace_diff_json", self.trace_diff_json),
            ("trace_diff_markdown", self.trace_diff_markdown),
            ("protocol_self_audit_json", self.protocol_self_audit_json),
            ("protocol_self_audit_markdown", self.protocol_self_audit_markdown),
            ("baseline_lifecycle_json", self.baseline_lifecycle_json),
            ("baseline_lifecycle_markdown", self.baseline_lifecycle_markdown),
            ("drift_policy_json", self.drift_policy_json),
            ("drift_policy_markdown", self.drift_policy_markdown),
        )


DEFAULT_REPLAY_BUNDLE_PATHS = ReplayBundlePaths()


@dataclass(frozen=True)
class ReplayBundleWriteResult:
    written_paths: tuple[str, ...]
    baseline_updated: bool = False
    state_change: str = "none"
    authority: str = REPLAY_BUNDLE_AUTHORITY

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("replay bundle writes must not change state")
        if self.baseline_updated:
            raise ValueError("replay bundle writer must not update baseline")

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_change": self.state_change,
            "authority": self.authority,
            "baseline_updated": self.baseline_updated,
            "written_paths": list(self.written_paths),
            "boundary": {
                "may_suggest": [
                    "inspect regenerated replay evidence",
                    "compare drift",
                    "request human review",
                    "propose a separate baseline refresh trigger",
                ],
                "must_not_apply": [
                    "mutate state",
                    "update baseline automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat replay success as permission",
                ],
            },
        }


@dataclass(frozen=True)
class ReplayBundle:
    report: ReadinessReport
    trace: DecisionTrace
    trace_diff: TraceDiff
    protocol_self_audit: ProtocolSelfAuditReport
    baseline_lifecycle: BaselineLifecycleReport
    drift_policy: DriftPolicyReport
    state_change: str = "none"
    authority: str = REPLAY_BUNDLE_AUTHORITY
    bundle_role: str = "advisory replay bundle evidence only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("replay bundles must not change state")
        if self.report.state_change != "none":
            raise ValueError("replay bundles cannot wrap mutating reports")
        if self.trace.state_change != "none":
            raise ValueError("replay bundles cannot wrap mutating traces")
        if self.trace_diff.state_change != "none":
            raise ValueError("replay bundles cannot wrap mutating trace diffs")
        if self.protocol_self_audit.state_change != "none":
            raise ValueError("replay bundles cannot wrap mutating protocol self-audits")
        if self.baseline_lifecycle.state_change != "none":
            raise ValueError("replay bundles cannot wrap mutating lifecycle reports")
        if self.drift_policy.state_change != "none":
            raise ValueError("replay bundles cannot wrap mutating drift policy reports")

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_change": self.state_change,
            "authority": self.authority,
            "bundle_role": self.bundle_role,
            "summary": {
                "source_count": len(self.report.source_reads),
                "candidates_extracted": self.report.candidate_count,
                "findings_evaluated": self.report.finding_count,
                "ready_count": self.report.ready_count,
                "blocked_count": self.report.blocked_count,
                "insufficient_count": self.report.insufficient_count,
                "report_action_readiness": self.report.action_readiness,
                "trace_diff_has_regression": self.trace_diff.has_regression,
                "trace_diff_advisory_readiness": self.trace_diff.advisory_readiness,
                "protocol_self_audit_candidate_count": self.protocol_self_audit.candidate_count,
                "protocol_self_audit_high_or_blocking_count": (
                    self.protocol_self_audit.high_or_blocking_count
                ),
                "baseline_lifecycle_recommendation": self.baseline_lifecycle.recommendation,
                "baseline_lifecycle_required_human_action": (
                    self.baseline_lifecycle.required_human_action
                ),
                "baseline_lifecycle_action_readiness": self.baseline_lifecycle.action_readiness,
                "baseline_lifecycle_drift_total": self.baseline_lifecycle.drift_total,
                "drift_policy_classification": self.drift_policy.classification,
                "drift_policy_recommendation": self.drift_policy.recommendation,
                "drift_policy_action_readiness": self.drift_policy.action_readiness,
                "drift_policy_required_human_action": self.drift_policy.required_human_action,
            },
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "replay_success_is_not_permission": True,
                "baseline_refresh_is_not_automatic": True,
                "bundle_is_not_runtime_gate": True,
                "bundle_is_not_authority": True,
                "drift_policy_is_not_permission": True,
            },
            "boundary": {
                "may_suggest": [
                    "inspect regenerated replay evidence",
                    "compare replay drift",
                    "request human review",
                    "propose a future baseline refresh trigger",
                    "classify drift disposition",
                ],
                "must_not_apply": [
                    "mutate state",
                    "update baseline automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat replay success as permission",
                    "treat drift policy as permission",
                    "write learned memory automatically",
                ],
            },
        }


def build_replay_bundle(
    root: str | Path,
    manifest_path: str | Path,
    baseline_trace_path: str | Path,
    *,
    baseline_label: str = "baseline",
    current_label: str = "current",
    self_audit_source_label: str = "epistemic-readiness-replay-bundle",
    churn_threshold: int = 10,
) -> ReplayBundle:
    root_path = Path(root)
    report = generate_readiness_report_from_manifest(root_path, manifest_path)
    trace = build_decision_trace(root_path, manifest_path, report=report)
    baseline_trace = load_decision_trace_json(baseline_trace_path)
    current_trace = trace.to_dict()
    trace_diff = compare_decision_traces(
        baseline_trace,
        current_trace,
        baseline_label=baseline_label,
        current_label=current_label,
    )
    protocol_self_audit = audit_protocol_from_trace_diff(
        trace_diff.to_dict(),
        source_label=self_audit_source_label,
        churn_threshold=churn_threshold,
    )
    baseline_lifecycle = evaluate_baseline_lifecycle(
        baseline_trace,
        current_trace,
        trace_diff.to_dict(),
        protocol_self_audit.to_dict(),
        baseline_label=baseline_label,
        current_label=current_label,
    )
    drift_policy = evaluate_drift_policy(
        trace_diff.to_dict(),
        protocol_self_audit.to_dict(),
        baseline_lifecycle.to_dict(),
    )
    return ReplayBundle(
        report=report,
        trace=trace,
        trace_diff=trace_diff,
        protocol_self_audit=protocol_self_audit,
        baseline_lifecycle=baseline_lifecycle,
        drift_policy=drift_policy,
    )


def write_replay_bundle(
    root: str | Path,
    bundle: ReplayBundle,
    *,
    paths: ReplayBundlePaths = DEFAULT_REPLAY_BUNDLE_PATHS,
) -> ReplayBundleWriteResult:
    rendered = {
        "readiness_report": render_readiness_markdown(bundle.report),
        "decision_trace": render_decision_trace_json(bundle.trace),
        "trace_diff_json": render_trace_diff_json(bundle.trace_diff),
        "trace_diff_markdown": render_trace_diff_markdown(bundle.trace_diff),
        "protocol_self_audit_json": render_protocol_self_audit_json(bundle.protocol_self_audit),
        "protocol_self_audit_markdown": render_protocol_self_audit_markdown(bundle.protocol_self_audit),
        "baseline_lifecycle_json": render_baseline_lifecycle_json(bundle.baseline_lifecycle),
        "baseline_lifecycle_markdown": render_baseline_lifecycle_markdown(bundle.baseline_lifecycle),
        "drift_policy_json": render_drift_policy_json(bundle.drift_policy),
        "drift_policy_markdown": render_drift_policy_markdown(bundle.drift_policy),
    }
    resolved = {
        field_name: _safe_output_path(root, relative_path, field_name)
        for field_name, relative_path in paths.as_items()
    }
    written: list[str] = []
    for field_name, target in resolved.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered[field_name], encoding="utf-8")
        written.append(_display_path(root, target))
    return ReplayBundleWriteResult(written_paths=tuple(written))


def _safe_output_path(root: str | Path, path: str, field_name: str) -> Path:
    if not path:
        raise ValueError(f"{field_name} output path is required")
    root_path = Path(root).resolve()
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (root_path / candidate).resolve()
    try:
        relative = resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"{field_name} output path escapes root: {path}") from exc
    if any(part.lower() == ".cerebro" for part in relative.parts):
        raise ValueError(f"{field_name} output path points into .cerebro: {path}")
    if resolved.name == BASELINE_TRACE_FILENAME:
        raise ValueError(f"{field_name} output path targets replay baseline: {path}")
    return resolved


def _display_path(root: str | Path, path: Path) -> str:
    root_path = Path(root).resolve()
    try:
        return path.resolve().relative_to(root_path).as_posix()
    except ValueError:
        return str(path.resolve()).replace("\\", "/")
