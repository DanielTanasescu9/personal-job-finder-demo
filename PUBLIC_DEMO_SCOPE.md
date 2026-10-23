# Public Demo Scope: Real vs Mocked vs Private

This file is intended to prevent confusion between the public demonstration and the production application.

## Real and implemented in the demo

- Page rendering, navigation, CSS/JavaScript controls and local API routes.
- Local-only input validation for the demo backend.
- Editing and saving **demo** preferences/profile fields locally.
- Filtering and changing status on fictional job records.
- CSV export of the fictional records, with spreadsheet-formula escaping.
- Tests, sample fixtures and the abstract interface contracts.

## Mocked or simulated

- Job collection and source-health rows.
- SearXNG/web search result acquisition.
- Combined search/collector workflow, deduplication and matching scores.
- Candidate CV analysis and evidence explanations.
- Model catalog, compatibility, host hardware detection, runtime health and model activation.
- Orchestrator dependency checks and all AI-generated job analysis.

A button that says “Simulate” or “Demo only” only changes demo state or returns a fixture. It does not represent a successful external connection.

## Deliberately omitted and should stay private

- Concrete scraper implementations and source-specific API/HTML details.
- Production HTTP clients, source URLs, selectors, request profiles, API credentials, anti-blocking strategy and source-specific error recovery.
- The production orchestrator's prompts, tools, policies, workflow routing, score blending and internal matching logic.
- Production SearXNG connector configuration, real model runtime clients, inference prompts, hardware probing and container orchestration.
- User CVs, candidate profiles, application history, live job CSVs, secrets, logs and local machine paths.

## Extension contracts only

`scrapers/base.py`, `scrapers/registry.py`, `search/contracts.py`, `orchestrator/contracts.py` and `model_runtime/contracts.py` define abstract data shapes and interfaces. They contain no working production implementations and raise `NotImplementedError` where an implementation would be required.

## Why this split exists

The public demo is for explaining and previewing the product. The production app should live in a private repository with access controls. Public code cannot be made confidential through minification or frontend feature flags; if proprietary scraping or orchestration logic is placed in a public repository, people can inspect and copy it.
