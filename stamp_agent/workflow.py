from __future__ import annotations

from typing import Any

from stamp_agent.models import CheckStatus, ValidationCheck, Verdict


def compute_overall_confidence(checks: list[ValidationCheck]) -> float:
    if not checks:
        return 0.0
    return round(sum(check.score for check in checks) / len(checks), 4)


def determine_verdict(
    checks: list[ValidationCheck],
    rules: dict[str, Any],
) -> tuple[Verdict, list[str], float]:
    reject_on_fail = set(rules.get("reject_on_fail_checks", [
        "seal_presence",
        "signature_presence",
        "dated_imprint",
        "signer_name_present",
        "designation_present",
    ]))
    fraud_review_checks = set(rules.get("fraud_review_checks", [
        "seal_text_readable",
        "authority_match",
        "stamp_placement",
        "ink_color_plausibility",
    ]))
    warn_threshold = int(rules.get("fraud_review_warn_threshold", 2))

    failed = [c for c in checks if c.status == CheckStatus.FAIL]
    warned = [c for c in checks if c.status == CheckStatus.WARN]

    fail_ids = {c.check_id for c in failed}
    warn_ids = {c.check_id for c in warned}

    reasons: list[str] = []

    if fail_ids & reject_on_fail:
        verdict = Verdict.REJECTED
        reasons.extend([c.message for c in failed if c.check_id in reject_on_fail])
    elif (fail_ids & fraud_review_checks) or len(warned) >= warn_threshold or (warn_ids & fraud_review_checks):
        verdict = Verdict.FRAUD_REVIEW
        reasons.extend([c.message for c in failed + warned if c.check_id in fraud_review_checks])
        if len(warned) >= warn_threshold:
            reasons.append(f"Multiple warning checks triggered ({len(warned)} warnings).")
    else:
        verdict = Verdict.APPROVED
        reasons.append("All critical compliance and authenticity checks passed.")

    if not reasons:
        reasons = ["Workflow decision derived from validation checks."]

    confidence = compute_overall_confidence(checks)
    return verdict, reasons, confidence


def workflow_action_for_verdict(verdict: Verdict) -> str:
    mapping = {
        Verdict.APPROVED: "AUTO_APPROVE",
        Verdict.REJECTED: "AUTO_REJECT",
        Verdict.FRAUD_REVIEW: "QUEUE_FRAUD_REVIEW",
    }
    return mapping[verdict]
