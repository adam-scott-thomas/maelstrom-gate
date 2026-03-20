"""Maelstrom Gate — runtime governance for AI tool access.

Dynamically filter which tools an LLM can see and use based on
a threat/mode signal.

    from maelstrom_gate import Gate, Tool

    gate = Gate()
    gate.add_tool(Tool("send_email", execution_class="external_action"))
    gate.add_tool(Tool("read_file", execution_class="read_only"))
    gate.add_tool(Tool("deploy", execution_class="high_impact"))

    visible = gate.filter(mode=0.8)
    # → only read_file visible — send_email and deploy suppressed
"""

__version__ = "0.1.0"

from maelstrom_gate.core import Gate, Tool, ToolFilter, ExecutionClass
from maelstrom_gate.envelope import AuthorizationEnvelope, build_envelope, verify_envelope
from maelstrom_gate.ingress import validate_proposal, IngressResult

__all__ = [
    "Gate",
    "Tool",
    "ToolFilter",
    "ExecutionClass",
    "AuthorizationEnvelope",
    "build_envelope",
    "verify_envelope",
    "validate_proposal",
    "IngressResult",
]
