#!/usr/bin/env python3
"""Public UI demo for Personal Job Finder.

This program intentionally contains no real scraper, search-engine, model-runtime,
or production-orchestrator implementation. All search/model responses are labelled
as simulated. It uses only the Python standard library.
"""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from demo_services.models import MODEL_SAMPLES, demo_catalog
from demo_services.search import sample_search_results, simulated_search_status

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("JOB_FINDER_PORT", "7860"))
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "demo_state.json"
FIXTURES_PATH = ROOT / "demo_fixtures" / "sample_jobs.json"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
LOCK = threading.RLock()

PAGES = {
    "/": ("dashboard", "Overview", "Public demo workspace", "Explore the interface using invented sample records; no live job search is performed.", "dashboard.html"),
    "/search": ("search", "Search demo", "Preview the discovery workflow", "Search actions return clearly labelled fixtures. They do not contact search engines or run collectors.", "search.html"),
    "/jobs": ("jobs", "Job tracker", "Sample job tracker", "Filter, save and update fictitious job records stored locally by this demo.", "jobs.html"),
    "/profile": ("profile", "CV & profile", "Preview candidate profiling", "Load a fictional sample profile or enter test data manually. This demo never uploads or parses your CV.", "profile.html"),
    "/models": ("models", "Model manager demo", "Preview model management", "Model choices and activation states are simulated; no local files are scanned and no model is loaded.", "models.html"),
    "/sources": ("sources", "Source health demo", "Preview service status", "Statuses describe demo adapters only. No scraper, SearXNG instance, orchestrator or model runtime is contacted.", "sources.html"),
    "/settings": ("settings", "Settings", "Demo preferences", "Preference forms are local demo state; they do not configure a real backend.", "settings.html"),
}

DEFAULT_SETTINGS = {
    "orchestrator_url": "DEMO ONLY — no production endpoint configured",
    "web_result_pages": 2, "language": "en-US", "location": "", "country": "",
    "radius_km": 0, "salary_min": "", "salary_currency": "DKK",
    "employment_types": ["full-time", "part-time", "contract"],
    "work_modes": ["onsite", "hybrid", "remote"], "include_remote_europe": True,
    "include_public_feeds": True, "use_model_matching": True,
    "use_ai_search_planning": True, "use_ai_job_briefs": True,
    "enrich_job_pages": True, "use_ai_for_cv": True,
    "max_harvest_pages": 2, "last_saved_at": ""
}
DEFAULT_PROFILE = {
    "target_direction": "", "search_terms": [],
    "candidate": {"name": "", "email": "", "phone": "", "headline": "", "summary": "",
        "years_experience": None, "preferred_titles": [], "preferred_locations": [], "skills": [], "tools": [],
        "experience": [], "projects": [], "education": [], "certifications": [], "languages": [],
        "achievements": [], "work_modes": ["onsite", "hybrid", "remote"]}
}
with FIXTURES_PATH.open("r", encoding="utf-8") as stream:
    SAMPLE_JOBS = json.load(stream)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clone(value):
    return json.loads(json.dumps(value))


def load_state() -> dict:
    with LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            saved = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                return saved
        except (OSError, json.JSONDecodeError):
            pass
        state = {"jobs": clone(SAMPLE_JOBS), "settings": clone(DEFAULT_SETTINGS),
                 "profile": clone(DEFAULT_PROFILE), "selected_model_id": None,
                 "activation": {"status": "demo", "message": "Demo only — no runtime has been started or model loaded."}}
        save_state(state)
        return state


def save_state(state: dict) -> None:
    with LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp = STATE_PATH.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, STATE_PATH)


def get_jobs(state: dict) -> list[dict]:
    return state.setdefault("jobs", clone(SAMPLE_JOBS))


def job_stats(jobs: list[dict]) -> dict:
    return {"total": len(jobs), "high_priority": sum(int(x.get("ranking_score", x.get("score", 0)) or 0) >= 65 for x in jobs),
            "saved": sum(x.get("status") == "Saved" for x in jobs), "applied": sum(x.get("status") == "Applied" for x in jobs)}


def render_page(path: str) -> bytes:
    page, title, heading, subtitle, filename = PAGES[path]
    base = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    content = (TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    for key, value in {"{{TITLE}}": title, "{{PAGE}}": page, "{{HEADING}}": heading,
                       "{{SUBTITLE}}": subtitle, "{{ACTION}}": "",
                       "{{CONTENT}}": content}.items():
        base = base.replace(key, value)
    return base.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "PJF-Public-Demo/0.1"

    def log_message(self, fmt, *args):
        print("[demo] " + (fmt % args))

    def send_bytes(self, data: bytes, content_type: str = "application/json; charset=utf-8", status: int = 200,
                   extra_headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), usb=()")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def valid_local_context(self) -> bool:
        try:
            host = urlparse("//" + self.headers.get("Host", ""))
            allowed = {"127.0.0.1", "localhost", "::1"}
            if (host.hostname or "").lower() not in allowed or host.port != int(self.server.server_address[1]):
                self.send_bytes(json_bytes({"error": "Use the local demo address only."}), status=403)
                return False
            origin = self.headers.get("Origin")
            if origin:
                origin_url = urlparse(origin)
                if origin_url.scheme != "http" or (origin_url.hostname or "").lower() not in allowed or origin_url.netloc.lower() != self.headers.get("Host", "").lower():
                    self.send_bytes(json_bytes({"error": "Cross-origin requests are not allowed."}), status=403)
                    return False
        except ValueError:
            self.send_bytes(json_bytes({"error": "Invalid local host."}), status=403)
            return False
        return True

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length <= 0 or length > 1_000_000:
            raise ValueError("JSON body must be between 1 byte and 1 MB")
        doc = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(doc, dict):
            raise ValueError("JSON body must be an object")
        return doc

    def do_GET(self):
        if not self.valid_local_context():
            return
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self.send_bytes(render_page("/"), "text/html; charset=utf-8")
        elif path in PAGES:
            self.send_bytes(render_page(path), "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            target = (STATIC_DIR / path.removeprefix("/static/")).resolve()
            if not str(target).startswith(str(STATIC_DIR.resolve()) + os.sep) or not target.is_file():
                self.send_bytes(json_bytes({"error": "Not found"}), status=404); return
            mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self.send_bytes(target.read_bytes(), mime + ("; charset=utf-8" if mime.startswith(("text/", "application/javascript")) else ""))
        elif path == "/api/health":
            self.send_bytes(json_bytes({"status": "demo", "mode": "public-demo", "demo": True, "real_scraping": False,
                "real_web_search": False, "real_model_inference": False, "persistent_local_state": True,
                "message": "Only fictitious fixtures and simulated service responses are enabled."}))
        elif path == "/api/jobs":
            state = load_state(); jobs = get_jobs(state)
            self.send_bytes(json_bytes({"jobs": jobs, "stats": job_stats(jobs), "demo": True}))
        elif path == "/api/status":
            self.send_bytes(json_bytes({"running": False, "last_search": "", "demo": True,
                "sources": simulated_search_status(),
                "requested_terms": [], "page_depth": 0}))
        elif path == "/api/profile":
            state = load_state(); self.send_bytes(json_bytes({**state.get("profile", clone(DEFAULT_PROFILE)), "demo": True}))
        elif path == "/api/settings":
            state = load_state(); self.send_bytes(json_bytes({**state.get("settings", clone(DEFAULT_SETTINGS)),
                "model_name": "Fictional demo model (not loaded)", "model_runtime": "demo", "model_parameter_billions": 0, "demo": True}))
        elif path == "/api/models":
            self.send_bytes(json_bytes(self.model_catalog()))
        elif path in {"/api/models/activation", "/api/models/runtime-health"}:
            state = load_state(); self.send_bytes(json_bytes({**state.get("activation", {}), "status": "demo", "demo": True,
                "message": "Demo only — no model process is launched and no model weights are read."}))
        elif path == "/api/shortcuts":
            query = parse_qs(parsed.query).get("query", [""])[0]
            self.send_bytes(json_bytes({"items": [{"name": "Demo search result", "url": "https://example.invalid/demo-search", "query": query, "demo": True}]}))
        elif path == "/download.csv":
            state = load_state(); rows = get_jobs(state)
            columns = ["job_id", "title", "company", "location", "source", "url", "description", "score", "ranking_score", "status", "demo_sample"]
            buffer = io.StringIO(newline=""); writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\r\n"); writer.writeheader()
            for row in rows:
                safe = {}
                for key in columns:
                    value = str(row.get(key, ""))
                    if key not in {"score", "ranking_score", "demo_sample"} and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
                        value = "'" + value
                    safe[key] = value
                writer.writerow(safe)
            self.send_bytes(buffer.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", extra_headers={"Content-Disposition": "attachment; filename=personal-job-finder-demo.csv"})
        else:
            self.send_bytes(json_bytes({"error": "Not found"}), status=404)

    def model_catalog(self):
        state = load_state()
        return demo_catalog(state.get("selected_model_id"))

    def do_POST(self):
        if not self.valid_local_context():
            return
        path = urlparse(self.path).path
        try:
            body = self.read_json()
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.send_bytes(json_bytes({"error": str(exc)}), status=400); return
        state = load_state()
        if path == "/api/settings":
            allowed = set(DEFAULT_SETTINGS) - {"orchestrator_url", "last_saved_at"}
            settings = clone(state.get("settings", DEFAULT_SETTINGS))
            for key in allowed:
                if key in body:
                    settings[key] = body[key]
            settings["orchestrator_url"] = DEFAULT_SETTINGS["orchestrator_url"]
            settings["last_saved_at"] = now_iso(); state["settings"] = settings; save_state(state)
            self.send_bytes(json_bytes({**settings, "demo": True}))
        elif path == "/api/settings/reset":
            state["settings"] = clone(DEFAULT_SETTINGS); save_state(state); self.send_bytes(json_bytes({**DEFAULT_SETTINGS, "demo": True}))
        elif path == "/api/profile":
            profile = clone(DEFAULT_PROFILE)
            candidate = body.get("candidate") if isinstance(body.get("candidate"), dict) else {}
            profile["target_direction"] = str(body.get("target_direction", ""))[:500]
            profile["search_terms"] = [str(x)[:120] for x in candidate.get("preferred_titles", []) if isinstance(x, str)][:30]
            # User-entered demo profile is stored locally, but no CV file or CV text is accepted.
            profile["candidate"] = {k: candidate.get(k, DEFAULT_PROFILE["candidate"].get(k)) for k in DEFAULT_PROFILE["candidate"]}
            state["profile"] = profile; save_state(state)
            self.send_bytes(json_bytes({"profile": profile, "rescored_jobs": len(get_jobs(state)), "demo": True}))
        elif path in {"/api/websearch", "/api/hybrid-search", "/api/search"}:
            query = str(body.get("query", body.get("terms", "")))[:500]
            results = sample_search_results(SAMPLE_JOBS, query)
            saved_count = 0
            if body.get("save_results", True):
                known = {str(job.get("job_id")) for job in get_jobs(state)}
                for item in results:
                    if item["job_id"] not in known:
                        get_jobs(state).append(item); saved_count += 1
                save_state(state)
            if path == "/api/search":
                response = {"ok": True, "matched_in_run": len(results), "summary": {"new": len(results), "refreshed": 0},
                    "message": "DEMO ONLY — sample records returned; no scraper made a network request.", "demo": True}
            else:
                response = {"ok": True, "demo": True, "results": results, "count": len(results), "saved_count": saved_count,
                    "scraper_count": 3 if path == "/api/hybrid-search" else 0,
                    "web_count": 3 if path == "/api/hybrid-search" else len(results),
                    "unique_count": len(results), "descriptions_enriched": 0, "search_plan": [], "errors": [],
                    "message": "DEMO ONLY — these are fictional fixture records. No scrapers, web search, orchestrator or model were called."}
            self.send_bytes(json_bytes(response))
        elif path in {"/api/searxng/test", "/api/orchestrator/test"}:
            response = {"ok": False, "status": "demo", "demo": True,
                "result_count": 3, "endpoint": "SIMULATED — no request sent", "model_name": "Fictional demo model (not loaded)",
                "message": "Demo only — no service was contacted.",
                "dependencies": {"orchestrator": {"status": "demo", "message": "No orchestrator was contacted."},
                    "model": {"status": "demo", "runtime": "demo", "message": "No model was loaded."},
                    "searxng": {"status": "demo", "message": "No web search was made."}}}
            self.send_bytes(json_bytes(response))
        elif path == "/api/jobs/save-result":
            incoming = body.get("job")
            if not isinstance(incoming, dict) or not incoming.get("title"):
                self.send_bytes(json_bytes({"error": "A sample job object is required."}), status=400); return
            url = str(incoming.get("url", ""))
            if not url.startswith("https://example.invalid/"):
                self.send_bytes(json_bytes({"error": "Demo mode accepts only reserved example.invalid URLs."}), status=400); return
            job = clone(incoming); job["demo_sample"] = True; job["status"] = "New"
            job["job_id"] = str(job.get("job_id") or f"demo-saved-{len(get_jobs(state))+1:03d}")
            if not any(str(x.get("job_id")) == job["job_id"] for x in get_jobs(state)):
                get_jobs(state).append(job)
            save_state(state); self.send_bytes(json_bytes({"ok": True, "job_id": job["job_id"], "demo": True}))
        elif path == "/api/status":
            job_id = str(body.get("job_id", "")); status = str(body.get("status", ""))
            if status not in {"New", "Saved", "Applied", "Not relevant"}:
                self.send_bytes(json_bytes({"error": "Invalid demo status."}), status=400); return
            found = False
            for item in get_jobs(state):
                if str(item.get("job_id")) == job_id:
                    item["status"] = status; found = True; break
            if not found:
                self.send_bytes(json_bytes({"error": "Sample job was not found."}), status=404); return
            save_state(state); self.send_bytes(json_bytes({"ok": True, "status": status, "demo": True}))
        elif path == "/api/jobs/delete-status":
            before = len(get_jobs(state)); state["jobs"] = [j for j in get_jobs(state) if j.get("status") != "Not relevant"]
            deleted = before - len(state["jobs"]); save_state(state); self.send_bytes(json_bytes({"ok": True, "deleted": deleted, "demo": True}))
        elif path == "/api/models/scan":
            self.send_bytes(json_bytes(self.model_catalog()))
        elif path == "/api/models/select":
            model_id = str(body.get("model_id", ""))
            if model_id not in {m["id"] for m in MODEL_SAMPLES}:
                self.send_bytes(json_bytes({"error": "Unknown demo model."}), status=400); return
            state["selected_model_id"] = model_id
            state["activation"] = {"status": "demo", "message": "Selection saved for UI demonstration. No model process was started."}
            save_state(state); self.send_bytes(json_bytes({"ok": True, "demo": True}))
        elif path == "/api/models/activate":
            state["activation"] = {"status": "demo", "message": "Activation simulated only. No container, runtime or model was started."}
            save_state(state); self.send_bytes(json_bytes({**state["activation"], "demo": True}))
        elif path == "/api/models/stop":
            state["activation"] = {"status": "demo", "message": "Demo state reset; there was no model process to stop."}
            save_state(state); self.send_bytes(json_bytes({**state["activation"], "demo": True}))
        elif path == "/api/cv/analyze":
            # JSON only; file uploads are intentionally not supported by this demo.
            self.send_bytes(json_bytes({"error": "CV file processing is intentionally disabled in the public demo. Use 'Load sample CV profile' in the UI."}), status=410)
        else:
            self.send_bytes(json_bytes({"error": "Endpoint is not implemented in the public demo."}), status=404)


def json_bytes(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Personal Job Finder — PUBLIC DEMO")
    print("No live scrapers, web search, production orchestrator or model runtime is included.")
    print(f"Open http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping public demo…")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
