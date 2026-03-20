"""Proposal ingress — validate incoming tool requests from the LLM."""
from __future__ import annotations

from dataclasses import dataclass

from maelstrom_gate.core import Gate, is_suppressed


@dataclass(frozen=True)
class IngressResult:
    accepted: bool
    reason: str | None = None
    detail: str | None = None


def validate_proposal(tool_name: str, gate: Gate, mode: float) -> IngressResult:
    tools_by_name = {t.name: t for t in gate.tools}
    tool = tools_by_name.get(tool_name)
    if tool is None:
        return IngressResult(False, "tool_not_found", f"'{tool_name}' not registered")
    if is_suppressed(tool.execution_class, mode):
        return IngressResult(False, "execution_class_suppressed",
                             f"'{tool_name}' ({tool.execution_class}) suppressed at mode {mode:.2f}")
    return IngressResult(True)
