from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class CoverageWindow:
    start: datetime
    end: datetime
    hours: int
    label: str


def coverage_window(now: datetime | None = None, timezone_name: str = "America/New_York", override_hours: int | None = None) -> CoverageWindow:
    """Monday covers 72 hours; every other weekday covers the prior 24 hours."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    local_now = now.astimezone(ZoneInfo(timezone_name))
    hours = override_hours if override_hours is not None else (72 if local_now.weekday() == 0 else 24)
    if not 1 <= hours <= 24 * 90:
        raise ValueError("lookback must be between 1 and 2160 hours")
    label = "weekend roundup" if hours == 72 and local_now.weekday() == 0 else f"last {hours} hours"
    return CoverageWindow(start=now - timedelta(hours=hours), end=now, hours=hours, label=label)
