from __future__ import annotations

import json
from pathlib import Path

from stamp_agent.config import load_rules, load_settings
from stamp_agent.demo import create_synthetic_demo_image
from stamp_agent.pipeline import StampIntelligencePipeline, build_sarvam_client


def test_full_pipeline_mock_generates_report_and_findings(tmp_path, monkeypatch):
    monkeypatch.setenv("SARVAM_USE_MOCK", "true")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))

    input_image = create_synthetic_demo_image(tmp_path / "input.png")
    settings = load_settings()
    rules = load_rules(Path(__file__).resolve().parent.parent / "config" / "config.yaml")

    pipeline = StampIntelligencePipeline(settings=settings, rules=rules, sarvam_client=build_sarvam_client(settings))
    result = pipeline.analyze(input_image)

    assert result.report_path.exists()
    assert result.report.verdict.value in {"APPROVED", "FRAUD_REVIEW", "REJECTED"}

    finding_types = [f.finding_type for f in result.report.extraction_findings]
    assert "stamp_or_seal" in finding_types
    assert "signature" in finding_types

    data = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert data["input_file"] == input_image.name
    assert data["verdict"] == result.report.verdict.value
    assert "extraction_findings" in data
    assert "validation_checks" in data
    assert "reasons" in data
    assert "overall_confidence" in data
