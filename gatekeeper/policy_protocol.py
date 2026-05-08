"""Policy integration protocol for gate-core — STUB.

Defines the interface that any policy engine must implement
to integrate with Gate.filter(). This lives in gate-core so
the core doesn't need to depend on any specific policy package.

Seeded by Creator 4. Improvers: wire this into Gate.filter()
as an optional policy_engine parameter.
"""

from __future__ import annotations

from typing import Any, Protocol


class PolicyEvaluator(Protocol):
    """Protocol for policy engines that sit on top of gate-core.

    Any class implementing this protocol can be passed to Gate
    for policy-aware filtering without gate-core depending on
    the specific policy implementation.
    """

    def evaluate(self, tool_name: str, execution_class: str, context: dict[str, Any]) -> str:
        """Evaluate a tool against the policy.

        Returns "allow" or "deny".
        """
        ...

    def filter_tools(self, tools: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Filter a tool manifest through the policy.

        Returns {"allowed": [...], "denied": [...]}.
        """
        ...


# Usage sketch for Improvers:
#
#   class Gate:
#       def __init__(self, thresholds=None, policy: PolicyEvaluator | None = None):
#           self._policy = policy
#
#       def filter(self, mode: float, context: dict | None = None) -> ToolFilter:
#           # ... existing mode suppression ...
#           if self._policy and context:
#               # apply policy on top of mode results
#               ...
