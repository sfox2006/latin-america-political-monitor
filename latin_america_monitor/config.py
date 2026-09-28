from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    timezone: str = os.getenv("MONITOR_TIMEZONE", "America/New_York")
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "45"))
    request_delay: float = max(5.1, float(os.getenv("REQUEST_DELAY_SECONDS", "5.25")))
    max_records: int = min(250, int(os.getenv("MAX_RECORDS_PER_QUERY", "250")))
    source_batch_size: int = int(os.getenv("SOURCE_BATCH_SIZE", "8"))
    enrich_headlines: bool = _bool("ENRICH_HEADLINES", False)
    enrich_workers: int = int(os.getenv("ENRICH_WORKERS", "12"))
    user_agent: str = os.getenv("USER_AGENT", "LatinAmericaPoliticalMonitor/1.0")
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "output"))
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_to: tuple[str, ...] = tuple(x.strip() for x in os.getenv("EMAIL_TO", "").split(",") if x.strip())
