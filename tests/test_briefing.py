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
    assert "First indexed (UTC)" in report


def test_briefing_lists_every_item_including_cross_publisher_duplicates():
    end = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
    window = CoverageWindow(end - timedelta(hours=24), end, 24, "last 24 hours")
    shared = "Senate confirms the ambassador"
    items = [
        Headline(shared, "Clarín", "https://clarin.com/a?id=1", end - timedelta(hours=2), "Argentina", "latin_america", "clarin.com"),
        Headline(shared, "Reuters", "https://reuters.com/b?id=9", end - timedelta(hours=2), "International", "international", "reuters.com"),
        Headline("Reform [live]", "El País", "https://elpais.com/c_(draft)", end - timedelta(hours=3), "Spain", "international", "elpais.com"),
    ]
    report = build_markdown(items, window, end)
    assert report.count(shared) == 2
    assert "https://clarin.com/a?id=1" in report
    assert "https://reuters.com/b?id=9" in report
    assert "Reform \\[live\\]" in report
    assert "https://elpais.com/c_%28draft%29" in report
    assert len(items) == report.count("](http")
