"""Data contracts for an orchestration layer, not orchestration logic.

Production prompts, tool-routing policy, model control flow, ranking internals,
retry policy, and privileged tool implementations are intentionally excluded.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class OrchestrationRequest:
    query: str
    profile_id: str | None = None
    location: str = ""
    max_results: int = 20


@dataclass
class OrchestrationResult:
    items: list[dict[str, Any]] = field(default_factory=list)
    status: str = "not_implemented"
    warnings: list[str] = field(default_factory=list)
    demo: bool = True


@runtime_checkable
class Orchestrator(Protocol):
    """Interface for the private orchestrator implementation."""

    def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        raise NotImplementedError("Production orchestrator logic is intentionally omitted.")
