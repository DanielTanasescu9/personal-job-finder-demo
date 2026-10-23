"""Generic local-model runtime interface without runtime implementation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ModelSelection:
    model_id: str
    path: str
    format: str


@dataclass
class RuntimeStatus:
    state: str = "not_implemented"
    message: str = "No model runtime is included in the public demo."
    details: dict[str, Any] | None = None


@runtime_checkable
class ModelRuntime(Protocol):
    def activate(self, selection: ModelSelection) -> RuntimeStatus:
        raise NotImplementedError("Production model runtime is intentionally omitted.")

    def generate(self, prompt: str) -> str:
        raise NotImplementedError("Production model inference is intentionally omitted.")

    def stop(self) -> RuntimeStatus:
        raise NotImplementedError("No real runtime is part of the public demo.")
