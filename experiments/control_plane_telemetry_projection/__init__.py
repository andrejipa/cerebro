"""Advisory in-memory telemetry projection for Control Plane packets."""

from .projection import (
    ControlPlaneTelemetryEvent,
    ControlPlaneTelemetryProjection,
    ControlPlaneTelemetryProjectionError,
    ControlPlaneTelemetrySpan,
    project_control_plane_adversarial_report_to_telemetry,
    project_control_plane_matrix_to_telemetry,
    project_control_plane_packets_to_telemetry,
    project_control_plane_packet_to_telemetry,
    project_control_plane_scenario_lab_to_telemetry,
    render_control_plane_telemetry_json,
    render_control_plane_telemetry_markdown,
)

__all__ = [
    "ControlPlaneTelemetryEvent",
    "ControlPlaneTelemetryProjection",
    "ControlPlaneTelemetryProjectionError",
    "ControlPlaneTelemetrySpan",
    "project_control_plane_adversarial_report_to_telemetry",
    "project_control_plane_matrix_to_telemetry",
    "project_control_plane_packets_to_telemetry",
    "project_control_plane_packet_to_telemetry",
    "project_control_plane_scenario_lab_to_telemetry",
    "render_control_plane_telemetry_json",
    "render_control_plane_telemetry_markdown",
]
