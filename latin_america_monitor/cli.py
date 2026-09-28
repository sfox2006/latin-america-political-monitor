from __future__ import annotations

import argparse
import logging
import json
from datetime import datetime, timezone
from pathlib import Path

from .briefing import publisher_summary, write_outputs
from .collector import collect, CollectionError
from .config import Settings
from .emailer import send_report
from .window import coverage_window, CoverageWindow


def scheduled_window(now: datetime, state_path: Path) -> CoverageWindow:
    # The schedule is fixed in UTC. Queue delays must not move the boundaries.
    end = now.astimezone(timezone.utc).replace(hour=11, minute=0, second=0, microsecond=0)
    if end > now:
        raise ValueError("Scheduled run started before its 11:00 UTC boundary")
    window = coverage_window(end, "UTC")
    if state_path.exists():
        previous = datetime.fromisoformat(state_path.read_text(encoding="utf-8").strip())
        if previous.tzinfo is None or previous > end:
            raise ValueError("Invalid previous successful coverage boundary")
        if previous < window.start:
            if (end - previous).days >= 90:
                raise ValueError("Recovery exceeds news-index history; manual recovery required")
            window = CoverageWindow(previous, end, window.hours, window.label + " plus missed-run recovery")
    return window


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Collect Latin American political headlines from major newspapers.")
    result.add_argument("--lookback-hours", type=int, help="Override the automatic Monday=72h, other days=24h window")
    result.add_argument("--no-email", action="store_true", help="Generate files without sending email")
    result.add_argument("--scheduled", action="store_true", help="Anchor to 11:00 UTC and recover missed runs")
    result.add_argument("--state-file", type=Path, default=Path("state/last_success.txt"))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()
    now = datetime.now(timezone.utc)
    if args.scheduled and args.lookback_hours is not None:
        raise ValueError("Scheduled runs cannot override lookback")
    window = scheduled_window(now, args.state_file) if args.scheduled else coverage_window(now, settings.timezone, args.lookback_hours)
    logging.info("Collecting %s: %s to %s", window.label, window.start, window.end)
    try:
        headlines = collect(window, settings)
    except CollectionError as exc:
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        (settings.output_dir / "failure.json").write_text(json.dumps({"status": "failed", "error": str(exc), "start": window.start.isoformat(), "end": window.end.isoformat()}), encoding="utf-8")
        logging.error("No briefing sent: %s", exc)
        return 1
    paths = write_outputs(headlines, window, settings.output_dir)
    logging.info("Wrote %d headlines to %s, %s and %s", len(headlines), *paths)
    if headlines:
        logging.info("Largest publisher counts: %s", publisher_summary(headlines))
    if not args.no_email:
        sent = send_report(headlines, window, paths[0], paths[1], settings)
        logging.info("Email %s", "sent" if sent else "skipped (SMTP settings not configured)")
    if args.scheduled:
        args.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.state_file.with_suffix(".tmp")
        temporary.write_text(window.end.isoformat(), encoding="utf-8")
        temporary.replace(args.state_file)
    return 0
