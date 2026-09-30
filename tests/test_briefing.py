from datetime import datetime, timedelta, timezone

from latin_america_monitor.briefing import build_html, build_markdown, write_outputs
from latin_america_monitor.models import Headline
from latin_america_monitor.window import CoverageWindow


def _item(title, publisher, url, market="Mexico", scope="latin_america", domain="example.com", hours_ago=1, end=None):
    end = end or datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
    return Headline(title, publisher, url, end - timedelta(hours=hours_ago), market, scope, domain)


def test_briefing_is_publisher_headline_and_link_by_region():
    end = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
    mexico = _item("Mexico y China firman un tratado", "Proceso", "https://proceso.com.mx/story", end=end)
    argentina_tier2 = _item("Argentina convoca a su embajador", "La Nación", "https://lanacion.com.ar/fmi", market="Argentina", domain="lanacion.com.ar", hours_ago=1, end=end)
    argentina_tier1 = _item("Milei y Trump acuerdan un tratado", "DW", "https://dw.com/milei", market="International", scope="international", domain="dw.com", hours_ago=5, end=end)
    domestic = _item("Keiko Fujimori aprueba alza del salario minimo", "El Comercio", "https://elcomercio.pe/salario", market="Peru", domain="elcomercio.pe", end=end)
    report = build_markdown([argentina_tier2, domestic, argentina_tier1, mexico])
    assert report.index("NORTEAMÉRICA") < report.index("SUDAMÉRICA")
    assert "MÉXICO" in report and "ARGENTINA" in report
    assert "Proceso: Mexico y China firman un tratado" in report
    assert "https://proceso.com.mx/story" in report
    assert "DW: Milei y Trump acuerdan un tratado" in report
    assert report.index("Milei y Trump") < report.index("Argentina convoca a su embajador")
    assert "salario" not in report
    assert "Results:" not in report
    assert "First indexed" not in report
    assert "headlines from" not in report
    assert "(1)" not in report
    assert "weekend roundup" not in report
    html = build_html([mexico, argentina_tier1])
    assert "Proceso" in html and "https://proceso.com.mx/story" in html
    assert "Results" not in html


def test_briefing_keeps_cross_publisher_duplicates_and_raw_links():
    end = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
    shared = "Mexico and Brazil sign a treaty"
    items = [
        _item(shared, "Clarín", "https://clarin.com/a?id=1", market="Argentina", domain="clarin.com", end=end),
        _item(shared, "Reuters", "https://reuters.com/b?id=9", market="International", scope="international", domain="reuters.com", end=end),
        _item("Chile and China sign a treaty [live]", "El País", "https://elpais.com/c_(draft)", market="Spain", scope="international", domain="elpais.com", hours_ago=3, end=end),
    ]
    report = build_markdown(items)
    assert report.count(shared) == 2
    assert "Clarín: " + shared in report
    assert "Reuters: " + shared in report
    assert "https://clarin.com/a?id=1" in report
    assert "https://reuters.com/b?id=9" in report
    assert "Chile and China sign a treaty [live]" in report
    assert "https://elpais.com/c_(draft)" in report
    assert "\\[" not in report


def test_briefing_has_no_top_n_cap():
    end = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
    items = [
        _item(f"Mexico and China sign treaty number {i}", "Clarín", f"https://clarin.com/{i}", market="Argentina", domain="clarin.com", hours_ago=i + 1, end=end)
        for i in range(40)
    ]
    report = build_markdown(items)
    assert report.count("Clarín:") == 40
    assert all(f"https://clarin.com/{i}" in report for i in range(40))


def test_report_file_is_markdown_only(tmp_path):
    end = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
    window = CoverageWindow(end - timedelta(hours=24), end, 24, "last 24 hours")
    items = [
        _item("Mexico and Brazil sign a treaty", "Clarín", "https://clarin.com/a", market="Argentina", domain="clarin.com", end=end),
        _item("Mexico and Brazil sign a treaty", "Reuters", "https://reuters.com/b", market="International", scope="international", domain="reuters.com", hours_ago=1, end=end),
    ]
    path = write_outputs(items, window, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert path.name.endswith(".md")
    assert text.count("Mexico and Brazil sign a treaty") == 2
    assert list(tmp_path.glob("*.csv")) == []
    assert list(tmp_path.glob("*.json")) == []
    assert "First indexed" not in text
    assert "seen_at" not in text
