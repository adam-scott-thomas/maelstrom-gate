"""Core gate logic — tool classification, suppression, and filtering.

Zero dependencies. Works with any agent framework.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

T_DOWN = 0.35
T_UP = 0.65


class ExecutionClass(str, Enum):
    READ_ONLY = "read_only"
    ADVISORY = "advisory"
    EXTERNAL_ACTION = "external_action"
    STATE_MUTATION = "state_mutation"
    HIGH_IMPACT = "high_impact"


SUPPRESSION_THRESHOLDS: dict[ExecutionClass, float | None] = {
    ExecutionClass.READ_ONLY: None,
    ExecutionClass.ADVISORY: None,
    ExecutionClass.EXTERNAL_ACTION: T_UP,
    ExecutionClass.STATE_MUTATION: T_UP,
    ExecutionClass.HIGH_IMPACT: T_DOWN,
}


@dataclass(frozen=True)
class Tool:
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
    visible: tuple[Tool, ...]
    suppressed: tuple[Tool, ...]
    mode: float
    mode_status: str
    thresholds: dict[str, float | None] = field(default_factory=dict)

    @property
    def visible_names(self) -> list[str]:
        return [t.name for t in self.visible]

    @property
    def suppressed_names(self) -> list[str]:
        return [t.name for t in self.suppressed]

    def to_catalog(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "execution_class": t.execution_class,
             "description": t.description, "inputs": t.inputs}
            for t in self.visible
        ]


def is_suppressed(execution_class: str, mode: float) -> bool:
    try:
        ec = ExecutionClass(execution_class)
    except ValueError:
        return True
    threshold = SUPPRESSION_THRESHOLDS.get(ec)
    if threshold is None:
        return False
    return mode > threshold


class Gate:
    def __init__(self, thresholds: dict[str, float | None] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._thresholds: dict[ExecutionClass, float | None] = dict(SUPPRESSION_THRESHOLDS)
        if thresholds:
            for name, val in thresholds.items():
                try:
                    self._thresholds[ExecutionClass(name)] = val
                except ValueError:
                    pass

    def add_tool(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def add_tools(self, tools: list[Tool]) -> None:
        for t in tools:
            self._tools[t.name] = t

    def remove_tool(self, name: str) -> None:
        self._tools.pop(name, None)

    def filter(self, mode: float) -> ToolFilter:
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
        return sorted(self._tools.values(), key=lambda t: t.name)
