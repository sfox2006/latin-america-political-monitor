from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

from .briefing import publisher_summary, write_outputs
from .collector import collect
from .config import Settings
from .emailer import send_report
from .window import coverage_window


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Collect Latin American political headlines from major newspapers.")
    result.add_argument("--lookback-hours", type=int, help="Override the automatic Monday=72h, other days=24h window")
    result.add_argument("--no-email", action="store_true", help="Generate files without sending email")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()
    now = datetime.now(timezone.utc)
    window = coverage_window(now, settings.timezone, args.lookback_hours)
    logging.info("Collecting %s: %s to %s", window.label, window.start, window.end)
    headlines = collect(window, settings)
    paths = write_outputs(headlines, window, settings.output_dir)
    logging.info("Wrote %d headlines to %s, %s and %s", len(headlines), *paths)
    if headlines:
        logging.info("Largest publisher counts: %s", publisher_summary(headlines))
    if not args.no_email:
        sent = send_report(headlines, window, paths[0], paths[1], settings)
        logging.info("Email %s", "sent" if sent else "skipped (SMTP settings not configured)")
    return 0

