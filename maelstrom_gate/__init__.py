"""Maelstrom Gate -- runtime governance for AI tool access.

Implements the Maelstrom Gate standard (see SPEC.md) for dynamically filtering
which tools an AI agent can see and invoke based on a threat/mode signal.

    from maelstrom_gate import Gate, Tool

    gate = Gate()
    gate.add_tool(Tool("send_email", execution_class="external_action"))
    gate.add_tool(Tool("read_file", execution_class="read_only"))
    gate.add_tool(Tool("deploy", execution_class="high_impact"))

    visible = gate.filter(mode=0.8)
    # -> only read_file visible -- send_email and deploy suppressed

Specification: SPEC.md
JSON Schemas: schema/tool.schema.json, schema/envelope.schema.json
"""

__version__ = "0.1.0"

from maelstrom_gate.core import (
    Gate,
    Tool,
    ToolFilter,
    ExecutionClass,
    SUPPRESSION_THRESHOLDS,
    T_DOWN,
    T_UP,
    zone,
)
from maelstrom_gate.envelope import AuthorizationEnvelope, build_envelope, verify_envelope, verify_envelope_fresh
from maelstrom_gate.ingress import validate_proposal, IngressResult

__all__ = [
    "Gate",
    "Tool",
    "ToolFilter",
    "ExecutionClass",
    "SUPPRESSION_THRESHOLDS",
    "T_DOWN",
    "T_UP",
    "zone",
    "AuthorizationEnvelope",
    "build_envelope",
    "verify_envelope",
    "verify_envelope_fresh",
    "validate_proposal",
    "IngressResult",
]
