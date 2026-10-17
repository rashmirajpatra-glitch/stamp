from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppSettings:
    sarvam_api_key: str | None
    sarvam_base_url: str
    sarvam_language: str
    sarvam_timeout_seconds: int
    sarvam_poll_interval_seconds: float
    sarvam_max_wait_seconds: int
    sarvam_use_mock: bool
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_use_tls: bool
    notify_email: str | None
    output_dir: Path


DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"


DEFAULT_RULES: dict[str, Any] = {
    "expected_authorities": ["Government Authority"],
    "expected_signers": ["John Doe"],
    "expected_designations": ["Officer"],
    "required_elements": ["seal", "signature", "date", "signer_name", "designation"],
    "allowed_stamp_colors": ["red", "blue", "green"],
    "signature_lower_page_min_ratio": 0.55,
    "max_stamp_signature_distance_ratio": 0.45,
    "reject_on_fail_checks": [
        "seal_presence",
        "signature_presence",
        "dated_imprint",
        "signer_name_present",
        "designation_present",
    ],
    "fraud_review_checks": [
        "seal_text_readable",
        "authority_match",
        "stamp_placement",
        "ink_color_plausibility",
        "signature_placement",
    ],
    "fraud_review_warn_threshold": 2,
}


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> AppSettings:
    output_dir = Path(os.getenv("OUTPUT_DIR", "output")).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return AppSettings(
        sarvam_api_key=os.getenv("SARVAM_API_KEY"),
        sarvam_base_url=os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai"),
        sarvam_language=os.getenv("SARVAM_LANGUAGE", "en-IN"),
        sarvam_timeout_seconds=int(os.getenv("SARVAM_TIMEOUT_SECONDS", "45")),
        sarvam_poll_interval_seconds=float(os.getenv("SARVAM_POLL_INTERVAL_SECONDS", "2")),
        sarvam_max_wait_seconds=int(os.getenv("SARVAM_MAX_WAIT_SECONDS", "90")),
        sarvam_use_mock=_parse_bool(os.getenv("SARVAM_USE_MOCK"), default=False),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        smtp_use_tls=_parse_bool(os.getenv("SMTP_USE_TLS"), default=True),
        notify_email=os.getenv("NOTIFY_EMAIL"),
        output_dir=output_dir,
    )


def load_rules(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_RULES_PATH
    if not path.exists():
        return dict(DEFAULT_RULES)

    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    rules = dict(DEFAULT_RULES)
    rules.update(loaded)
    return rules
