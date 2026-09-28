from datetime import datetime, timezone

from latin_america_monitor.window import coverage_window


def test_monday_uses_72_hours():
    window = coverage_window(datetime(2026, 9, 28, 11, tzinfo=timezone.utc), "America/New_York")
    assert window.hours == 72
    assert window.label == "weekend roundup"


def test_tuesday_uses_24_hours():
    window = coverage_window(datetime(2026, 9, 29, 11, tzinfo=timezone.utc), "America/New_York")
    assert window.hours == 24


def test_override_wins():
    window = coverage_window(datetime(2026, 9, 28, 11, tzinfo=timezone.utc), override_hours=48)
    assert window.hours == 48

