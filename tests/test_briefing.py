from datetime import datetime, timedelta, timezone

from latin_america_monitor.briefing import build_markdown
from latin_america_monitor.models import Headline
from latin_america_monitor.window import CoverageWindow


def test_briefing_contains_headline_publisher_and_original_link():
    end = datetime(2026, 9, 28, 11, tzinfo=timezone.utc)
    window = CoverageWindow(end - timedelta(hours=72), end, 72, "weekend roundup")
    item = Headline(
        title="Congress approves electoral reform",
        publisher="Example Daily",
        url="https://example.com/original-story",
        seen_at=end - timedelta(hours=1),
        market="Mexico",
        scope="latin_america",
        domain="example.com",
    )
    report = build_markdown([item], window, end)
    assert "Congress approves electoral reform" in report
    assert "Example Daily" in report
    assert "https://example.com/original-story" in report
    assert "weekend roundup" in report
