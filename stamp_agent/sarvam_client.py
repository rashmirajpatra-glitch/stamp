from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

TERMINAL_STATES = {"completed", "partially_completed", "failed", "rejected"}


class SarvamError(Exception):
    """Base error for Sarvam integration."""


class SarvamAuthError(SarvamError):
    """Raised when Sarvam authentication fails."""


class SarvamTimeoutError(SarvamError):
    """Raised when job polling exceeds configured timeout."""


class SarvamJobFailedError(SarvamError):
    """Raised when Sarvam reports failed/rejected terminal state."""


@dataclass
class SarvamJobResult:
    job_id: str
    status: str
    result: dict[str, Any]


class SarvamDocAIClient(ABC):
    @abstractmethod
    def run_digitise_job(self, file_path: str | Path) -> SarvamJobResult:
        raise NotImplementedError


class SarvamHttpDocAIClient(SarvamDocAIClient):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.sarvam.ai",
        language: str = "en-IN",
        timeout_seconds: int = 45,
        poll_interval_seconds: float = 2.0,
        max_wait_seconds: int = 90,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "api-subscription-key": self.api_key,
            "Accept": "application/json",
        }

    def _handle_common_errors(self, response: requests.Response) -> None:
        if response.status_code in {401, 403}:
            body = response.text.lower()
            if "invalid_api_key_error" in body or "api key" in body:
                raise SarvamAuthError("Sarvam authentication failed: invalid or missing API key.")
            raise SarvamAuthError(f"Sarvam authentication failed with status {response.status_code}.")

    def submit_digitise_job(self, file_path: str | Path) -> str:
        target = Path(file_path)
        if not target.exists():
            raise FileNotFoundError(f"Input file does not exist: {target}")

        url = f"{self.base_url}/doc-ai/v1/job/digitise"
        data = {"language": self.language}
        with target.open("rb") as handle:
            files = {"file": (target.name, handle, "application/octet-stream")}
            response = requests.post(
                url,
                headers=self._headers(),
                data=data,
                files=files,
                timeout=self.timeout_seconds,
            )

        self._handle_common_errors(response)
        if response.status_code >= 400:
            raise SarvamError(f"Failed to submit digitise job ({response.status_code}): {response.text}")

        payload = response.json()
        job_id = payload.get("job_id") or payload.get("id")
        if not job_id:
            raise SarvamError(f"Sarvam submit response missing job_id: {json.dumps(payload)}")
        return job_id

    def get_job_status(self, job_id: str) -> str:
        url = f"{self.base_url}/doc-ai/v1/job/{job_id}/status"
        response = requests.get(url, headers=self._headers(), timeout=self.timeout_seconds)
        self._handle_common_errors(response)
        if response.status_code >= 400:
            raise SarvamError(
                f"Failed to fetch status for job {job_id} ({response.status_code}): {response.text}"
            )

        payload = response.json()
        status = str(payload.get("status", "")).lower().strip()
        if not status:
            raise SarvamError(f"Sarvam status response missing status for job {job_id}: {payload}")
        return status

    def fetch_results(self, job_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/doc-ai/v1/job/{job_id}/results"
        response = requests.get(url, headers=self._headers(), timeout=self.timeout_seconds)
        self._handle_common_errors(response)

        if response.status_code == 409:
            raise SarvamError(
                f"Sarvam job {job_id} results requested too early (409 conflict). Poll status until terminal first."
            )
        if response.status_code >= 400:
            raise SarvamError(
                f"Failed to fetch results for job {job_id} ({response.status_code}): {response.text}"
            )
        return response.json()

    def poll_until_terminal(self, job_id: str) -> str:
        start = time.monotonic()
        interval = self.poll_interval_seconds
        while True:
            status = self.get_job_status(job_id)
            if status in TERMINAL_STATES:
                return status

            elapsed = time.monotonic() - start
            if elapsed > self.max_wait_seconds:
                raise SarvamTimeoutError(
                    f"Timed out waiting for Sarvam job {job_id} to complete after {self.max_wait_seconds}s."
                )

            logger.debug("Sarvam job %s status=%s; sleeping %.2fs", job_id, status, interval)
            time.sleep(interval)
            interval = min(interval * 1.5, 10.0)

    def run_digitise_job(self, file_path: str | Path) -> SarvamJobResult:
        job_id = self.submit_digitise_job(file_path)
        status = self.poll_until_terminal(job_id)
        if status in {"failed", "rejected"}:
            raise SarvamJobFailedError(f"Sarvam job {job_id} ended with terminal status: {status}")

        result = self.fetch_results(job_id)
        return SarvamJobResult(job_id=job_id, status=status, result=result)


class MockSarvamDocAIClient(SarvamDocAIClient):
    def __init__(self, fixed_text: list[str] | None = None) -> None:
        self.fixed_text = fixed_text or [
            "Government Authority",
            "Approved",
            "Date: 2026-10-17",
            "Signer: John Doe",
            "Designation: Officer",
        ]

    def run_digitise_job(self, file_path: str | Path) -> SarvamJobResult:
        path = Path(file_path)
        fake = {
            "document": {
                "file_name": path.name,
                "pages": [
                    {
                        "page_number": 1,
                        "text": "\n".join(self.fixed_text),
                        "lines": [{"text": line} for line in self.fixed_text],
                    }
                ],
            }
        }
        return SarvamJobResult(job_id="mock-job-001", status="completed", result=fake)
