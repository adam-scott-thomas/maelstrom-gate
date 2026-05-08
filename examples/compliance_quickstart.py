#!/usr/bin/env python3
"""gate-compliance quickstart -- add audit trail to gate-core in 10 lines.

Shows how to record every gate decision with zero configuration.
Requires: pip install maelstrom-gate gate-compliance

STUB -- provided by Creator 1 (gate-compliance) as a quickstart for gate-core users.
"""
from gatekeeper import Gate, Tool
from gate_compliance.store import AuditStore
from gate_compliance.collector import ComplianceCollector
from gate_compliance.report import ComplianceReporter

# 1. Set up gate + compliance
gate = Gate()
gate.add_tool(Tool("read_file", execution_class="read_only"))
gate.add_tool(Tool("deploy", execution_class="high_impact"))
gate.add_tool(Tool("send_email", execution_class="external_action"))

store = AuditStore(":memory:")  # or "audit.db" for persistence
collector = ComplianceCollector(store, context_id="quickstart")

# 2. Record filter operations
for mode in [0.0, 0.4, 0.7, 1.0]:
    result = gate.filter(mode)
    collector.record_filter_result(mode, result)
    for t in result.suppressed:
        store.record_suppression(t.name, t.execution_class, mode, "quickstart")

# 3. Generate a report
reporter = ComplianceReporter(store)
print(reporter.text_report())

# Output: full compliance report with event counts, mode distribution,
# suppression rates, and top suppressed tools.
