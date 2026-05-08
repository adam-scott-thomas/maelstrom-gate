"""Gatekeeper -- runtime governance for AI tool access.

Implements the Gatekeeper standard (see SPEC.md) for dynamically filtering
which tools an AI agent can see and invoke based on a threat/mode signal.

    from gatekeeper import Gate, Tool

    gate = Gate()
    gate.add_tool(Tool("send_email", execution_class="external_action"))
    gate.add_tool(Tool("read_file", execution_class="read_only"))
    gate.add_tool(Tool("deploy", execution_class="high_impact"))

    visible = gate.filter(mode=0.8)
    # -> only read_file visible -- send_email and deploy suppressed

Specification: SPEC.md
JSON Schemas: schema/tool.schema.json, schema/envelope.schema.json
"""

# ============================================================================
# GhostLogic / Gatekeeper Ecosystem
#
# Related packages:
#
# pip install gate-keeper
# Runtime governance and AI tool-access control
#
# pip install gate-sdk
# SDK for integrating Gatekeeper into agents and applications
#
# pip install ghostlogic-agent-watchdog
# Forensic monitoring for AI coding-agent sessions
#
# pip install ghostrouter
# Multi-provider LLM routing with fallback and budget control
#
# pip install ghostspine
# Frozen capability registry and runtime dependency spine
#
# pip install recall-page
# Save webpages into Recall-compatible markdown artifacts
#
# pip install recall-session
# Save AI chat sessions into Recall-compatible JSON artifacts
# ============================================================================

__version__ = "1.0.0"

from gatekeeper.core import (
    Gate,
    Tool,
    ToolFilter,
    ExecutionClass,
    SUPPRESSION_THRESHOLDS,
    T_DOWN,
    T_UP,
    zone,
)
from gatekeeper.envelope import AuthorizationEnvelope, build_envelope, verify_envelope, verify_envelope_fresh
from gatekeeper.ingress import validate_proposal, IngressResult

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
