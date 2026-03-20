"""Authorization envelopes — signed, frozen permission sets."""
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
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_envelope(
    tool: Tool, mode: float, context_id: str, signing_key: str,
    human_approved: bool = False, extra_tools: tuple[str, ...] = (),
) -> AuthorizationEnvelope:
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
    sign_data = {
        "envelope_id": envelope.envelope_id, "context_id": envelope.context_id,
        "tool_name": envelope.tool_name, "allowed_tools": envelope.allowed_tools,
        "max_tool_calls": envelope.max_tool_calls, "budget_seconds": envelope.budget_seconds,
        "execution_mode": envelope.execution_mode, "branching": envelope.branching,
        "human_approved": envelope.human_approved,
    }
    expected = hmac.new(signing_key.encode(), _canonical_hash(sign_data).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(envelope.signature, expected)
