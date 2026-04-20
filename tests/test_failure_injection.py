"""Failure injection tests for gate-core — the foundation must be unbreakable.

Tests for:
- Empty gate (no tools registered)
- Duplicate tool names
- Tools with empty/weird names
- Extreme mode values
- Threshold edge cases
- ToolFilter immutability
- Concurrent filter calls
- is_suppressed() edge cases
- Zone boundary precision
"""
import threading
import pytest
from maelstrom_gate import Gate, Tool, ToolFilter, ExecutionClass
from maelstrom_gate.core import is_suppressed, T_DOWN, T_UP, SUPPRESSION_THRESHOLDS


# --- Empty gate ---


def test_filter_no_tools():
    g = Gate()
    r = g.filter(0.5)
    assert r.visible == ()
    assert r.suppressed == ()
    assert r.mode == 0.5
    assert r.mode_zone == "elevated"


def test_tools_property_empty():
    g = Gate()
    assert g.tools == []


# --- Tool name edge cases ---


def test_empty_tool_name():
    g = Gate()
    g.add_tool(Tool("", execution_class="read_only"))
    assert "" in g.filter(0.0).visible_names


def test_duplicate_tool_name_overwrites():
    g = Gate()
    g.add_tool(Tool("x", execution_class="read_only", description="v1"))
    g.add_tool(Tool("x", execution_class="high_impact", description="v2"))
    # Should have only one tool, with the second registration winning
    assert len(g.tools) == 1
    r = g.filter(0.5)
    assert "x" in r.suppressed_names  # high_impact at 0.5


def test_tool_with_special_chars():
    g = Gate()
    g.add_tool(Tool("tool/with:special$chars!", execution_class="read_only"))
    assert "tool/with:special$chars!" in g.filter(0.0).visible_names


def test_remove_nonexistent_tool():
    g = Gate()
    g.add_tool(Tool("a", execution_class="read_only"))
    g.remove_tool("nonexistent")  # should not raise
    assert len(g.tools) == 1


def test_add_tools_bulk_empty():
    g = Gate()
    g.add_tools([])
    assert len(g.tools) == 0


# --- Mode edge cases ---


def test_mode_negative_clamped():
    g = Gate()
    g.add_tool(Tool("x", execution_class="high_impact"))
    r = g.filter(-100.0)
    assert r.mode == 0.0
    assert "x" in r.visible_names  # mode 0 = below all thresholds


def test_mode_very_large_clamped():
    g = Gate()
    g.add_tool(Tool("x", execution_class="read_only"))
    r = g.filter(999.0)
    assert r.mode == 1.0
    assert "x" in r.visible_names  # read_only never suppressed


def test_mode_exactly_zero():
    g = Gate()
    g.add_tool(Tool("x", execution_class="high_impact"))
    r = g.filter(0.0)
    assert r.mode_zone == "normal"
    assert "x" in r.visible_names


def test_mode_exactly_one():
    g = Gate()
    g.add_tool(Tool("r", execution_class="read_only"))
    g.add_tool(Tool("d", execution_class="high_impact"))
    r = g.filter(1.0)
    assert r.mode_zone == "crisis"
    assert "r" in r.visible_names
    assert "d" in r.suppressed_names


# --- Zone boundary precision ---


def test_zone_boundary_t_down():
    g = Gate()
    g.add_tool(Tool("x", execution_class="read_only"))
    assert g.filter(T_DOWN).mode_zone == "normal"
    assert g.filter(T_DOWN + 0.001).mode_zone == "elevated"


def test_zone_boundary_t_up():
    g = Gate()
    g.add_tool(Tool("x", execution_class="read_only"))
    assert g.filter(T_UP).mode_zone == "elevated"
    assert g.filter(T_UP + 0.001).mode_zone == "crisis"


def test_suppression_boundary_high_impact():
    g = Gate()
    g.add_tool(Tool("x", execution_class="high_impact"))
    assert "x" in g.filter(T_DOWN).visible_names      # at boundary = visible
    assert "x" in g.filter(T_DOWN + 0.001).suppressed_names  # above = suppressed


def test_suppression_boundary_external_action():
    g = Gate()
    g.add_tool(Tool("x", execution_class="external_action"))
    assert "x" in g.filter(T_UP).visible_names         # at boundary = visible
    assert "x" in g.filter(T_UP + 0.001).suppressed_names    # above = suppressed


# --- Custom thresholds ---


def test_custom_threshold_none_never_suppresses():
    g = Gate(thresholds={"high_impact": None})
    g.add_tool(Tool("deploy", execution_class="high_impact"))
    assert "deploy" in g.filter(1.0).visible_names  # None = never suppress


def test_custom_threshold_zero_always_suppresses():
    g = Gate(thresholds={"read_only": 0.0})
    g.add_tool(Tool("read", execution_class="read_only"))
    assert "read" in g.filter(0.01).suppressed_names  # mode > 0.0 = suppressed
    assert "read" in g.filter(0.0).visible_names       # mode == 0.0 = visible


def test_custom_threshold_unknown_class_ignored():
    g = Gate(thresholds={"totally_fake": 0.5})
    g.add_tool(Tool("x", execution_class="read_only"))
    r = g.filter(0.5)
    # Should work fine, unknown threshold key just ignored
    assert "x" in r.visible_names


# --- ToolFilter immutability ---


def test_toolfilter_frozen():
    r = Gate().filter(0.0)
    with pytest.raises(AttributeError):
        r.mode = 0.5


# --- is_suppressed() edge cases ---


def test_is_suppressed_all_classes():
    assert not is_suppressed("read_only", 1.0)
    assert not is_suppressed("advisory", 1.0)
    assert is_suppressed("external_action", 0.66)
    assert is_suppressed("state_mutation", 0.66)
    assert is_suppressed("high_impact", 0.36)


def test_is_suppressed_unknown_class():
    assert is_suppressed("totally_unknown", 0.0)  # unknown = always suppressed


def test_is_suppressed_at_boundary():
    assert not is_suppressed("high_impact", T_DOWN)      # at threshold = not suppressed
    assert is_suppressed("high_impact", T_DOWN + 0.001)  # above = suppressed


# --- Concurrent filter ---


def test_concurrent_filter_calls():
    g = Gate()
    for i in range(20):
        g.add_tool(Tool(f"tool_{i}", execution_class=["read_only", "advisory", "external_action", "state_mutation", "high_impact"][i % 5]))

    errors = []
    results = []

    def do_filter(mode):
        try:
            r = g.filter(mode)
            results.append(r)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=do_filter, args=(i / 10,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(results) == 10


# --- to_openai_tools edge cases ---


def test_to_openai_tools_empty_inputs():
    g = Gate()
    g.add_tool(Tool("x", execution_class="read_only", description="test"))
    tools = g.filter(0.0).to_openai_tools()
    assert len(tools) == 1
    assert tools[0]["function"]["parameters"]["properties"] == {}


def test_to_openai_tools_no_description():
    g = Gate()
    g.add_tool(Tool("x", execution_class="read_only"))
    tools = g.filter(0.0).to_openai_tools()
    assert tools[0]["function"]["description"] == "x"  # falls back to name


# --- Envelope edge cases ---

from maelstrom_gate.envelope import build_envelope, verify_envelope, AuthorizationEnvelope


def test_envelope_empty_signing_key():
    """Empty signing key should still produce a valid envelope."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", "")
    assert verify_envelope(e, "")
    assert not verify_envelope(e, "any-other-key")


def test_envelope_unicode_context():
    """Unicode context IDs should work."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx-\u2603-snowman", "key")
    assert verify_envelope(e, "key")
    assert e.context_id == "ctx-\u2603-snowman"


def test_envelope_extra_tools():
    """Extra tools should be included in allowed_tools."""
    e = build_envelope(
        Tool("main", execution_class="read_only"), 0.1, "ctx", "key",
        extra_tools=("helper_a", "helper_b"),
    )
    assert e.allowed_tools == ("main", "helper_a", "helper_b")
    assert verify_envelope(e, "key")


def test_envelope_tamper_tool_name():
    """Tampering with tool_name should break verification."""
    e = build_envelope(Tool("read", execution_class="read_only"), 0.1, "ctx", "key")
    tampered = AuthorizationEnvelope(
        envelope_id=e.envelope_id, context_id=e.context_id,
        tool_name="HACKED",  # tampered
        allowed_tools=e.allowed_tools, max_tool_calls=e.max_tool_calls,
        max_retries=e.max_retries, budget_seconds=e.budget_seconds,
        execution_mode=e.execution_mode, branching=e.branching,
        human_approved=e.human_approved, signature=e.signature,
    )
    assert not verify_envelope(tampered, "key")


def test_envelope_tamper_budget():
    """Tampering with budget should break verification."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", "key")
    tampered = AuthorizationEnvelope(
        envelope_id=e.envelope_id, context_id=e.context_id,
        tool_name=e.tool_name, allowed_tools=e.allowed_tools,
        max_tool_calls=e.max_tool_calls, max_retries=e.max_retries,
        budget_seconds=9999,  # tampered
        execution_mode=e.execution_mode, branching=e.branching,
        human_approved=e.human_approved, signature=e.signature,
    )
    assert not verify_envelope(tampered, "key")


def test_envelope_tamper_human_approved():
    """Tampering with human_approved should break verification."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", "key", human_approved=False)
    tampered = AuthorizationEnvelope(
        envelope_id=e.envelope_id, context_id=e.context_id,
        tool_name=e.tool_name, allowed_tools=e.allowed_tools,
        max_tool_calls=e.max_tool_calls, max_retries=e.max_retries,
        budget_seconds=e.budget_seconds, execution_mode=e.execution_mode,
        branching=e.branching,
        human_approved=True,  # tampered
        signature=e.signature,
    )
    assert not verify_envelope(tampered, "key")


def test_envelope_branching_by_class():
    """read_only and advisory get auto branching; others get deny."""
    e_ro = build_envelope(Tool("r", execution_class="read_only"), 0.1, "ctx", "key")
    e_ad = build_envelope(Tool("a", execution_class="advisory"), 0.1, "ctx", "key")
    e_hi = build_envelope(Tool("d", execution_class="high_impact"), 0.1, "ctx", "key")
    e_sm = build_envelope(Tool("w", execution_class="state_mutation"), 0.1, "ctx", "key")
    assert e_ro.branching == "auto"
    assert e_ad.branching == "auto"
    assert e_hi.branching == "deny"
    assert e_sm.branching == "deny"


def test_envelope_crisis_tightens_branching():
    """Even auto-branching classes get deny in crisis."""
    e = build_envelope(Tool("r", execution_class="read_only"), 0.8, "ctx", "key")
    assert e.branching == "deny"
    assert e.execution_mode == "minimal"


# --- Ingress edge cases ---

from maelstrom_gate.ingress import validate_proposal, IngressResult


def test_ingress_empty_tool_name():
    """Validating empty string tool name against empty gate."""
    g = Gate()
    r = validate_proposal("", g, 0.0)
    assert not r.accepted
    assert r.reason == "tool_not_found"


def test_ingress_with_registered_empty_name():
    """Empty-named tool should be findable."""
    g = Gate()
    g.add_tool(Tool("", execution_class="read_only"))
    r = validate_proposal("", g, 0.0)
    assert r.accepted


def test_ingress_mode_clamping():
    """Ingress uses is_suppressed which doesn't clamp mode — verify behavior."""
    g = Gate()
    g.add_tool(Tool("deploy", execution_class="high_impact"))
    # Negative mode: below all thresholds
    r = validate_proposal("deploy", g, -1.0)
    assert r.accepted  # is_suppressed(-1.0) = False for high_impact (mode <= threshold)

    # Very high mode
    r2 = validate_proposal("deploy", g, 100.0)
    assert not r2.accepted


def test_ingress_result_frozen():
    """IngressResult should be immutable."""
    r = IngressResult(True)
    with pytest.raises(AttributeError):
        r.accepted = False
