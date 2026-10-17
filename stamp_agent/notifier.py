from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from stamp_agent.config import AppSettings
from stamp_agent.models import AnalysisReport
from stamp_agent.workflow import workflow_action_for_verdict

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def _is_configured(self) -> bool:
        return bool(
            self.settings.smtp_host
            and self.settings.smtp_port
            and self.settings.notify_email
            and self.settings.smtp_user
            and self.settings.smtp_password
        )

    def send(self, report: AnalysisReport, report_path: str | None = None) -> bool:
        if not self._is_configured():
            logger.info("SMTP not configured completely; skipping email notification.")
            return False

        message = EmailMessage()
        message["From"] = self.settings.smtp_user
        message["To"] = self.settings.notify_email
        message["Subject"] = f"Stamp Intelligence Verdict: {report.verdict.value}"

        action = workflow_action_for_verdict(report.verdict)
        body_lines = [
            "Sarvam AI Stamp Intelligence Agent Result",
            "",
            f"Input file: {report.input_file}",
            f"Verdict: {report.verdict.value}",
            f"Workflow action: {action}",
            f"Overall confidence: {report.overall_confidence:.4f}",
            f"Reasons: {'; '.join(report.reasons)}",
        ]
        if report_path:
            body_lines.append(f"JSON report: {report_path}")

        message.set_content("\n".join(body_lines))

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
                if self.settings.smtp_use_tls:
                    smtp.starttls()
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
                smtp.send_message(message)
            logger.info("Notification email sent to %s", self.settings.notify_email)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Email notification failed (continuing pipeline): %s", exc)
            return False
