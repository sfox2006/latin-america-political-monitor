import re
from pathlib import Path

from latin_america_monitor.collector import (
    MAX_ENCODED_QUERY_LENGTH,
    POLITICAL_TERMS,
    LATIN_AMERICA_PLACES,
    _encoded_query_length,
    _top_level_groups,
    build_queries,
)
from latin_america_monitor.sources import INTERNATIONAL_PUBLICATIONS, LATIN_AMERICAN_PUBLICATIONS, PUBLICATIONS, match_publication


def test_source_catalogue_is_broad():
    assert len(PUBLICATIONS) >= 85
    assert len({p.market for p in PUBLICATIONS if p.scope == "latin_america"}) >= 20


def test_matches_subdomains():
    publication = match_publication("politica.elpais.com.uy")
    assert publication is not None
    assert publication.name == "El País"
    assert publication.market == "Uruguay"


def test_queries_cover_both_scopes():
    queries = build_queries(8)
    labels = {label for _, label in queries}
    assert labels == {"Latin American press", "international press"}
    assert any("domain:reuters.com" in query for query, _ in queries)
    assert any("domain:clarin.com" in query for query, _ in queries)


def test_queries_fit_index_limit_and_cover_the_catalogue():
    queries = build_queries()
    assert 1 <= len(queries) <= 600
    blob = "\n".join(query for query, _ in queries)
    for publication in LATIN_AMERICAN_PUBLICATIONS + INTERNATIONAL_PUBLICATIONS:
        assert re.search(rf"domain:{re.escape(publication.domain)}(?:\)|\s)", blob)
    for place in LATIN_AMERICA_PLACES:
        assert place in blob
    for term in POLITICAL_TERMS:
        assert term in blob
    assert all(_encoded_query_length(query) <= MAX_ENCODED_QUERY_LENGTH for query, _ in queries)
    places_by_domain: dict[str, set[str]] = {}
    for query, _label in queries:
        groups = _top_level_groups(query)
        assert len(groups) == 3

        def terms(group: str) -> list[str]:
            return [part.strip().strip('"') for part in group[1:-1].split(" OR ")]

        domains = [term.removeprefix("domain:") for term in terms(groups[0])]
        places = set(terms(groups[1]))
        assert set(terms(groups[2])) == set(POLITICAL_TERMS)
        for domain in domains:
            places_by_domain.setdefault(domain, set()).update(places)
    assert set(places_by_domain) == {publication.domain for publication in PUBLICATIONS}
    for domain, places in places_by_domain.items():
        assert places == set(LATIN_AMERICA_PLACES), domain


def test_weekday_workflow_runs_monday_through_friday():
    workflow = Path(".github/workflows/weekday-monitor.yml").read_text(encoding="utf-8")
    assert 'cron: "0 11 * * 1-5"' in workflow
    assert "timeout-minutes: 150" in workflow
    assert "python main.py --scheduled" in workflow

