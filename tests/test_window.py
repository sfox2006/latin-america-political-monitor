from datetime import datetime, timedelta, timezone

from latin_america_monitor.cli import scheduled_end, scheduled_window
from latin_america_monitor.window import coverage_window


MONDAY = datetime(2026, 9, 28, 11, tzinfo=timezone.utc)
TUESDAY = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
FRIDAY = datetime(2026, 9, 25, 11, tzinfo=timezone.utc)


def test_monday_covers_the_weekend():
    window = coverage_window(MONDAY, "America/New_York")
    assert MONDAY.weekday() == 0
    assert window.hours == 72
    assert window.start == MONDAY - timedelta(hours=72)
    assert window.end == MONDAY
    assert window.label == "weekend roundup"


def test_tuesday_covers_the_previous_24_hours():
    window = coverage_window(TUESDAY, "America/New_York")
    assert TUESDAY.weekday() == 1
    assert window.hours == 24
    assert window.start == TUESDAY - timedelta(hours=24)
    assert window.end == TUESDAY
    assert window.label == "last 24 hours"


def test_friday_window_meets_monday_weekend():
    friday = coverage_window(FRIDAY, "UTC")
    monday = coverage_window(MONDAY, "UTC")
    assert FRIDAY.weekday() == 4
    assert friday.hours == 24
    assert monday.hours == 72
    assert friday.end == monday.start == FRIDAY


def test_wednesday_and_friday_use_24_hours():
    wednesday = coverage_window(MONDAY + timedelta(days=2), "UTC")
    friday = coverage_window(FRIDAY, "America/Sao_Paulo")
    assert wednesday.hours == 24
    assert friday.hours == 24


def test_override_wins():
    window = coverage_window(MONDAY, override_hours=48)
    assert window.hours == 48
    assert window.start == MONDAY - timedelta(hours=48)


def test_delayed_monday_run_after_midnight_still_covers_the_weekend(tmp_path):
    late_now = TUESDAY.replace(hour=2)
    assert scheduled_end(late_now) == MONDAY
    late = scheduled_window(late_now, tmp_path / "missing")
    assert late.hours == 72
    assert late.label == "weekend roundup"
    assert late.end == MONDAY
    assert late.start == MONDAY - timedelta(hours=72)


def test_slightly_early_start_keeps_todays_boundary(tmp_path):
    early = MONDAY - timedelta(minutes=5)
    window = scheduled_window(early, tmp_path / "missing")
    assert window.end == MONDAY
    assert window.hours == 72

