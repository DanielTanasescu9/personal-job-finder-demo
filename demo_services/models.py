"""Fictional model cards for the public demo UI; no local files are scanned."""
MODEL_SAMPLES = [
    {
        "id": "demo-gguf", "name": "Fictional GGUF model (demo only)",
        "parameter_billions": 1.7, "parameter_source": "fabricated demo metadata",
        "size_bytes": 1100000000, "runtime": "GGUF adapter (simulated)",
        "format": "GGUF (simulated)", "architecture": "DemoArchitecture",
        "quantization": "Demo quantization", "model_path": "No local path — demo only",
        "supported": True, "selectable": True,
        "reasons": ["Fixture only; not an installed model.", "No filesystem scan or model loading occurs."],
        "selected": False,
    },
    {
        "id": "demo-safetensors", "name": "Fictional Safetensors model (demo only)",
        "parameter_billions": 3.0, "parameter_source": "fabricated demo metadata",
        "size_bytes": 2400000000, "runtime": "Transformers adapter (simulated)",
        "format": "Safetensors (simulated)", "architecture": "DemoTextArchitecture",
        "quantization": "Demo metadata", "model_path": "No local path — demo only",
        "supported": True, "selectable": True,
        "reasons": ["Fixture only; not an installed model.", "No filesystem scan or model loading occurs."],
        "selected": False,
    },
]


def demo_catalog(selected_model_id: str | None = None) -> dict:
    """Build model cards without inspecting the host or starting a runtime."""
    from copy import deepcopy
    models = deepcopy(MODEL_SAMPLES)
    for model in models:
        model["selected"] = model["id"] == selected_model_id
    selected = next((model for model in models if model["selected"]), None)
    return {
        "models": models, "count": len(models), "files_scanned": 0,
        "model_roots": ["Demo only — local folders are not scanned"],
        "errors": [], "selected_model": selected,
        "hardware": {
            "demo": True, "platform": "Demo response (not detected)",
            "cpu_count_logical": None, "ram_total_gb": None,
            "ram_available_gb": None, "gpus": [],
            "policy": "Hardware detection is simulated in this public demo.",
            "gpu_detection_note": "No system diagnostics or GPU commands are executed.",
        },
        "activation": {"status": "demo", "message": "No model is activated in public demo mode."},
        "demo": True,
    }
