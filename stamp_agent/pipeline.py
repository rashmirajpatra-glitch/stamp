from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stamp_agent.config import AppSettings
from stamp_agent.extractor import extract_stamps_seals_signatures
from stamp_agent.models import AnalysisReport
from stamp_agent.notifier import EmailNotifier
from stamp_agent.report_writer import write_json_report
from stamp_agent.sarvam_client import (
    MockSarvamDocAIClient,
    SarvamAuthError,
    SarvamDocAIClient,
    SarvamError,
    SarvamHttpDocAIClient,
)
from stamp_agent.validator import run_validation
from stamp_agent.workflow import determine_verdict, workflow_action_for_verdict

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    report: AnalysisReport
    report_path: Path
    email_sent: bool


class StampIntelligencePipeline:
    def __init__(
        self,
        settings: AppSettings,
        rules: dict[str, Any],
        sarvam_client: SarvamDocAIClient,
        notifier: EmailNotifier | None = None,
    ) -> None:
        self.settings = settings
        self.rules = rules
        self.sarvam_client = sarvam_client
        self.notifier = notifier or EmailNotifier(settings)

    def analyze(self, input_file: str | Path, output_dir: str | Path | None = None) -> PipelineResult:
        input_path = Path(input_file).expanduser().resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")

        sarvam_payload: dict[str, Any] | None = None
        sarvam_status = "not_run"
        sarvam_metadata: dict[str, Any] = {}

        try:
            job_result = self.sarvam_client.run_digitise_job(input_path)
            sarvam_payload = job_result.result
            sarvam_status = job_result.status
            sarvam_metadata = {"job_id": job_result.job_id}
        except SarvamAuthError as exc:
            sarvam_status = "auth_error"
            sarvam_metadata = {"warning": str(exc)}
            logger.warning("Sarvam auth error; proceeding with CV-only extraction: %s", exc)
        except SarvamError as exc:
            sarvam_status = "error"
            sarvam_metadata = {"warning": str(exc)}
            logger.warning("Sarvam processing error; proceeding with CV-only extraction: %s", exc)

        findings = extract_stamps_seals_signatures(input_path, sarvam_payload)
        checks = run_validation(findings, sarvam_payload, self.rules)
        verdict, reasons, overall_confidence = determine_verdict(checks, self.rules)

        metadata = {
            "sarvam": {
                "status": sarvam_status,
                **sarvam_metadata,
            },
            "workflow_action": workflow_action_for_verdict(verdict),
        }

        report = AnalysisReport.create(
            input_file=input_path.name,
            extraction_findings=findings,
            validation_checks=checks,
            verdict=verdict,
            reasons=reasons,
            overall_confidence=overall_confidence,
            sarvam_status=sarvam_status,
            metadata=metadata,
        )

        target_output = Path(output_dir).expanduser().resolve() if output_dir else self.settings.output_dir
        report_path = write_json_report(report, target_output)

        email_sent = self.notifier.send(report, str(report_path))
        return PipelineResult(report=report, report_path=report_path, email_sent=email_sent)


def build_sarvam_client(settings: AppSettings) -> SarvamDocAIClient:
    if settings.sarvam_use_mock:
        return MockSarvamDocAIClient()
    if settings.sarvam_api_key:
        return SarvamHttpDocAIClient(
            api_key=settings.sarvam_api_key,
            base_url=settings.sarvam_base_url,
            language=settings.sarvam_language,
            timeout_seconds=settings.sarvam_timeout_seconds,
            poll_interval_seconds=settings.sarvam_poll_interval_seconds,
            max_wait_seconds=settings.sarvam_max_wait_seconds,
        )

    logger.warning("SARVAM_API_KEY not provided; using mock client.")
    return MockSarvamDocAIClient()
