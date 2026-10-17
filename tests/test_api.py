from __future__ import annotations

from fastapi.testclient import TestClient

from stamp_agent.api import app
from stamp_agent.demo import create_synthetic_demo_image


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_endpoint_with_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("SARVAM_USE_MOCK", "true")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))

    sample = create_synthetic_demo_image(tmp_path / "api_input.png")
    client = TestClient(app)

    with sample.open("rb") as handle:
        response = client.post("/analyze", files={"file": (sample.name, handle, "image/png")})

    assert response.status_code == 200
    payload = response.json()
    assert payload["input_file"]
    assert payload["verdict"] in {"APPROVED", "FRAUD_REVIEW", "REJECTED"}
    assert payload["report_path"]
    assert isinstance(payload["extraction_findings"], list)
    assert isinstance(payload["validation_checks"], list)
