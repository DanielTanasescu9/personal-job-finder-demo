"""Fictional search fixtures used only by the public demo.

No HTTP clients, search API details, source URLs, or production query planning
are included in this module.
"""
from __future__ import annotations
from copy import deepcopy


def sample_search_results(sample_jobs: list[dict], query: str = "") -> list[dict]:
    """Return fixture records; this function performs no network activity."""
    items = deepcopy(sample_jobs[:3])
    for idx, item in enumerate(items, start=1):
        item["job_id"] = f"demo-search-{idx:03d}"
        item["source"] = "DEMO SAMPLE — Search Adapter"
        item["saved"] = False
        item["status"] = "New"
        item["demo_sample"] = True
        item["description_quality"] = "Fictional sample; not fetched from a live source"
        item["search_query_demo"] = str(query)[:200]
    return items


def simulated_search_status() -> dict:
    """Return explicitly simulated statuses; never contact remote services."""
    return {
        "search-adapter-a": {"status": "demo", "count": 2, "message": "Fictional adapter status; no request sent."},
        "search-adapter-b": {"status": "demo", "count": 1, "message": "Fictional adapter status; no request sent."},
        "combined-search": {"status": "demo", "count": 3, "message": "Fixed fixture response; no search performed."},
    }
