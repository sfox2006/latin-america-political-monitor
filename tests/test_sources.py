from latin_america_monitor.collector import build_queries
from latin_america_monitor.sources import PUBLICATIONS, match_publication


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

