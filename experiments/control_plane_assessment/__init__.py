"""Read-only control-plane assessment composition.

This experiment composes existing advisory/runtime surfaces. It does not schedule work, grant permission, write memory, or mutate canonical state.
"""

from .assessment import (
    ControlPlaneAssessment,
    ControlPlaneAssessmentError,
    build_control_plane_assessment,
    render_control_plane_assessment_json,
    render_control_plane_assessment_markdown,
)

__all__ = [
    "ControlPlaneAssessment",
    "ControlPlaneAssessmentError",
    "build_control_plane_assessment",
    "render_control_plane_assessment_json",
    "render_control_plane_assessment_markdown",
]
