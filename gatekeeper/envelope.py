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

from gatekeeper.core import Tool


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
    created_at: int = 0  # Unix microseconds (int64), signed to prevent replay.
                          # Integer microseconds serialize identically in Python and Go,
                          # and fit within float64 precision (~15.95 digits) so the
                          # value survives JSON round-trips through untyped decoders.
    signature: str = ""


def _canonical_hash(data: Any) -> bytes:
    """Compute SHA-256 of canonical JSON (sorted keys, no whitespace).

    Returns the raw 32-byte digest (not hex) so HMAC operates on the same
    bytes across Python and Go implementations. This is step 2-3 of the
    signature algorithm in SPEC.md Section 8.
    """
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).digest()


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
    import time as _time
    envelope_id = f"env_{context_id}_{uuid.uuid4().hex[:8]}"
    created_at = _time.time_ns() // 1000  # microseconds
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
        "created_at": created_at,
    }
    sig = hmac.new(signing_key.encode(), _canonical_hash(sign_data), hashlib.sha256).hexdigest()
    return AuthorizationEnvelope(
        envelope_id=envelope_id, context_id=context_id, tool_name=tool.name,
        allowed_tools=allowed, max_tool_calls=max_tool_calls, max_retries=1,
        budget_seconds=budget_seconds, execution_mode=execution_mode,
        branching=branching, human_approved=human_approved,
        created_at=created_at, signature=sig,
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
        "created_at": envelope.created_at,
    }
    expected = hmac.new(signing_key.encode(), _canonical_hash(sign_data), hashlib.sha256).hexdigest()
    return hmac.compare_digest(envelope.signature, expected)


def verify_envelope_fresh(
    envelope: AuthorizationEnvelope, signing_key: str, max_age_seconds: float = 300.0,
) -> tuple[bool, str]:
    """Verify envelope signature AND check it hasn't expired.

    Prevents replay attacks — an envelope built during calm mode can't be
    reused hours later when threat level has risen.

    Args:
        envelope: The envelope to verify.
        signing_key: The HMAC signing key.
        max_age_seconds: Maximum age in seconds (default 300 = 5 minutes).

    Returns:
        (valid, reason) tuple. If valid is False, reason explains why.
    """
    if not verify_envelope(envelope, signing_key):
        return False, "signature_invalid"

    if envelope.created_at == 0:
        return False, "no_timestamp"

    import time as _time
    age = (_time.time_ns() // 1000 - envelope.created_at) / 1e6
    if age > max_age_seconds:
        return False, f"expired (age={age:.0f}s, max={max_age_seconds:.0f}s)"
    if age < -30:  # allow 30s clock skew
        return False, f"future_timestamp (age={age:.0f}s)"

    return True, "valid"
