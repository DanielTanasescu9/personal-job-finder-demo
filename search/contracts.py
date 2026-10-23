"""Generic search-provider contract without endpoint details or credentials."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SearchRequest:
    query: str
    language: str = "all"
    page: int = 1


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class SearchProvider(Protocol):
    def search(self, request: SearchRequest) -> list[SearchResult]:
        raise NotImplementedError("The live search-provider implementation is not included.")
