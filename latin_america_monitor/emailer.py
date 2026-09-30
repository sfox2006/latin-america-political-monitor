from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from .briefing import build_html
from .config import Settings
from .models import Headline
from .window import CoverageWindow


def send_report(headlines: list[Headline], window: CoverageWindow, report_path: Path, settings: Settings) -> bool:
    if not (settings.smtp_user and settings.smtp_password and settings.email_to):
        return False
    message = EmailMessage()
    message["Subject"] = f"Latin America Political Monitor — {window.end:%d %B %Y}"
    message["From"] = settings.email_from or settings.smtp_user
    message["To"] = ", ".join(settings.email_to)
    message.set_content(report_path.read_text(encoding="utf-8"))
    message.add_alternative(build_html(headlines), subtype="html")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=45) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)
    return True
