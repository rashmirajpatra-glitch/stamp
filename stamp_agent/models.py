from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FRAUD_REVIEW = "FRAUD_REVIEW"


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


@dataclass
class ExtractionFinding:
    finding_type: str
    bbox: BoundingBox
    area: float
    confidence: float
    color: str | None = None
    text: str | None = None
    page: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["bbox"] = asdict(self.bbox)
        return payload


@dataclass
class ValidationCheck:
    check_id: str
    category: str
    status: CheckStatus
    score: float
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass
class AnalysisReport:
    input_file: str
    timestamp: str
    extraction_findings: list[ExtractionFinding]
    validation_checks: list[ValidationCheck]
    verdict: Verdict
    reasons: list[str]
    overall_confidence: float
    sarvam_status: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        input_file: str,
        extraction_findings: list[ExtractionFinding],
        validation_checks: list[ValidationCheck],
        verdict: Verdict,
        reasons: list[str],
        overall_confidence: float,
        sarvam_status: str,
        metadata: dict[str, Any] | None = None,
    ) -> "AnalysisReport":
        return cls(
            input_file=input_file,
            timestamp=datetime.now(timezone.utc).isoformat(),
            extraction_findings=extraction_findings,
            validation_checks=validation_checks,
            verdict=verdict,
            reasons=reasons,
            overall_confidence=overall_confidence,
            sarvam_status=sarvam_status,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_file": self.input_file,
            "timestamp": self.timestamp,
            "extraction_findings": [finding.to_dict() for finding in self.extraction_findings],
            "validation_checks": [check.to_dict() for check in self.validation_checks],
            "verdict": self.verdict.value,
            "reasons": self.reasons,
            "overall_confidence": round(self.overall_confidence, 4),
            "sarvam_status": self.sarvam_status,
            "metadata": self.metadata,
        }
