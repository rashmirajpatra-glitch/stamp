from __future__ import annotations

import math
import re
from typing import Any

from stamp_agent.models import CheckStatus, ExtractionFinding, ValidationCheck

DATE_REGEX = re.compile(r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")


def _normalize(text: str) -> str:
    return text.strip().lower()


def _extract_ocr_lines(sarvam_result: dict[str, Any] | None) -> list[str]:
    if not sarvam_result:
        return []

    lines: list[str] = []
    pages = sarvam_result.get("document", {}).get("pages", [])
    for page in pages:
        for line in page.get("lines", []):
            if isinstance(line, dict) and line.get("text"):
                lines.append(str(line["text"]))
        page_text = page.get("text")
        if page_text and not lines:
            lines.extend(str(page_text).splitlines())
    return [line.strip() for line in lines if line and line.strip()]


def _check(status: CheckStatus, check_id: str, category: str, score: float, message: str, evidence: dict[str, Any]) -> ValidationCheck:
    return ValidationCheck(
        check_id=check_id,
        category=category,
        status=status,
        score=max(0.0, min(1.0, float(score))),
        message=message,
        evidence=evidence,
    )


def _contains_any(haystack: str, needles: list[str]) -> bool:
    h = _normalize(haystack)
    return any(_normalize(n) in h for n in needles if n)


def _center(finding: ExtractionFinding) -> tuple[float, float]:
    return (
        finding.bbox.x + finding.bbox.width / 2.0,
        finding.bbox.y + finding.bbox.height / 2.0,
    )


def run_validation(
    findings: list[ExtractionFinding],
    sarvam_result: dict[str, Any] | None,
    rules: dict[str, Any],
) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []

    ocr_lines = _extract_ocr_lines(sarvam_result)
    ocr_blob = "\n".join(ocr_lines)

    expected_authorities = rules.get("expected_authorities", [])
    expected_signers = rules.get("expected_signers", [])
    expected_designations = rules.get("expected_designations", [])

    required = rules.get("required_elements", ["seal", "signature", "date", "signer_name", "designation"])
    allowed_stamp_colors = rules.get("allowed_stamp_colors", ["red", "blue", "green"])
    signature_lower_ratio = float(rules.get("signature_lower_page_min_ratio", 0.55))
    max_stamp_signature_distance_ratio = float(rules.get("max_stamp_signature_distance_ratio", 0.45))

    seals = [f for f in findings if f.finding_type == "stamp_or_seal"]
    signatures = [f for f in findings if f.finding_type == "signature"]

    seal_present = bool(seals)
    signature_present = bool(signatures)
    checks.append(
        _check(
            CheckStatus.PASS if seal_present else CheckStatus.FAIL,
            "seal_presence",
            "compliance",
            0.95 if seal_present else 0.0,
            "Seal/stamp detected." if seal_present else "Required seal/stamp is missing.",
            {"count": len(seals)},
        )
    )
    checks.append(
        _check(
            CheckStatus.PASS if signature_present else CheckStatus.FAIL,
            "signature_presence",
            "compliance",
            0.95 if signature_present else 0.0,
            "Signature detected." if signature_present else "Required signature is missing.",
            {"count": len(signatures)},
        )
    )

    seal_text_available = any((s.text or "").strip() for s in seals)
    checks.append(
        _check(
            CheckStatus.PASS if seal_text_available else CheckStatus.WARN,
            "seal_text_readable",
            "authenticity",
            0.85 if seal_text_available else 0.35,
            "Seal text is readable from OCR." if seal_text_available else "Seal text is not clearly readable from OCR.",
            {"ocr_line_count": len(ocr_lines)},
        )
    )

    authority_match = _contains_any(ocr_blob, expected_authorities) if expected_authorities else True
    checks.append(
        _check(
            CheckStatus.PASS if authority_match else CheckStatus.WARN,
            "authority_match",
            "authenticity",
            0.9 if authority_match else 0.4,
            "Authority text aligns with configured authorities."
            if authority_match
            else "Authority text does not match expected authority values.",
            {"expected_authorities": expected_authorities},
        )
    )

    date_found = bool(DATE_REGEX.search(ocr_blob))
    checks.append(
        _check(
            CheckStatus.PASS if date_found else CheckStatus.FAIL if "date" in required else CheckStatus.WARN,
            "dated_imprint",
            "authenticity",
            0.88 if date_found else 0.2,
            "Date imprint present." if date_found else "Date imprint not detected.",
            {},
        )
    )

    signer_present = _contains_any(ocr_blob, expected_signers) if expected_signers else ("signer" in _normalize(ocr_blob))
    checks.append(
        _check(
            CheckStatus.PASS if signer_present else CheckStatus.FAIL if "signer_name" in required else CheckStatus.WARN,
            "signer_name_present",
            "compliance",
            0.9 if signer_present else 0.25,
            "Signer name present in OCR content." if signer_present else "Signer name missing in OCR content.",
            {"expected_signers": expected_signers},
        )
    )

    designation_present = _contains_any(ocr_blob, expected_designations) if expected_designations else ("designation" in _normalize(ocr_blob))
    checks.append(
        _check(
            CheckStatus.PASS if designation_present else CheckStatus.FAIL if "designation" in required else CheckStatus.WARN,
            "designation_present",
            "compliance",
            0.88 if designation_present else 0.25,
            "Designation present in OCR content." if designation_present else "Designation missing in OCR content.",
            {"expected_designations": expected_designations},
        )
    )

    # Signature placement: expected lower portion of page.
    if signatures:
        lower_hits = [s for s in signatures if float(s.metadata.get("center_y_ratio", 0.0)) >= signature_lower_ratio]
        signature_placement_ok = bool(lower_hits)
        status = CheckStatus.PASS if signature_placement_ok else CheckStatus.WARN
        score = 0.9 if signature_placement_ok else 0.45
        message = (
            "Signature placement is in the lower signing region."
            if signature_placement_ok
            else "Signature found but outside the expected lower signing region."
        )
    else:
        status = CheckStatus.FAIL
        score = 0.0
        message = "Signature placement cannot be validated because no signature was detected."
        lower_hits = []

    checks.append(
        _check(
            status,
            "signature_placement",
            "placement",
            score,
            message,
            {"threshold": signature_lower_ratio, "matching_signatures": len(lower_hits)},
        )
    )

    # Stamp placement: expected near signature.
    stamp_near_signature = False
    min_ratio: float | None = None
    if seals and signatures:
        for seal in seals:
            sx, sy = _center(seal)
            page_w = float(seal.metadata.get("page_width", 1.0))
            page_h = float(seal.metadata.get("page_height", 1.0))
            diag = math.sqrt(page_w * page_w + page_h * page_h)
            for sig in signatures:
                if sig.page != seal.page:
                    continue
                tx, ty = _center(sig)
                distance = math.dist((sx, sy), (tx, ty))
                ratio = distance / float(diag or 1.0)
                if min_ratio is None or ratio < min_ratio:
                    min_ratio = ratio
                if ratio <= max_stamp_signature_distance_ratio:
                    stamp_near_signature = True
                    break
            if stamp_near_signature:
                break

    stamp_status = CheckStatus.PASS if stamp_near_signature else (CheckStatus.WARN if seals and signatures else CheckStatus.FAIL)
    checks.append(
        _check(
            stamp_status,
            "stamp_placement",
            "placement",
            0.9 if stamp_near_signature else (0.45 if seals and signatures else 0.0),
            "Stamp is located near signature/designated area."
            if stamp_near_signature
            else "Stamp is not near the signature/designated area.",
            {
                "max_distance_ratio": max_stamp_signature_distance_ratio,
                "observed_min_distance_ratio": None if min_ratio is None else round(min_ratio, 4),
            },
        )
    )

    # Ink color plausibility for seals.
    invalid_color_count = len([seal for seal in seals if (seal.color or "").lower() not in {c.lower() for c in allowed_stamp_colors}])
    color_ok = invalid_color_count == 0 and bool(seals)
    color_status = CheckStatus.PASS if color_ok else (CheckStatus.WARN if seals else CheckStatus.FAIL)
    checks.append(
        _check(
            color_status,
            "ink_color_plausibility",
            "authenticity",
            0.86 if color_ok else (0.45 if seals else 0.0),
            "Seal ink color is plausible." if color_ok else "Seal ink color is unusual or no seal detected.",
            {"allowed_stamp_colors": allowed_stamp_colors, "invalid_color_count": invalid_color_count},
        )
    )

    return checks
