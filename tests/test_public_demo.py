from __future__ import annotations
import csv
import io
import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import main
from demo_services.models import demo_catalog
from demo_services.search import sample_search_results, simulated_search_status
from orchestrator.contracts import OrchestrationRequest, OrchestrationResult, Orchestrator
from model_runtime.contracts import ModelRuntime, ModelSelection
from scrapers.base import CollectionRequest, ScraperAdapter
from scrapers.registry import get_production_adapters, registry_summary
from search.contracts import SearchProvider, SearchRequest


PROJECT = Path(__file__).resolve().parents[1]


class QuietHandler(main.Handler):
    def log_message(self, fmt, *args):
        pass


class PublicDemoHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.patch_data = patch.multiple(
            main, DATA_DIR=Path(self.tempdir.name),
            STATE_PATH=Path(self.tempdir.name) / "demo_state.json"
        )
        self.patch_data.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.patch_data.stop()
        self.tempdir.cleanup()

    def get(self, path, headers=None):
        request = urllib.request.Request(self.base + path, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def post(self, path, payload, headers=None):
        merged = {"Content-Type": "application/json"}
        merged.update(headers or {})
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data, headers=merged, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def json_get(self, path):
        status, headers, body = self.get(path)
        self.assertEqual(status, 200)
        return json.loads(body)

    def json_post(self, path, payload):
        status, headers, body = self.post(path, payload)
        self.assertEqual(status, 200, body.decode("utf-8", "replace"))
        return json.loads(body)

    def test_all_pages_render_and_disclose_demo_mode(self):
        for path in main.PAGES:
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                text = body.decode("utf-8")
                self.assertEqual(status, 200)
                self.assertIn("PUBLIC DEMO ONLY", text)
                self.assertIn("simulated", text.lower())
                self.assertIn("/static/app.css", text)
                self.assertIn("/static/app.js", text)

    def test_html_ids_are_unique_and_have_no_spaces(self):
        for path in main.PAGES:
            with self.subTest(path=path):
                _, _, body = self.get(path)
                html = body.decode("utf-8")
                ids = re.findall(r'\bid="([^"]+)"', html)
                self.assertEqual(len(ids), len(set(ids)), f"Duplicate HTML id on {path}")
                self.assertTrue(all(not re.search(r"\s", value) for value in ids), f"Invalid HTML id on {path}")

    def test_frontend_does_not_directly_call_external_services(self):
        js = (PROJECT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"fetch\(\s*['\"]https?://")
        self.assertNotRegex(js, r"XMLHttpRequest|WebSocket\s*\(")
        for page in main.PAGES:
            _, _, body = self.get(page)
            self.assertNotRegex(body.decode("utf-8"), r'href=["\']https?://')

    def test_static_assets_are_served_locally(self):
        for path, expected in [("/static/app.css", b".app-header"), ("/static/app.js", b"DOMContentLoaded")]:
            status, _, body = self.get(path)
            self.assertEqual(status, 200)
            self.assertIn(expected, body)

    def test_health_explicitly_disables_real_integrations(self):
        health = self.json_get("/api/health")
        self.assertEqual(health["mode"], "public-demo")
        self.assertFalse(health["real_scraping"])
        self.assertFalse(health["real_web_search"])
        self.assertFalse(health["real_model_inference"])
        self.assertTrue(health["demo"] if "demo" in health else True)

    def test_job_records_are_fictional_and_use_reserved_invalid_urls(self):
        jobs = self.json_get("/api/jobs")["jobs"]
        self.assertGreaterEqual(len(jobs), 3)
        for job in jobs:
            self.assertTrue(job["demo_sample"])
            self.assertIn("example.invalid", job["url"])
            self.assertIn("Fictional", job["company"])

    def test_search_returns_fixtures_without_live_search(self):
        data = self.json_post("/api/websearch", {"query": "accountant in example place", "save_results": False})
        self.assertTrue(data["demo"])
        self.assertEqual(data["count"], 3)
        self.assertIn("No scrapers, web search, orchestrator or model were called", data["message"])
        self.assertTrue(all("example.invalid" in item["url"] for item in data["results"]))

    def test_hybrid_and_collector_actions_are_simulated(self):
        hybrid = self.json_post("/api/hybrid-search", {"query": "sample", "save_results": False})
        collector = self.json_post("/api/search", {"terms": "sample"})
        self.assertTrue(hybrid["demo"])
        self.assertEqual(hybrid["scraper_count"], 3)
        self.assertTrue(collector["demo"])
        self.assertIn("network request", collector["message"].lower())

    def test_sample_search_helper_is_deterministic_and_marked(self):
        fixtures = json.loads((PROJECT / "demo_fixtures" / "sample_jobs.json").read_text(encoding="utf-8"))
        rows = sample_search_results(fixtures, "sample query")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["demo_sample"] for row in rows))
        self.assertEqual(rows[0]["search_query_demo"], "sample query")
        self.assertTrue(all(row["source"].startswith("DEMO SAMPLE") for row in rows))

    def test_save_search_result_only_accepts_reserved_invalid_domain(self):
        unsafe = {"job": {"title": "Fictional", "url": "https://example.com/real"}}
        status, _, body = self.post("/api/jobs/save-result", unsafe)
        self.assertEqual(status, 400)
        self.assertIn(b"example.invalid", body)
        good = {"job": {"job_id": "demo-new", "title": "Fictional role", "url": "https://example.invalid/demo/new"}}
        response = self.json_post("/api/jobs/save-result", good)
        self.assertTrue(response["demo"])
        self.assertIn("demo-new", {job["job_id"] for job in self.json_get("/api/jobs")["jobs"]})

    def test_job_status_updates_and_delete_are_local_persistent(self):
        sample = self.json_get("/api/jobs")["jobs"][0]
        update = self.json_post("/api/status", {"job_id": sample["job_id"], "status": "Saved"})
        self.assertTrue(update["demo"])
        updated = {j["job_id"]: j for j in self.json_get("/api/jobs")["jobs"]}[sample["job_id"]]
        self.assertEqual(updated["status"], "Saved")
        self.json_post("/api/status", {"job_id": sample["job_id"], "status": "Not relevant"})
        deleted = self.json_post("/api/jobs/delete-status", {"status": "Not relevant"})
        self.assertGreaterEqual(deleted["deleted"], 1)
        self.assertTrue(all(j.get("status") != "Not relevant" for j in self.json_get("/api/jobs")["jobs"]))

    def test_csv_export_is_csv_of_demo_data_and_formula_safe(self):
        job = {"job_id": "demo-formula", "title": "=CMD()", "company": "@SUM(1,2)",
               "url": "https://example.invalid/demo/formula"}
        self.json_post("/api/jobs/save-result", {"job": job})
        status, headers, payload = self.get("/download.csv")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers.get("Content-Type", ""))
        text = payload.decode("utf-8-sig")
        self.assertIn("' =CMD()", text) if "' =CMD()" in text else self.assertIn("'=CMD()", text)
        self.assertIn("example.invalid", text)

    def test_profile_is_local_demo_data_and_cv_analysis_is_disabled(self):
        profile = self.json_post("/api/profile", {"target_direction": "Fictional sample", "candidate": {"headline": "Not real", "skills": ["Sample skill"]}})
        self.assertTrue(profile["demo"])
        self.assertEqual(self.json_get("/api/profile")["candidate"]["headline"], "Not real")
        status, _, body = self.post("/api/cv/analyze", {"cv_text": "should not be accepted"})
        self.assertEqual(status, 410)
        self.assertIn(b"intentionally disabled", body)

    def test_settings_save_and_reset_are_local_demo_state(self):
        saved = self.json_post("/api/settings", {"location": "Example City", "country": "Exampleland", "web_result_pages": 3, "orchestrator_url": "https://attacker.invalid"})
        self.assertTrue(saved["demo"])
        self.assertEqual(saved["location"], "Example City")
        self.assertEqual(saved["orchestrator_url"], main.DEFAULT_SETTINGS["orchestrator_url"])
        reset = self.json_post("/api/settings/reset", {})
        self.assertEqual(reset["location"], "")

    def test_model_catalog_and_activation_never_claim_real_readiness(self):
        catalog = self.json_get("/api/models")
        self.assertTrue(catalog["demo"])
        self.assertEqual(catalog["files_scanned"], 0)
        self.assertTrue(catalog["hardware"]["demo"])
        selected = self.json_post("/api/models/select", {"model_id": "demo-gguf"})
        self.assertTrue(selected["demo"])
        activated = self.json_post("/api/models/activate", {})
        self.assertEqual(activated["status"], "demo")
        self.assertIn("No container", activated["message"])
        health = self.json_get("/api/models/runtime-health")
        self.assertEqual(health["status"], "demo")

    def test_service_checks_are_explicitly_mocked(self):
        for path in ("/api/searxng/test", "/api/orchestrator/test"):
            data = self.json_post(path, {})
            self.assertTrue(data["demo"])
            self.assertFalse(data["ok"])
            self.assertIn("no service was contacted", data["message"].lower())

    def test_cross_origin_posts_are_rejected(self):
        status, _, body = self.post("/api/settings", {"location": "bad"}, {"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        self.assertIn(b"Cross-origin", body)

    def test_unexpected_host_is_rejected(self):
        status, _, body = self.get("/api/health", {"Host": "attacker.example"})
        self.assertEqual(status, 403)
        self.assertIn(b"local demo", body)


class ArchitectureSafetyTests(unittest.TestCase):
    def test_production_scraper_registry_is_empty(self):
        self.assertEqual(get_production_adapters(), [])
        summary = registry_summary()
        self.assertTrue(summary["demo"])
        self.assertEqual(summary["active_adapters"], 0)
        self.assertTrue(all(not slot["implementation_included"] for slot in summary["registered_slots"]))

    def test_interface_contracts_raise_not_implemented(self):
        class EmptyScraper:
            adapter_id = "fixture"
        scraper = EmptyScraper()
        with self.assertRaises(NotImplementedError):
            ScraperAdapter.collect(scraper, CollectionRequest(query="demo"))

        class EmptyOrchestrator:
            def run(self, request):
                raise NotImplementedError
        with self.assertRaises(NotImplementedError):
            Orchestrator.run(EmptyOrchestrator(), OrchestrationRequest(query="demo"))

        class EmptySearch:
            def search(self, request):
                raise NotImplementedError
        with self.assertRaises(NotImplementedError):
            SearchProvider.search(EmptySearch(), SearchRequest(query="demo"))

        class EmptyRuntime:
            def activate(self, selection):
                raise NotImplementedError
        with self.assertRaises(NotImplementedError):
            ModelRuntime.activate(EmptyRuntime(), ModelSelection(model_id="demo", path="", format="GGUF"))

    def test_production_network_details_are_absent(self):
        forbidden_modules = ("requests", "httpx", "urllib.request", "subprocess", "socket")
        source = (PROJECT / "main.py").read_text(encoding="utf-8")
        for module in forbidden_modules:
            self.assertNotIn(f"import {module}", source)
            self.assertNotIn(f"from {module}", source)
        audited_dirs = ("templates", "static", "demo_fixtures", "demo_services", "scrapers", "search", "orchestrator", "model_runtime")
        source_files = [PROJECT / "main.py"]
        for folder in audited_dirs:
            source_files.extend(path for path in (PROJECT / folder).rglob("*") if path.is_file())
        all_source = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in source_files)
        external_domains = re.findall(r"https?://([^/\s\"'<>]+)", all_source)
        self.assertTrue(all(host.startswith("example.invalid") or host.startswith("127.0.0.1") or host.startswith("localhost") or host.startswith("{HOST}:{PORT}") for host in external_domains), external_domains)

    def test_no_personal_or_runtime_files_in_source_snapshot(self):
        forbidden_names = {"demo_state.json", ".env", "model-runtime.env", "jobs.csv", "profile.json", "app_settings.json", "model_manager.json"}
        found = [path.relative_to(PROJECT).as_posix() for path in PROJECT.rglob("*") if path.is_file() and path.name in forbidden_names]
        self.assertEqual(found, [])
        weights = [path for path in PROJECT.rglob("*") if path.is_file() and path.suffix.lower() in {".gguf", ".safetensors", ".pt", ".pth", ".onnx"}]
        self.assertEqual(weights, [])

    def test_demo_fixtures_use_reserved_invalid_urls(self):
        jobs = json.loads((PROJECT / "demo_fixtures" / "sample_jobs.json").read_text(encoding="utf-8"))
        self.assertTrue(jobs)
        self.assertTrue(all(job["url"].startswith("https://example.invalid/") for job in jobs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
