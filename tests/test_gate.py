"""Tests for maelstrom-gate."""
import pytest
from gatekeeper import (
    Gate, Tool, ToolFilter, ExecutionClass,
    AuthorizationEnvelope, build_envelope, verify_envelope,
    validate_proposal, IngressResult,
)


class TestGate:
    def _gate(self):
        g = Gate()
        g.add_tools([
            Tool("read_file", execution_class="read_only"),
            Tool("analyze", execution_class="advisory"),
            Tool("send_email", execution_class="external_action"),
            Tool("write_file", execution_class="state_mutation"),
            Tool("deploy", execution_class="high_impact"),
        ])
        return g

    def test_calm_all_visible(self):
        assert len(self._gate().filter(0.1).visible) == 5

    def test_elevated_high_impact_gone(self):
        r = self._gate().filter(0.5)
        assert "deploy" in r.suppressed_names
        assert len(r.visible) == 4

    def test_crisis_three_suppressed(self):
        r = self._gate().filter(0.8)
        assert set(r.suppressed_names) == {"send_email", "write_file", "deploy"}
        assert set(r.visible_names) == {"read_file", "analyze"}

    def test_read_only_never_suppressed(self):
        assert "read_file" in self._gate().filter(1.0).visible_names

    def test_advisory_never_suppressed(self):
        assert "analyze" in self._gate().filter(1.0).visible_names

    def test_high_impact_boundary(self):
        assert "deploy" in self._gate().filter(0.35).visible_names
        assert "deploy" in self._gate().filter(0.36).suppressed_names

    def test_external_action_boundary(self):
        assert "send_email" in self._gate().filter(0.65).visible_names
        assert "send_email" in self._gate().filter(0.66).suppressed_names

    def test_unknown_class_treated_as_high_impact(self):
        g = Gate()
        g.add_tool(Tool("x", execution_class="evil"))
        assert "x" in g.filter(0.1).visible_names  # below T_DOWN, still visible
        assert "x" in g.filter(0.5).suppressed_names  # above T_DOWN, suppressed

    def test_custom_thresholds(self):
        g = Gate(thresholds={"high_impact": 0.10})
        g.add_tool(Tool("deploy", execution_class="high_impact"))
        assert "deploy" in g.filter(0.15).suppressed_names

    def test_to_catalog(self):
        c = self._gate().filter(0.1).to_catalog()
        assert len(c) == 5
        assert all("name" in e for e in c)

    def test_mode_clamped(self):
        assert self._gate().filter(5.0).mode == 1.0
        assert self._gate().filter(-1.0).mode == 0.0


KEY = "test-key"

class TestEnvelope:
    def test_build_verify(self):
        e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "c", KEY)
        assert verify_envelope(e, KEY)

    def test_wrong_key(self):
        e = build_envelope(Tool("r", execution_class="read_only"), 0.1, "c", KEY)
        assert not verify_envelope(e, "wrong")

    def test_normal_budget(self):
        e = build_envelope(Tool("r"), 0.1, "c", KEY)
        assert e.budget_seconds == 30

    def test_elevated_budget(self):
        e = build_envelope(Tool("r"), 0.5, "c", KEY)
        assert e.budget_seconds == 15
        assert e.execution_mode == "cautious"

    def test_crisis_budget(self):
        e = build_envelope(Tool("r"), 0.8, "c", KEY)
        assert e.budget_seconds == 7
        assert e.execution_mode == "minimal"

    def test_frozen(self):
        e = build_envelope(Tool("r"), 0.1, "c", KEY)
        with pytest.raises(AttributeError):
            e.budget_seconds = 999


class TestIngress:
    def _gate(self):
        g = Gate()
        g.add_tools([Tool("read_file", execution_class="read_only"),
                      Tool("deploy", execution_class="high_impact")])
        return g

    def test_valid(self):
        assert validate_proposal("read_file", self._gate(), 0.1).accepted

    def test_unknown(self):
        r = validate_proposal("hack", self._gate(), 0.1)
        assert not r.accepted and r.reason == "tool_not_found"

    def test_suppressed(self):
        r = validate_proposal("deploy", self._gate(), 0.5)
        assert not r.accepted and r.reason == "execution_class_suppressed"

    def test_visible_at_low_mode(self):
        assert validate_proposal("deploy", self._gate(), 0.1).accepted
