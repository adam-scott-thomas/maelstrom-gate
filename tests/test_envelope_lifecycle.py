"""Envelope lifecycle tests — real-world serialization + verification patterns.

In production, envelopes are:
  1. Built by gate-server (build_envelope)
  2. Serialized to JSON for HTTP response
  3. Deserialized by the SDK/client
  4. Verified before tool execution (verify_envelope)
  5. Potentially stored in compliance audit trail

These tests verify the full lifecycle, not just build+verify in memory.
"""
import json
import pytest
from dataclasses import asdict

from maelstrom_gate import (
    Gate, Tool, ToolFilter,
    AuthorizationEnvelope, build_envelope, verify_envelope,
    validate_proposal,
)


KEY = "lifecycle-test-key"


def _roundtrip_json(envelope: AuthorizationEnvelope) -> AuthorizationEnvelope:
    """Serialize envelope to JSON and back — simulates HTTP transport."""
    data = asdict(envelope)
    json_str = json.dumps(data)
    parsed = json.loads(json_str)
    return AuthorizationEnvelope(
        envelope_id=parsed["envelope_id"],
        context_id=parsed["context_id"],
        tool_name=parsed["tool_name"],
        allowed_tools=tuple(parsed["allowed_tools"]),
        max_tool_calls=parsed["max_tool_calls"],
        max_retries=parsed["max_retries"],
        budget_seconds=parsed["budget_seconds"],
        execution_mode=parsed["execution_mode"],
        dry_run=parsed["dry_run"],
        branching=parsed["branching"],
        human_approved=parsed["human_approved"],
        created_at=parsed.get("created_at", 0.0),
        signature=parsed["signature"],
    )


# --- Serialization roundtrip ---


def test_envelope_survives_json_roundtrip():
    """Envelope should verify after JSON serialization + deserialization."""
    e = build_envelope(Tool("read_file", execution_class="read_only"), 0.1, "ctx", KEY)
    e2 = _roundtrip_json(e)
    assert verify_envelope(e2, KEY)


def test_envelope_all_modes_survive_roundtrip():
    """Envelopes at all three mode levels should survive roundtrip."""
    tool = Tool("x", execution_class="read_only")
    for mode in [0.0, 0.1, 0.35, 0.5, 0.65, 0.8, 1.0]:
        e = build_envelope(tool, mode, f"ctx-{mode}", KEY)
        e2 = _roundtrip_json(e)
        assert verify_envelope(e2, KEY), f"Failed at mode {mode}"


def test_envelope_extra_tools_survive_roundtrip():
    """Extra tools tuple must roundtrip through JSON (list -> tuple)."""
    e = build_envelope(
        Tool("main", execution_class="read_only"), 0.1, "ctx", KEY,
        extra_tools=("helper_a", "helper_b", "helper_c"),
    )
    e2 = _roundtrip_json(e)
    assert e2.allowed_tools == ("main", "helper_a", "helper_b", "helper_c")
    assert verify_envelope(e2, KEY)


def test_tampered_envelope_detected_after_roundtrip():
    """Tampering after roundtrip should still be detected."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", KEY)
    data = asdict(e)
    data["budget_seconds"] = 9999
    json_str = json.dumps(data)
    parsed = json.loads(json_str)
    tampered = AuthorizationEnvelope(
        envelope_id=parsed["envelope_id"],
        context_id=parsed["context_id"],
        tool_name=parsed["tool_name"],
        allowed_tools=tuple(parsed["allowed_tools"]),
        max_tool_calls=parsed["max_tool_calls"],
        max_retries=parsed["max_retries"],
        budget_seconds=parsed["budget_seconds"],
        execution_mode=parsed["execution_mode"],
        dry_run=parsed["dry_run"],
        branching=parsed["branching"],
        human_approved=parsed["human_approved"],
        signature=parsed["signature"],
    )
    assert not verify_envelope(tampered, KEY)


# --- Full gate -> filter -> ingress -> envelope -> verify lifecycle ---


def test_full_lifecycle():
    """Complete lifecycle: register -> filter -> validate -> authorize -> verify."""
    gate = Gate()
    gate.add_tools([
        Tool("read_file", execution_class="read_only"),
        Tool("deploy", execution_class="high_impact"),
    ])

    # Step 1: Filter at normal mode
    result = gate.filter(0.1)
    assert "read_file" in result.visible_names
    assert "deploy" in result.visible_names

    # Step 2: Validate proposed tool via ingress
    ingress = validate_proposal("read_file", gate, 0.1)
    assert ingress.accepted

    # Step 3: Build envelope for authorized tool
    envelope = build_envelope(
        tool=Tool("read_file", execution_class="read_only"),
        mode=0.1, context_id="session-1", signing_key=KEY,
    )

    # Step 4: Serialize (as gate-server would for HTTP response)
    envelope_json = json.dumps(asdict(envelope))

    # Step 5: Deserialize (as SDK client would)
    envelope_received = _roundtrip_json(envelope)

    # Step 6: Verify before execution
    assert verify_envelope(envelope_received, KEY)

    # Step 7: Check envelope constraints
    assert envelope_received.budget_seconds == 30
    assert envelope_received.execution_mode == "standard"
    assert envelope_received.branching == "auto"  # read_only gets auto


def test_lifecycle_crisis_mode():
    """Lifecycle under crisis: suppressed tools can't get envelopes."""
    gate = Gate()
    gate.add_tools([
        Tool("read_file", execution_class="read_only"),
        Tool("deploy", execution_class="high_impact"),
    ])

    # Filter at crisis
    result = gate.filter(0.8)
    assert "deploy" in result.suppressed_names

    # Ingress rejects the suppressed tool
    ingress = validate_proposal("deploy", gate, 0.8)
    assert not ingress.accepted
    assert ingress.reason == "execution_class_suppressed"

    # But read_file still works with tightened constraints
    ingress_read = validate_proposal("read_file", gate, 0.8)
    assert ingress_read.accepted

    env = build_envelope(
        tool=Tool("read_file", execution_class="read_only"),
        mode=0.8, context_id="crisis-session", signing_key=KEY,
    )
    env2 = _roundtrip_json(env)
    assert verify_envelope(env2, KEY)
    assert env2.budget_seconds == 7
    assert env2.execution_mode == "minimal"
    assert env2.branching == "deny"


def test_lifecycle_mode_escalation():
    """Same tool gets progressively tighter envelopes as mode rises."""
    tool = Tool("read_file", execution_class="read_only")

    envelopes = {}
    for mode in [0.0, 0.5, 0.9]:
        e = build_envelope(tool, mode, f"ctx-{mode}", KEY)
        e2 = _roundtrip_json(e)
        assert verify_envelope(e2, KEY)
        envelopes[mode] = e2

    # Budget tightens
    assert envelopes[0.0].budget_seconds > envelopes[0.5].budget_seconds
    assert envelopes[0.5].budget_seconds > envelopes[0.9].budget_seconds

    # Max calls tightens
    assert envelopes[0.0].max_tool_calls > envelopes[0.5].max_tool_calls
    assert envelopes[0.5].max_tool_calls > envelopes[0.9].max_tool_calls


def test_different_keys_incompatible():
    """Envelope signed with key A should not verify with key B."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", "key-A")
    e2 = _roundtrip_json(e)
    assert verify_envelope(e2, "key-A")
    assert not verify_envelope(e2, "key-B")


def test_envelope_has_created_at():
    """New envelopes should have a non-zero created_at timestamp."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", KEY)
    assert e.created_at > 0


def test_created_at_survives_roundtrip():
    """created_at should survive JSON serialization."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", KEY)
    e2 = _roundtrip_json(e)
    assert e2.created_at == e.created_at
    assert verify_envelope(e2, KEY)


def test_verify_fresh_valid():
    """A freshly built envelope should pass freshness check."""
    from maelstrom_gate.envelope import verify_envelope_fresh
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", KEY)
    valid, reason = verify_envelope_fresh(e, KEY, max_age_seconds=60)
    assert valid is True
    assert reason == "valid"


def test_verify_fresh_expired():
    """An old envelope should fail freshness check."""
    import time
    from maelstrom_gate.envelope import verify_envelope_fresh
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", KEY)
    # Manually create an expired envelope by reconstructing with old timestamp
    old_time = time.time() - 600  # 10 minutes ago
    old_data = {
        "envelope_id": e.envelope_id, "context_id": e.context_id,
        "tool_name": e.tool_name, "allowed_tools": e.allowed_tools,
        "max_tool_calls": e.max_tool_calls, "budget_seconds": e.budget_seconds,
        "execution_mode": e.execution_mode, "branching": e.branching,
        "human_approved": e.human_approved, "created_at": old_time,
    }
    import hashlib, hmac as _hmac
    from maelstrom_gate.envelope import _canonical_hash
    sig = _hmac.new(KEY.encode(), _canonical_hash(old_data), hashlib.sha256).hexdigest()
    old_env = AuthorizationEnvelope(
        envelope_id=e.envelope_id, context_id=e.context_id,
        tool_name=e.tool_name, allowed_tools=e.allowed_tools,
        max_tool_calls=e.max_tool_calls, max_retries=e.max_retries,
        budget_seconds=e.budget_seconds, execution_mode=e.execution_mode,
        branching=e.branching, human_approved=e.human_approved,
        created_at=old_time, signature=sig,
    )
    # Signature is valid but envelope is expired
    assert verify_envelope(old_env, KEY)
    valid, reason = verify_envelope_fresh(old_env, KEY, max_age_seconds=300)
    assert valid is False
    assert "expired" in reason


def test_verify_fresh_no_timestamp():
    """Envelope with created_at=0 should fail freshness check."""
    from maelstrom_gate.envelope import verify_envelope_fresh
    # Legacy envelope without timestamp — manually construct
    legacy = AuthorizationEnvelope(
        envelope_id="e1", context_id="c1", tool_name="r",
        allowed_tools=("r",), signature="fake",
    )
    valid, reason = verify_envelope_fresh(legacy, KEY)
    assert valid is False
    assert reason in ("signature_invalid", "no_timestamp")


def test_envelope_deterministic_fields():
    """Two envelopes for the same tool/mode/context should have same constraints
    (different IDs and signatures due to UUID)."""
    tool = Tool("r", execution_class="read_only")
    e1 = build_envelope(tool, 0.5, "ctx", KEY)
    e2 = build_envelope(tool, 0.5, "ctx", KEY)

    assert e1.budget_seconds == e2.budget_seconds
    assert e1.max_tool_calls == e2.max_tool_calls
    assert e1.execution_mode == e2.execution_mode
    assert e1.branching == e2.branching
    # But IDs and signatures differ (UUID)
    assert e1.envelope_id != e2.envelope_id
    assert e1.signature != e2.signature
