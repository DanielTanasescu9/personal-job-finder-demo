"""Safe public view of the scraper registry.

Only generic adapter slots are shown. No real source names, URLs, API recipes,
HTML selectors, parser code, request headers or retry logic are exposed.
"""
from __future__ import annotations

DEMO_ADAPTER_SLOTS = (
    {"adapter_id": "collector-a", "implementation_included": False, "status": "mock"},
    {"adapter_id": "collector-b", "implementation_included": False, "status": "mock"},
    {"adapter_id": "collector-c", "implementation_included": False, "status": "mock"},
)


def get_production_adapters() -> list:
    """There are deliberately no active production adapters in this release."""
    return []


def registry_summary() -> dict:
    return {"demo": True, "registered_slots": list(DEMO_ADAPTER_SLOTS), "active_adapters": 0}
