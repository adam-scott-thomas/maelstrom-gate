"""Proposal ingress -- validate incoming tool requests from the LLM.

Implements SPEC.md Section 9 (Ingress Validation):
1. Registration check: tool must exist in the gate's registry.
2. Suppression check: tool must not be suppressed at the current mode.

Both checks MUST pass before any tool execution occurs.
"""
from __future__ import annotations

from dataclasses import dataclass

from gatekeeper.core import Gate, is_suppressed


@dataclass(frozen=True)
class IngressResult:
    """Result of ingress validation.

    Attributes:
        accepted: True if the tool request passed all checks.
        reason: Machine-readable rejection reason, or None if accepted.
            One of: ``tool_not_found``, ``execution_class_suppressed``.
        detail: Human-readable detail message, or None if accepted.
    """
    accepted: bool
    reason: str | None = None
    detail: str | None = None


def validate_proposal(tool_name: str, gate: Gate, mode: float) -> IngressResult:
    """Validate a tool request from the language model.

    Applies the two required ingress checks from SPEC.md Section 9:
    1. The tool name must be registered with the gate.
    2. The tool must not be suppressed at the current mode level.

    Args:
        tool_name: The name of the tool the model wants to invoke.
        gate: The gate instance containing registered tools.
        mode: Current mode signal (0.0-1.0).

    Returns:
        An IngressResult indicating acceptance or rejection with reason.
    """
    tools_by_name = {t.name: t for t in gate.tools}
    tool = tools_by_name.get(tool_name)
    if tool is None:
        return IngressResult(False, "tool_not_found", f"'{tool_name}' not registered")
    if is_suppressed(tool.execution_class, mode):
        return IngressResult(False, "execution_class_suppressed",
                             f"'{tool_name}' ({tool.execution_class}) suppressed at mode {mode:.2f}")
    return IngressResult(True)
