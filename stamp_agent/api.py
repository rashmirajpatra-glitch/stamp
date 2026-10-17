from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from stamp_agent.config import load_rules, load_settings
from stamp_agent.pipeline import StampIntelligencePipeline, build_sarvam_client

app = FastAPI(title="Sarvam AI Stamp Intelligence Agent", version="0.1.0")

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _build_pipeline() -> StampIntelligencePipeline:
    settings = load_settings()
    rules = load_rules(None)
    client = build_sarvam_client(settings)
    return StampIntelligencePipeline(settings=settings, rules=rules, sarvam_client=client)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only JPG and PNG files are supported.")

    settings = load_settings()
    upload_dir = settings.output_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=upload_dir) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        pipeline = _build_pipeline()
        result = pipeline.analyze(tmp_path)
        payload = result.report.to_dict()
        payload["report_path"] = str(result.report_path)
        payload["email_sent"] = result.email_sent
        return payload
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
