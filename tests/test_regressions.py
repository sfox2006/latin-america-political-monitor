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
    assert session.get.call_count == 3


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


def test_small_split_respects_api_minimum():
    session = Mock()
    session.get.side_effect = [response([{}, {}]), response([{"url": "a"}]), response([{"url": "b"}])]
    window = collector.CoverageWindow(NOW-timedelta(minutes=20), NOW, 1, "test")
    with patch.object(collector.time, "sleep"):
        collector._request_json(session, "test", window, Settings(max_records=2))
    for call in session.get.call_args_list[1:]:
        params = call.kwargs["params"]
        start = datetime.strptime(params["startdatetime"], "%Y%m%d%H%M%S")
        end = datetime.strptime(params["enddatetime"], "%Y%m%d%H%M%S")
        assert end-start >= timedelta(minutes=15)


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
