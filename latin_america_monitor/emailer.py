from __future__ import annotations

import smtplib
from email.message import EmailMessage
from html import escape
from pathlib import Path

from .config import Settings
from .models import Headline
from .window import CoverageWindow


def _html_body(headlines: list[Headline], window: CoverageWindow) -> str:
    rows = "".join(
        f'<tr><td>{item.published:%Y-%m-%d %H:%M}</td><td>{escape(item.publisher)}</td>'
        f'<td><a href="{escape(item.url, quote=True)}">{escape(item.title)}</a></td></tr>'
        for item in headlines
    )
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;color:#17233c">
<h1 style="font-size:22px">Latin America Political Monitor</h1>
<p><strong>Coverage:</strong> {window.start:%Y-%m-%d %H:%M UTC} to {window.end:%Y-%m-%d %H:%M UTC} ({window.label})</p>
<p><strong>{len(headlines)} headlines</strong>. The attached CSV contains the complete machine-readable list.</p>
<table cellpadding="7" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px">
<thead><tr style="background:#17233c;color:white"><th>Published (UTC)</th><th>Publisher</th><th>Headline</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>"""


def send_report(headlines: list[Headline], window: CoverageWindow, markdown_path: Path, csv_path: Path, settings: Settings) -> bool:
    if not (settings.smtp_user and settings.smtp_password and settings.email_to):
        return False
    message = EmailMessage()
    message["Subject"] = f"Latin America Political Monitor — {window.end:%d %B %Y}"
    message["From"] = settings.email_from or settings.smtp_user
    message["To"] = ", ".join(settings.email_to)
    message.set_content(markdown_path.read_text(encoding="utf-8"))
    message.add_alternative(_html_body(headlines, window), subtype="html")
    message.add_attachment(csv_path.read_bytes(), maintype="text", subtype="csv", filename=csv_path.name)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=45) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)
    return True

