"""Core gate logic -- tool classification, suppression, and filtering.

Implements SPEC.md Sections 2-5 and 7:
- Five execution classes (Section 2)
- Suppression rule: mode > threshold (Section 3)
- Default thresholds (Section 4)
- Mode zones: normal, elevated, crisis (Section 5)
- Filter result structure (Section 7)

Zero dependencies. Works with any agent framework.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Zone boundaries (SPEC.md Section 5)
T_DOWN = 0.35
T_UP = 0.65


class ExecutionClass(str, Enum):
    """Tool execution class -- classifies side-effect severity.

    See SPEC.md Section 2 for descriptions.
    """
    READ_ONLY = "read_only"
    ADVISORY = "advisory"
    EXTERNAL_ACTION = "external_action"
    STATE_MUTATION = "state_mutation"
    HIGH_IMPACT = "high_impact"


# Default suppression thresholds (SPEC.md Section 4).
# None means the class is never suppressed.
SUPPRESSION_THRESHOLDS: dict[ExecutionClass, float | None] = {
    ExecutionClass.READ_ONLY: None,
    ExecutionClass.ADVISORY: None,
    ExecutionClass.EXTERNAL_ACTION: T_UP,
    ExecutionClass.STATE_MUTATION: T_UP,
    ExecutionClass.HIGH_IMPACT: T_DOWN,
}


@dataclass(frozen=True)
class Tool:
    """A tool registered with the gate.

    Conforms to schema/tool.schema.json. The ``execution_class`` field
    determines when this tool is suppressed. Unrecognized classes are
    treated as ``high_impact`` per SPEC.md Section 2.
    """
    name: str
    execution_class: str = "read_only"
    description: str = ""
    inputs: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def _exec_class(self) -> ExecutionClass:
        try:
            return ExecutionClass(self.execution_class)
        except ValueError:
            return ExecutionClass.HIGH_IMPACT


@dataclass(frozen=True)
class ToolFilter:
    """Result of a gate filter operation.

    Conforms to schema/filter-result.schema.json (SPEC.md Section 7).
    Contains the visible tools, suppressed tools, mode value, zone name,
    and the thresholds that were applied.
    """
    visible: tuple[Tool, ...]
    suppressed: tuple[Tool, ...]
    mode: float
    mode_status: str
    thresholds: dict[str, float | None] = field(default_factory=dict)

    @property
    def visible_names(self) -> list[str]:
        """Names of tools that passed the gate."""
        return [t.name for t in self.visible]

    @property
    def suppressed_names(self) -> list[str]:
        """Names of tools that were suppressed."""
        return [t.name for t in self.suppressed]

    def to_catalog(self) -> list[dict[str, Any]]:
        """Export visible tools as dicts suitable for an LLM system prompt."""
        return [
            {"name": t.name, "execution_class": t.execution_class,
             "description": t.description, "inputs": t.inputs}
            for t in self.visible
        ]


def is_suppressed(execution_class: str, mode: float) -> bool:
    """Check whether a tool with the given class is suppressed at the given mode.

    Implements the suppression rule from SPEC.md Section 3:
    a tool is suppressed when mode > threshold for its execution class.
    Unrecognized classes are treated as high_impact.
    """
    try:
        ec = ExecutionClass(execution_class)
    except ValueError:
        return True
    threshold = SUPPRESSION_THRESHOLDS.get(ec)
    if threshold is None:
        return False
    return mode > threshold


class Gate:
    """The runtime governance gate.

    Register tools, then call ``filter(mode)`` to get the tools visible at
    the current threat level. Suppressed tools are removed from the result
    before the manifest reaches the language model.

    Implements SPEC.md Sections 3-5 and 10 (conformance).
    """

    def __init__(self, thresholds: dict[str, float | None] | None = None) -> None:
        """Initialize the gate with optional custom thresholds.

        Args:
            thresholds: Override default suppression thresholds. Keys are
                execution class names, values are threshold floats or None
                (never suppress). Unrecognized keys are ignored.
        """
        self._tools: dict[str, Tool] = {}
        self._thresholds: dict[ExecutionClass, float | None] = dict(SUPPRESSION_THRESHOLDS)
        if thresholds:
            for name, val in thresholds.items():
                try:
                    self._thresholds[ExecutionClass(name)] = val
                except ValueError:
                    pass

    def add_tool(self, tool: Tool) -> None:
        """Register a single tool with the gate."""
        self._tools[tool.name] = tool

    def add_tools(self, tools: list[Tool]) -> None:
        """Register multiple tools with the gate."""
        for t in tools:
            self._tools[t.name] = t

    def remove_tool(self, name: str) -> None:
        """Remove a tool from the gate by name. No-op if not found."""
        self._tools.pop(name, None)

    def filter(self, mode: float) -> ToolFilter:
        """Filter registered tools at the given mode level.

        Returns a ``ToolFilter`` containing visible tools, suppressed tools,
        the clamped mode value, the mode zone name, and effective thresholds.

        The mode value is clamped to [0.0, 1.0] per SPEC.md Section 10.
        """
        mode = max(0.0, min(1.0, mode))
        visible, suppressed = [], []
        for tool in sorted(self._tools.values(), key=lambda t: t.name):
            ec = tool._exec_class
            th = self._thresholds.get(ec)
            if th is not None and mode > th:
                suppressed.append(tool)
            else:
                visible.append(tool)
        if mode > T_UP:
            status = "crisis"
        elif mode > T_DOWN:
            status = "elevated"
        else:
            status = "normal"
        return ToolFilter(
            visible=tuple(visible), suppressed=tuple(suppressed),
            mode=mode, mode_status=status,
            thresholds={ec.value: th for ec, th in self._thresholds.items()},
        )

    @property
    def tools(self) -> list[Tool]:
        """All registered tools, sorted by name."""
        return sorted(self._tools.values(), key=lambda t: t.name)
