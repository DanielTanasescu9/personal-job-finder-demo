"""Abstract scraper contract for documenting the production extension point.

This module intentionally contains no working network client or source adapter.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CollectionRequest:
    query: str
    location: str = ""
    country: str = ""
    page_limit: int = 1


@dataclass(frozen=True)
class CollectedJob:
    title: str
    company: str
    location: str
    description: str
    source_id: str
    source_url: str


@runtime_checkable
class ScraperAdapter(Protocol):
    """Interface only; implementations belong in a private source repository."""

    adapter_id: str

    def collect(self, request: CollectionRequest) -> list[CollectedJob]:
        """Collect records. The public demo ships no concrete implementation."""
        raise NotImplementedError("Production scraper adapters are intentionally omitted.")
