"""Authorization envelopes -- signed, frozen permission sets.

Implements SPEC.md Section 8: envelope schema, crisis adjustments,
and HMAC-SHA256 signature computation.

An authorization envelope accompanies a tool invocation and constrains the
executor. Envelope parameters tighten as the mode signal increases:
- Normal (mode <= 0.35): standard execution, full budget
- Elevated (0.35 < mode <= 0.65): cautious mode, reduced budget
- Crisis (mode > 0.65): minimal execution, tightest constraints

Conforms to schema/envelope.schema.json.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from typing import Any

from maelstrom_gate.core import Tool


@dataclass(frozen=True)
class AuthorizationEnvelope:
    """A signed, immutable permission set for a tool invocation.

    See SPEC.md Section 8 for field descriptions and the full schema.
    """
    envelope_id: str
    context_id: str
    tool_name: str
    allowed_tools: tuple[str, ...] = ()
    max_tool_calls: int = 20
    max_retries: int = 1
    budget_seconds: int = 30
    execution_mode: str = "standard"
    dry_run: bool = False
    branching: str = "deny"
    human_approved: bool = False
    signature: str = ""


def _canonical_hash(data: Any) -> str:
    """Compute SHA-256 of canonical JSON (sorted keys, no whitespace).

    This is step 2-3 of the signature algorithm in SPEC.md Section 8.
    """
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_envelope(
    tool: Tool, mode: float, context_id: str, signing_key: str,
    human_approved: bool = False, extra_tools: tuple[str, ...] = (),
) -> AuthorizationEnvelope:
    """Build and sign an authorization envelope for a tool invocation.

    Applies the crisis adjustment table from SPEC.md Section 8:
    - Normal:   30s budget, 20 calls, standard mode, per-class branching
    - Elevated: 15s budget, 10 calls, cautious mode, branching denied
    - Crisis:    7s budget,  5 calls, minimal mode,  branching denied

    Args:
        tool: The tool being authorized.
        mode: Current mode signal (0.0-1.0).
        context_id: Session or context identifier.
        signing_key: HMAC signing key.
        human_approved: Whether a human explicitly approved this invocation.
        extra_tools: Additional tool names permitted under this envelope.

    Returns:
        A signed, frozen AuthorizationEnvelope.
    """
    envelope_id = f"env_{context_id}_{uuid.uuid4().hex[:8]}"
    allowed = (tool.name,) + extra_tools
    max_tool_calls, budget_seconds = 20, 30
    execution_mode = "standard"
    branching = "auto" if tool.execution_class in ("read_only", "advisory") else "deny"
    if mode > 0.65:
        budget_seconds, max_tool_calls, execution_mode, branching = 7, 5, "minimal", "deny"
    elif mode > 0.35:
        budget_seconds, max_tool_calls, execution_mode, branching = 15, 10, "cautious", "deny"
    sign_data = {
        "envelope_id": envelope_id, "context_id": context_id, "tool_name": tool.name,
        "allowed_tools": allowed, "max_tool_calls": max_tool_calls,
        "budget_seconds": budget_seconds, "execution_mode": execution_mode,
        "branching": branching, "human_approved": human_approved,
    }
    sig = hmac.new(signing_key.encode(), _canonical_hash(sign_data).encode(), hashlib.sha256).hexdigest()
    return AuthorizationEnvelope(
        envelope_id=envelope_id, context_id=context_id, tool_name=tool.name,
        allowed_tools=allowed, max_tool_calls=max_tool_calls, max_retries=1,
        budget_seconds=budget_seconds, execution_mode=execution_mode,
        branching=branching, human_approved=human_approved, signature=sig,
    )


def verify_envelope(envelope: AuthorizationEnvelope, signing_key: str) -> bool:
    """Verify the HMAC-SHA256 signature of an authorization envelope.

    Recomputes the signature using the provided key and compares it
    to the envelope's stored signature using constant-time comparison.

    Args:
        envelope: The envelope to verify.
        signing_key: The HMAC signing key (must match the key used to build).

    Returns:
        True if the signature is valid, False otherwise.
    """
    sign_data = {
        "envelope_id": envelope.envelope_id, "context_id": envelope.context_id,
        "tool_name": envelope.tool_name, "allowed_tools": envelope.allowed_tools,
        "max_tool_calls": envelope.max_tool_calls, "budget_seconds": envelope.budget_seconds,
        "execution_mode": envelope.execution_mode, "branching": envelope.branching,
        "human_approved": envelope.human_approved,
    }
    expected = hmac.new(signing_key.encode(), _canonical_hash(sign_data).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(envelope.signature, expected)
