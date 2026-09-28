from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from latin_america_monitor import collector, cli
from latin_america_monitor.config import Settings
from latin_america_monitor.window import coverage_window
from latin_america_monitor.briefing import write_outputs
from latin_america_monitor.models import Headline


NOW = datetime(2026, 9, 28, 11, tzinfo=timezone.utc)


def response(rows=None, status=200):
    result = Mock(status_code=status, headers={})
    result.json.return_value = {"articles": rows or []}
    return result


def test_rate_limit_is_failure_not_empty_news():
    session = Mock()
    session.get.return_value = response(status=429)
    with patch.object(collector.time, "sleep"), pytest.raises(collector.CollectionError):
        collector._request_json(session, "test", coverage_window(NOW), Settings())
    assert session.get.call_count == 6


def test_cap_splits_and_keeps_both_halves():
    session = Mock()
    session.get.side_effect = [response([{}, {}]), response([{"url": "older"}]), response([{"url": "newer"}])]
    with patch.object(collector.time, "sleep"):
        rows = collector._request_json(session, "test", coverage_window(NOW), Settings(max_records=2))
    assert [r["url"] for r in rows] == ["older", "newer"]
    calls = session.get.call_args_list
    assert calls[1].kwargs["params"]["enddatetime"] == calls[2].kwargs["params"]["startdatetime"]


def test_unsplittable_cap_fails():
    session = Mock()
    session.get.return_value = response([{}])
    window = collector.CoverageWindow(NOW-timedelta(minutes=15), NOW, 1, "test")
    with patch.object(collector.time, "sleep"), pytest.raises(collector.CollectionError):
        collector._request_json(session, "test", window, Settings(max_records=1))


def test_article_ids_preserved_tracking_removed():
    normalize = collector._canonical_url
    assert normalize("https://example.com/article?id=1") != normalize("https://example.com/article?id=2")
    assert normalize("https://example.com/article?id=1&utm_source=test#x") == normalize("https://example.com/article?id=1")
    assert normalize("https://example.com/a?b=1&a=2") == normalize("https://example.com/a?a=2&b=1")


def test_enrichment_keeps_article_links_on_the_same_publisher():
    item = collector.Headline("Reform", "Clarín", "https://clarin.com/a", NOW, "Argentina", "latin_america", "clarin.com")
    assert collector._same_publisher_article(item, "https://www.clarin.com/politica/story")
    assert not collector._same_publisher_article(item, "https://www.clarin.com/")
    assert not collector._same_publisher_article(item, "https://www.clarin.com")
    assert not collector._same_publisher_article(item, "https://www.lanacion.com.ar/politica/story")


@pytest.mark.parametrize("minutes", [61, 75, 90, 120, 180, 24 * 60, 72 * 60])
def test_time_splits_cover_the_parent(minutes):
    window = collector.CoverageWindow(NOW - timedelta(minutes=minutes), NOW, 1, "test")
    left, right = collector.split_capped_window(window)
    assert left.start == window.start
    assert right.end == window.end
    assert left.end >= right.start
    assert left.end - left.start >= collector.MIN_QUERY_TIMESPAN
    assert right.end - right.start >= collector.MIN_QUERY_TIMESPAN
    assert left.end - left.start < window.end - window.start
    assert right.end - right.start < window.end - window.start


def test_query_split_keeps_every_term():
    query = "(domain:a.com OR domain:b.com) (Argentina OR Brazil OR Chile) (president OR election)"
    left, right = collector.split_query(query)
    assert left and right
    for term in ("domain:a.com", "domain:b.com", "Argentina", "Brazil", "Chile", "president", "election"):
        assert term in left or term in right
    assert left.count("(") == right.count("(") == 3


def test_short_capped_window_splits_the_boolean_query():
    session = Mock()
    session.get.side_effect = [response([{}, {}]), response([{"url": "left"}]), response([{"url": "right"}])]
    window = collector.CoverageWindow(NOW - timedelta(minutes=30), NOW, 1, "test")
    query = "(domain:a.com OR domain:b.com) (Argentina OR Brazil) (election)"
    with patch.object(collector.time, "sleep"):
        rows = collector._request_json(session, query, window, Settings(max_records=2))
    assert [row["url"] for row in rows] == ["left", "right"]
    assert session.get.call_args_list[1].kwargs["params"]["startdatetime"] == session.get.call_args_list[0].kwargs["params"]["startdatetime"]
    assert "domain:a.com" in session.get.call_args_list[1].kwargs["params"]["query"]
    assert "domain:b.com" in session.get.call_args_list[2].kwargs["params"]["query"]


def test_plain_text_rejection_is_not_empty_news():
    session = Mock()
    rejected = Mock(status_code=200, headers={}, text="Your query was too short or too long.")
    rejected.json.side_effect = ValueError("not json")
    session.get.return_value = rejected
    with patch.object(collector.time, "sleep"), pytest.raises(collector.CollectionError, match="too short or too long"):
        collector._request_json(session, "q", coverage_window(NOW), Settings())
    assert session.get.call_count == 1


def test_all_queries_require_region():
    for query, _ in collector.build_queries():
        assert any(place in query for place in collector.LATIN_AMERICA_PLACES)


def test_delayed_schedule_has_no_gap(tmp_path):
    monday = cli.scheduled_window(NOW, tmp_path / "state")
    tuesday = cli.scheduled_window(NOW+timedelta(days=1, minutes=20), tmp_path / "state")
    assert monday.end == tuesday.start


def test_failed_day_recovered(tmp_path):
    state = tmp_path / "state"
    state.write_text(NOW.isoformat())
    wednesday = cli.scheduled_window(NOW+timedelta(days=2), state)
    assert wednesday.start == NOW
    assert wednesday.end == NOW + timedelta(days=2)
    assert wednesday.hours == 48
    assert "recovered 48 hours" in wednesday.label


def test_failure_does_not_send_or_advance_state(tmp_path):
    state = tmp_path / "state"
    state.write_text(NOW.isoformat())
    with patch.object(cli, "Settings", return_value=Settings(output_dir=tmp_path)), patch.object(cli, "collect", side_effect=collector.CollectionError("unavailable")), patch.object(cli, "send_report") as send:
        assert cli.main(["--state-file", str(state)]) == 1
    send.assert_not_called()
    assert state.read_text() == NOW.isoformat()
    assert '"status": "failed"' in (tmp_path / "failure.json").read_text()


def test_reports_identify_index_time(tmp_path):
    item = Headline("Election result", "Daily", "https://example.com/a", NOW, "Mexico", "latin_america", "example.com")
    md, csv, js = write_outputs([item], coverage_window(NOW), tmp_path)
    assert "First indexed (UTC)" in md.read_text(encoding="utf-8")
    assert "seen_at" in csv.read_text(encoding="utf-8-sig")
    assert '"seen_at"' in js.read_text(encoding="utf-8")
    assert '"published"' not in js.read_text(encoding="utf-8")


def test_invalid_lookback_rejected():
    with pytest.raises(ValueError):
        coverage_window(NOW, override_hours=-1)


def test_cross_publisher_titles_are_kept_and_tracking_urls_collapse(monkeypatch):
    rows = [
        {"url": "https://www.clarin.com/story?id=1&utm_source=gdelt", "title": "Reform passes", "seendate": "20260928T100000Z", "domain": "clarin.com", "language": "Spanish"},
        {"url": "https://clarin.com/story?utm_medium=email&id=1", "title": "Reform passes", "seendate": "20260928T100000Z", "domain": "clarin.com", "language": "Spanish"},
        {"url": "https://www.reuters.com/world/reform?id=9", "title": "Reform passes", "seendate": "20260928T100500Z", "domain": "reuters.com", "language": "English"},
        {"url": "https://www.reuters.com/world/other?id=10", "title": "Reform passes", "seendate": "20260928T090000Z", "domain": "reuters.com", "language": "English"},
    ]
    monkeypatch.setattr(collector, "_request_json", lambda *args, **kwargs: rows)
    monkeypatch.setattr(collector, "build_queries", lambda *args, **kwargs: [("q", "Latin American press")])
    headlines = collector.collect(coverage_window(NOW), Settings())
    assert len(headlines) == 3
    assert {item.publisher for item in headlines} == {"Clarín", "Reuters"}
    assert sum(item.publisher == "Reuters" for item in headlines) == 2
    assert all(item.url.startswith("https://") for item in headlines)
